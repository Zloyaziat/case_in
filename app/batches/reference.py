"""Сравнение окна с эталонными партиями (чистый Python).

  1. pick_references   из эталонных партий формулы берём 10: сначала с близким v_in, потом более свежие
  2. RefIndex          для шага и времени окна собираем значения датчиков этих партий
  3. compare           delta = current - ref_avg; рекомендация, если |delta| > max(k * ref_std, допуск датчика)"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping

REF_LIMIT = 10        # сколько эталонных партий участвует в сравнении
K_STD = 3.0           # во сколько разбросов эталона допускается отклонение


@dataclass(frozen=True)
class RefBatch:
    id: int
    v_in: Mapping[str, float] | None
    started_at: datetime | None


def v_in_distance(a: Mapping[str, float] | None, b: Mapping[str, float] | None) -> float:
    """Средняя относительная разница по компонентам сырья: 0 - совпадает, компонент есть только в одной - 1."""
    a, b = a or {}, b or {}
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    total = 0.0
    for k in keys:
        if k not in a or k not in b:
            total += 1.0
            continue
        x, y = float(a[k]), float(b[k])
        total += min(1.0, abs(x - y) / max(abs(x), abs(y), 1e-9))
    return total / len(keys)


def pick_references(candidates: Iterable[RefBatch], v_in: Mapping[str, float] | None,
                    limit: int = REF_LIMIT) -> list[RefBatch]:
    """Ближайшие по v_in; при равенстве - более свежие."""
    def key(b: RefBatch):
        ts = b.started_at.timestamp() if b.started_at else float("-inf")
        return v_in_distance(v_in, b.v_in), -ts
    return sorted(candidates, key=key)[:limit]


def time_key(seconds: float) -> int:
    """Время окна как ключ: миллисекунды (2.0 и 2.0000001 - одно окно)."""
    return int(round(seconds * 1000))


class RefIndex:
    """{(шаг, время окна): {датчик: [значения эталонных партий]}}."""

    def __init__(self) -> None:
        self.data: dict[tuple[int, int], dict[str, list[float]]] = {}
        self.batch_ids: list[int] = []

    def add(self, step: int, time_s: float, detectors: Mapping[str, object]) -> None:
        slot = self.data.setdefault((step, time_key(time_s)), {})
        for tag, v in detectors.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                slot.setdefault(tag, []).append(float(v))

    def at(self, step: int, time_s: float) -> dict[str, list[float]]:
        return self.data.get((step, time_key(time_s)), {})


@dataclass(frozen=True)
class Deviation:
    tag: str
    value: float
    ref_avg: float
    ref_std: float
    n_refs: int
    delta: float
    threshold: float

    @property
    def direction(self) -> str:
        """'up' - значение ниже эталона, надо поднять; 'down' - выше, надо опустить."""
        return "up" if self.delta < 0 else "down"


def compare(current: Mapping[str, float], refs: Mapping[str, list[float]],
            tolerance: Mapping[str, float] | None = None, k: float = K_STD) -> list[Deviation]:
    """Отклонения окна от эталона. Датчики без эталонных значений в этот момент не проверяются."""
    tolerance = tolerance or {}
    out = []
    for tag, value in current.items():
        vals = refs.get(tag)
        if not vals:
            continue
        avg = statistics.fmean(vals)
        std = statistics.stdev(vals) if len(vals) > 1 else 0.0
        delta = value - avg
        threshold = max(k * std, tolerance.get(tag) or 0.0)
        if abs(delta) > threshold:
            out.append(Deviation(tag, value, round(avg, 4), round(std, 4), len(vals),
                                 round(delta, 4), round(threshold, 4)))
    return out
