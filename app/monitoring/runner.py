"""Цикл симуляции: по стадиям, с таймером. Чистый asyncio, без БД - запись делает "sink"."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

from .engine import Reading, SensorPlan, Verdict, evaluate
from .plan import StepRun, n_ticks
from .source import FileSource, SyntheticSource, pick_sources


@dataclass
class TickItem:
    plan: SensorPlan
    reading: Reading
    verdict: Verdict
    source: str          # 'file' | 'synthetic'


class Sink(Protocol):
    async def step_started(self, step: StepRun, sources: dict[str, str], n: int) -> None: ...
    async def tick(self, step: StepRun, k: int, n: int, elapsed_s: float, items: list[TickItem]) -> None: ...
    async def step_finished(self, step: StepRun, completed: bool) -> None: ...


async def run_plan(
    steps: list[StepRun],
    *,
    sink: Sink,
    tick_seconds: float = 0.5,
    file_source: FileSource | None = None,
    source_mode: str = "auto",
    fault_rate: float = 0.05,
    seed: int | str | None = None,
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    clock: Callable[[], float] = time.monotonic,
    emit: Callable[[dict], None] | None = None,
) -> dict:
    """Проходит стадии по порядку. На каждом тике (раз в tick_seconds) читает показания датчиков
    текущей стадии, проверяет их, отдаёт sink-у. Возвращает сводку."""
    emit = emit or (lambda e: None)
    synth = SyntheticSource(seed=seed, fault_rate=fault_rate)
    summary = {"steps": [], "readings": 0, "alerts": 0}

    for step in steps:
        n = n_ticks(step.duration_s, tick_seconds)
        sources = pick_sources(step.sensors, file_source, source_mode)
        await sink.step_started(step, sources, n)
        emit({"type": "step_start", "step": step.step, "key": step.key, "title": step.title,
              "duration_s": step.duration_s, "ticks": n, "sources": sources})

        stats = {"step": step.step, "ticks": n, "readings": 0, "alerts": 0, "sources": sources}
        completed = False
        try:
            t0 = clock()
            for k in range(n):
                elapsed = min(step.duration_s, (k + 1) * tick_seconds)
                items: list[TickItem] = []
                for sp in step.sensors:
                    if sources[sp.tag] == "file" and file_source is not None:
                        readings = file_source.slice(sp.tag, k, n)
                    else:
                        readings = [synth.reading(sp, k, n)]
                    for r in readings:
                        items.append(TickItem(sp, r, evaluate(sp, r), sources[sp.tag]))

                await sink.tick(step, k, n, elapsed, items)

                stats["readings"] += len(items)
                emit({"type": "tick", "step": step.step, "k": k + 1, "ticks": n,
                      "elapsed_s": elapsed, "readings": len(items)})
                for it in items:
                    if it.verdict.is_alert:
                        stats["alerts"] += 1
                        emit({"type": "alert", "step": step.step, "key": step.key, "tag": it.plan.tag,
                              "status": it.verdict.status, "value": it.reading.value, "raw": it.reading.raw,
                              "target": it.verdict.target, "elapsed_s": elapsed,
                              "duration_s": step.duration_s, "message": it.verdict.message})

                delay = t0 + (k + 1) * tick_seconds - clock()
                if delay > 0:
                    await sleep(delay)
            completed = True
        finally:
            await sink.step_finished(step, completed)
            emit({"type": "step_end", "step": step.step, "completed": completed, **{
                "readings": stats["readings"], "alerts": stats["alerts"]}})
        summary["steps"].append(stats)
        summary["readings"] += stats["readings"]
        summary["alerts"] += stats["alerts"]
    return summary
