"""Управляет единственным активным прогоном: запуск, остановка, статус, журнал событий."""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone

from ..database import async_session
from .plan import StepRun
from .repo import DbSink, finish_run
from .runner import run_plan
from .source import FileSource

logger = logging.getLogger("uvicorn.error")      # его uvicorn показывает в консоли


class SimulationManager:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.run_id: int | None = None
        self.events: deque[dict] = deque(maxlen=500)
        self.current: dict = {}
        self.summary: dict | None = None

    def is_running(self) -> bool:
        return self.task is not None and not self.task.done()

    async def start(self, run_id: int, steps: list[StepRun], *, tick_seconds: float, source_mode: str,
                    fault_rate: float, seed: int | None, file_source: FileSource | None) -> None:
        self.run_id = run_id
        self.events.clear()
        self.summary = None
        self.current = {"running": True, "step": None, "total_steps": len(steps),
                        "readings": 0, "alerts": 0, "elapsed_s": 0.0, "duration_s": None}
        self.task = asyncio.create_task(
            self._run(run_id, steps, tick_seconds, source_mode, fault_rate, seed, file_source))

    async def _run(self, run_id, steps, tick_seconds, source_mode, fault_rate, seed, file_source) -> None:
        status, note = "finished", None
        sink = DbSink(run_id, async_session)
        try:
            self.summary = await run_plan(
                steps, sink=sink, tick_seconds=tick_seconds, file_source=file_source,
                source_mode=source_mode, fault_rate=fault_rate, seed=seed, emit=self._emit)
        except asyncio.CancelledError:
            status = "stopped"
            raise
        except Exception as e:                       # noqa: BLE001 - фиксируем причину в БД
            status, note = "failed", repr(e)
            logger.exception("Симуляция %s упала", run_id)
        finally:
            self.current["running"] = False
            self.current["status"] = status
            await finish_run(async_session, run_id, status, note)
            logger.info("Симуляция %s: %s", run_id, status)

    def _emit(self, event: dict) -> None:
        kind = event["type"]
        if kind == "tick":                           # частые события в журнал не кладём
            self.current["elapsed_s"] = event["elapsed_s"]
            self.current["readings"] += event["readings"]
            return
        event = {"run_id": self.run_id, "at": datetime.now(timezone.utc).isoformat(), **event}
        self.events.append(event)
        if kind == "step_start":
            self.current.update(step=event["step"], step_key=event["key"], title=event["title"],
                                duration_s=event["duration_s"], elapsed_s=0.0, sources=event["sources"])
            logger.info("[run %s] стадия %s «%s»: %.1f с, %s тиков, источники: %s", self.run_id,
                        event["step"], event["key"], event["duration_s"], event["ticks"], event["sources"])
        elif kind == "alert":
            self.current["alerts"] += 1
            self.current["elapsed_s"] = event["elapsed_s"]
            logger.warning("[run %s | стадия %s | %.1f/%.0f с] %s", self.run_id, event["step"],
                           event["elapsed_s"], event["duration_s"], event["message"])

    async def stop(self) -> bool:
        if not self.is_running():
            return False
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
        return True

    def status(self) -> dict:
        alerts = [e for e in self.events if e["type"] == "alert"]
        return {"run_id": self.run_id, "running": self.is_running(), **self.current,
                "recent_alerts": [{"at": a["at"], "step": a["step"], "tag": a["tag"], "status": a["status"],
                                   "value": a["value"], "target": a["target"], "message": a["message"]}
                                  for a in alerts[-20:]]}


manager = SimulationManager()
