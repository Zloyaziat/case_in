"""Живая партия: проигрывает OPC-файл, двигает таймеры шагов, пишет окна и рекомендации в БД.

Каждый тик (TICK_S): берём строки, "пришедшие" к текущему моменту, отдаём их BatchProcess,
события сохраняем одной транзакцией. speed > 1 ускоряет и файл, и таймеры шагов одинаково."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Mapping

from sqlalchemy import update

from ..monitoring.engine import SensorSpec, action_message
from .models import Batch, BatchRecommendation, BatchStep, BatchStepWindow
from .opc import OpcEmulator
from .process import BatchProcess, ProcessDone, StepEnded, StepStarted, WindowClosed
from .reference import K_STD, RefIndex, compare

logger = logging.getLogger("uvicorn.error")

TICK_S = 0.1


class BatchSession:
    def __init__(self, batch_id: int, wall0: datetime, process: BatchProcess, emulator: OpcEmulator,
                 refs: RefIndex, specs: Mapping[str, SensorSpec], session_factory, *,
                 speed: float = 1.0, k: float = K_STD, clock=time.monotonic, sleep=asyncio.sleep):
        self.batch_id = batch_id
        self.wall0 = wall0
        self.process = process
        self.emulator = emulator
        self.refs = refs
        self.specs = specs
        self.tolerance = {t: s.noise_sd for t, s in specs.items() if s.noise_sd}
        self.sf = session_factory
        self.speed = speed
        self.k = k
        self.clock = clock
        self.sleep = sleep
        self.lock = asyncio.Lock()
        self.task: asyncio.Task | None = None
        self.t0 = 0.0
        self.error: str | None = None
        self.windows: deque[dict] = deque(maxlen=30)
        self.recommendations: deque[dict] = deque(maxlen=50)

    # ------------------------------------------------------------ время

    def now(self) -> float:
        """Секунды процесса от старта партии (с учётом speed)."""
        return (self.clock() - self.t0) * self.speed

    def wall(self, t_s: float) -> datetime:
        return self.wall0 + timedelta(seconds=t_s / self.speed)

    # ------------------------------------------------------------ управление

    async def begin(self) -> None:
        self.t0 = self.clock()
        await self._persist(self.process.start())
        self.task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        try:
            while not self.process.done:
                await self.sleep(TICK_S)
                async with self.lock:
                    await self._persist(self._advance())
        except asyncio.CancelledError:
            raise
        except Exception as e:                       # noqa: BLE001 - показываем причину в статусе
            self.error = repr(e)
            logger.exception("Партия %s: сбой обработки показаний", self.batch_id)

    def _advance(self) -> list:
        t = self.now()
        return self.process.advance(t, self.emulator.poll(t))

    async def next_step(self) -> None:
        async with self.lock:
            events = self._advance()
            events += self.process.next_step(self.now())
            await self._persist(events)

    async def stop(self, ended_by: str) -> float:
        """Останавливает приём показаний; -> момент остановки (секунды процесса)."""
        if self.task is not None and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        async with self.lock:
            events = self._advance()
            t = self.now()
            events += self.process.stop(t, ended_by)
            await self._persist(events)
        return t

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    # ------------------------------------------------------------ запись

    async def _persist(self, events: list) -> None:
        if not events:
            return
        async with self.sf() as db:
            for ev in events:
                if isinstance(ev, StepStarted):
                    step = next(s for s in self.process.steps if s.step == ev.step)
                    db.add(BatchStep(batch_id=self.batch_id, step=ev.step, started_at=self.wall(ev.at_s),
                                     status="running", planned_seconds=step.planned_s))
                    await db.execute(update(Batch).where(Batch.id == self.batch_id).values(current_step=ev.step))
                    logger.info("[партия %s] шаг %s начат", self.batch_id, ev.step)
                elif isinstance(ev, StepEnded):
                    await db.execute(
                        update(BatchStep).where(BatchStep.batch_id == self.batch_id, BatchStep.step == ev.step)
                        .values(finished_at=self.wall(ev.at_s), ended_by=ev.ended_by,
                                status="aborted" if ev.ended_by == "abort" else "done"))
                    logger.info("[партия %s] шаг %s завершён (%s)", self.batch_id, ev.step, ev.ended_by)
                elif isinstance(ev, WindowClosed):
                    self._save_window(db, ev)
                elif isinstance(ev, ProcessDone):
                    await db.execute(update(Batch).where(Batch.id == self.batch_id).values(current_step=None))
            await db.commit()

    def _save_window(self, db, ev: WindowClosed) -> None:
        at = timedelta(seconds=ev.end_s)
        db.add(BatchStepWindow(batch_id=self.batch_id, step=ev.step, time=at,
                               detectors=ev.values, n_samples=ev.n_samples))
        self.windows.append({"step": ev.step, "time_s": ev.end_s, "values": ev.values, "n_samples": ev.n_samples})

        for d in compare(ev.values, self.refs.at(ev.step, ev.end_s), self.tolerance, self.k):
            spec = self.specs.get(d.tag) or SensorSpec(tag=d.tag)
            msg = action_message(d.direction, spec, d.ref_avg)
            db.add(BatchRecommendation(batch_id=self.batch_id, step=ev.step, time=at, tag=d.tag,
                                       value=d.value, ref_avg=d.ref_avg, ref_std=d.ref_std, n_refs=d.n_refs,
                                       delta=d.delta, threshold=d.threshold, message=msg))
            self.recommendations.append({"step": ev.step, "time_s": ev.end_s, "tag": d.tag, "value": d.value,
                                         "ref_avg": d.ref_avg, "delta": d.delta, "message": msg})
            logger.warning("[партия %s | шаг %s | %.1f с] %s", self.batch_id, ev.step, ev.end_s, msg)

    # ------------------------------------------------------------ статус

    def status(self) -> dict:
        t = self.now()
        cur = self.process.current
        c = self.process.counters
        return {
            "receiving": self.running,
            "process_time_s": round(t, 2),
            "step": cur.step if cur else None,
            "step_elapsed_s": round(self.process.step_elapsed(t), 2) if cur else None,
            "step_planned_s": cur.planned_s if cur else None,
            "steps_done": self.process.done,
            "speed": self.speed,
            "window_s": self.process.window_s,
            "reference_batches": self.refs.batch_ids,
            "opc": {"read": self.emulator.pos, "total": len(self.emulator.lines)},
            "readings": {"accepted": c.accepted, "ignored": c.ignored,
                         "bad_value": c.bad_value, "out_of_range": c.out_of_range},
            "last_windows": list(self.windows)[-5:],
            "recommendations": list(self.recommendations)[-20:],
            "error": self.error,
        }


sessions: dict[int, BatchSession] = {}


async def shutdown() -> None:
    """При остановке сервера: прекращаем приём показаний. Партии в БД остаются running."""
    for s in sessions.values():
        if s.task is not None and not s.task.done():
            s.task.cancel()
    await asyncio.gather(*(s.task for s in sessions.values() if s.task), return_exceptions=True)
    sessions.clear()
