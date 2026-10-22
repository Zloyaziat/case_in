"""Ход партии: таймер шагов и усреднение показаний по окнам (чистый Python, без БД и asyncio).

Всё время - в секундах от старта партии. Время показания внутри шага = t - начало шага,
поэтому партии, запущенные в разное время, сравнимы между собой.

Окно - полуинтервал (end - window_s; end]: показание ровно на 2.0 с попадает в окно с end = 2.0.
Окно закрывается, когда время ушло за его правую границу; пустые окна не записываются."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .opc import OpcLine

EPS = 1e-9


@dataclass(frozen=True)
class StepDef:
    step: int
    tags: frozenset[str]
    planned_s: float | None        # None - шаг заканчивает только оператор


@dataclass(frozen=True)
class StepStarted:
    step: int
    at_s: float


@dataclass(frozen=True)
class StepEnded:
    step: int
    at_s: float
    ended_by: str                  # timer | operator | finish | abort


@dataclass(frozen=True)
class WindowClosed:
    step: int
    end_s: float                   # правая граница окна от начала шага
    values: dict[str, float]       # средние по датчикам
    counts: dict[str, int]

    @property
    def n_samples(self) -> int:
        return sum(self.counts.values())


@dataclass(frozen=True)
class ProcessDone:
    at_s: float


@dataclass
class Counters:
    accepted: int = 0              # попали в среднее
    ignored: int = 0               # датчик не относится к текущему шагу / шаг не идёт
    bad_value: int = 0             # пришёл мусор вместо числа
    out_of_range: int = 0          # вне физических пределов датчика (valid_min/valid_max)


@dataclass
class BatchProcess:
    steps: list[StepDef]
    window_s: float = 2.0
    limits: Mapping[str, tuple[float | None, float | None]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("у партии нет шагов")
        if self.window_s <= 0:
            raise ValueError("окно усреднения должно быть > 0")
        self.idx = -1                       # -1 - не начата; len(steps) - все шаги пройдены
        self.step_t0 = 0.0
        self.open_end: float | None = None
        self.buf: dict[str, list[float]] = {}
        self.counters = Counters()

    # ------------------------------------------------------------ состояние

    @property
    def current(self) -> StepDef | None:
        return self.steps[self.idx] if 0 <= self.idx < len(self.steps) else None

    @property
    def done(self) -> bool:
        return self.idx >= len(self.steps)

    def step_elapsed(self, t: float) -> float | None:
        return None if self.current is None else max(0.0, t - self.step_t0)

    # ------------------------------------------------------------ управление

    def start(self) -> list:
        if self.idx != -1:
            raise RuntimeError("партия уже запущена")
        return self._begin(0, 0.0)

    def advance(self, t: float, lines: Iterable[OpcLine] = ()) -> list:
        """Принимает показания, пришедшие к моменту t, и двигает таймеры. -> события по порядку."""
        events: list = []
        for line in lines:
            events += self._run_until(line.offset_s)
            events += self._accept(line)
        events += self._run_until(t)
        return events

    def next_step(self, t: float) -> list:
        """Оператор завершает текущий шаг досрочно."""
        events = self._run_until(t)
        if self.current is not None:
            events += self._end_step(t, "operator")
        return events

    def stop(self, t: float, ended_by: str) -> list:
        """Завершение или прерывание партии: закрыть текущий шаг и больше ничего не принимать."""
        events = self._run_until(t)
        if self.current is not None:
            events += self._end_step(t, ended_by, then_next=False)
            self.idx = len(self.steps)
            events.append(ProcessDone(t))
        return events

    # ------------------------------------------------------------ внутреннее

    def _begin(self, idx: int, t: float) -> list:
        self.idx = idx
        self.step_t0 = t
        if self.done:
            return [ProcessDone(t)]
        return [StepStarted(self.steps[idx].step, t)]

    def _run_until(self, t: float) -> list:
        events: list = []
        while self.current is not None:
            elapsed = t - self.step_t0
            planned = self.current.planned_s
            if planned is not None and elapsed > planned + EPS:
                events += self._end_step(self.step_t0 + planned, "timer")
                continue
            if self.open_end is not None and elapsed > self.open_end + EPS:
                events.append(self._flush(self.open_end))
            break
        return events

    def _end_step(self, t: float, ended_by: str, then_next: bool = True) -> list:
        step = self.current
        events: list = []
        if self.open_end is not None:
            # окно, оборванное концом шага, подписываем фактической границей
            events.append(self._flush(min(self.open_end, max(round(t - self.step_t0, 3), 0.001))))
        events.append(StepEnded(step.step, t, ended_by))
        if then_next:
            events += self._begin(self.idx + 1, t)
        return events

    def _window_end(self, elapsed: float) -> float:
        k = max(1, math.ceil(elapsed / self.window_s - EPS))
        end = round(k * self.window_s, 6)
        planned = self.current.planned_s
        return min(end, planned) if planned is not None else end

    def _accept(self, line: OpcLine) -> list:
        step = self.current
        if step is None or line.tag not in step.tags:
            self.counters.ignored += 1
            return []
        if line.value is None:
            self.counters.bad_value += 1
            return []
        lo, hi = self.limits.get(line.tag, (None, None))
        if (lo is not None and line.value < lo - EPS) or (hi is not None and line.value > hi + EPS):
            self.counters.out_of_range += 1
            return []
        events = []
        end = self._window_end(line.offset_s - self.step_t0)
        if self.open_end is not None and end != self.open_end:
            # только если строки пришли не по порядку времени: старое окно закрываем как есть
            events.append(self._flush(self.open_end))
        self.open_end = end
        self.buf.setdefault(line.tag, []).append(line.value)
        self.counters.accepted += 1
        return events

    def _flush(self, end_s: float) -> WindowClosed:
        values = {tag: round(sum(v) / len(v), 4) for tag, v in self.buf.items()}
        counts = {tag: len(v) for tag, v in self.buf.items()}
        ev = WindowClosed(self.current.step, end_s, values, counts)
        self.buf = {}
        self.open_end = None
        return ev
