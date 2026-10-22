"""План прогона: какие стадии, какие на них датчики, сколько секунд каждая стадия (чистый Python)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .engine import SensorPlan, SensorSpec, parse_step_sensors

MAX_REAL_SECONDS = 120.0     # дольше без явного указания длительности стадию не запускаем


@dataclass
class StepRun:
    step: int                        # номер стадии в формуле
    key: str                         # step_key
    title: str                       # step_value
    duration_s: float                # сколько секунд длится стадия в этом прогоне
    sensors: list[SensorPlan] = field(default_factory=list)
    step_id: int | None = None       # formula_steps.id
    duration_source: str = ""        # откуда взята длительность (для отчёта)


def build_sensor_plans(
    dict_plc_id,
    specs: Mapping[str, SensorSpec],
    profile: Mapping[str, tuple[float | None, float | None]] | None = None,
) -> list[SensorPlan]:
    """Датчики стадии. profile: {tag: (среднее_начало, среднее_конец)} по эталонным партиям."""
    profile = profile or {}
    plans = []
    for tag, limits in parse_step_sensors(dict_plc_id).items():
        spec = specs.get(tag) or SensorSpec(tag=tag)
        start, end = profile.get(tag, (None, None))
        plans.append(SensorPlan(spec=spec, limits=limits, start_mean=start, end_mean=end))
    return plans


def resolve_duration(
    step: int,
    amount_time_s: float | None,
    step_seconds: float | None = None,
    per_step: Mapping[int, float] | None = None,
    max_real_s: float = MAX_REAL_SECONDS,
) -> tuple[float, str]:
    """Приоритет: длительность для стадии > общая step_seconds > amount_time из БД.

    Если берём amount_time из БД и он длиннее max_real_s (например, "1 day") - просим указать
    короткую длительность, чтобы не запустить симуляцию на сутки."""
    if per_step and step in per_step:
        return float(per_step[step]), "запрос (для стадии)"
    if step_seconds is not None:
        return float(step_seconds), "запрос (для всех стадий)"
    if amount_time_s is None or amount_time_s <= 0:
        raise ValueError(f"у стадии {step} не задан amount_time - укажите step_seconds (например 14)")
    if amount_time_s > max_real_s:
        raise ValueError(
            f"стадия {step} длится {amount_time_s:.0f} с по данным БД - укажите step_seconds "
            f"(например 14) или step_durations, либо выставьте amount_time в секундах через PATCH")
    return float(amount_time_s), "БД (amount_time)"


def n_ticks(duration_s: float, tick_s: float) -> int:
    return max(1, int(round(duration_s / tick_s)))
