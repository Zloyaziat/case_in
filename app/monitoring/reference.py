"""Эталонные партии: генерируем N "хороших" прогонов и считаем средние начала/конца (чистый Python).

Для каждой пары (стадия, датчик) берём "идеальное" начальное и конечное значение:
  * центр допустимой полосы в начале и в конце стадии (из pre/during/post формулы);
  * если диапазонов в формуле нет - val_start / val_end из таблицы sensors.
Каждая из N партий - это эти значения + случайный разброс (внутри полосы). Среднее по партиям
и есть "наиболее подходящее" число, которое показываем при отклонении."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable

from .engine import Range, SensorLimits, SensorSpec, band_at


@dataclass(frozen=True)
class RefTarget:
    start: float
    end: float
    sigma: float                     # разброс между партиями
    start_band: Range | None = None
    end_band: Range | None = None


def ref_target(limits: SensorLimits, spec: SensorSpec) -> RefTarget | None:
    b0, b1 = band_at(limits, 0.0), band_at(limits, 1.0)
    start = b0.center() if b0 is not None else spec.val_start
    end = b1.center() if b1 is not None else spec.val_end
    if start is None and end is None:
        return None
    start = end if start is None else start
    end = start if end is None else end

    widths = [w for w in (b0.width() if b0 else None, b1.width() if b1 else None) if w]
    if widths:
        sigma = 0.08 * (sum(widths) / len(widths))
    else:
        sigma = max(spec.noise_sd or 0.0, 0.01 * abs((start + end) / 2), 1e-6)
    return RefTarget(start, end, sigma, b0, b1)


def _draw(rnd: random.Random, mean: float, sigma: float, band: Range | None) -> float:
    x = rnd.gauss(mean, sigma)
    if band is not None:
        x = band.clip(x)
    return round(x, 4)


def generate_batches(
    targets: dict[str, RefTarget], n_batches: int = 30, seed: int | str = 0, salt: str = ""
) -> list[tuple[int, str, float, float]]:
    """-> [(номер_партии, tag, v_start, v_end)]; для одного seed результат всегда одинаков."""
    rows = []
    for tag in sorted(targets):
        t = targets[tag]
        rnd = random.Random(f"{seed}:{salt}:{tag}")
        for b in range(1, n_batches + 1):
            rows.append((b, tag, _draw(rnd, t.start, t.sigma, t.start_band),
                         _draw(rnd, t.end, t.sigma, t.end_band)))
    return rows


def profile_from_rows(rows: Iterable[tuple[int, str, float, float]]) -> dict[str, tuple[float, float, int]]:
    acc: dict[str, list[float]] = {}
    for _, tag, v0, v1 in rows:
        a = acc.setdefault(tag, [0.0, 0.0, 0])
        a[0] += v0
        a[1] += v1
        a[2] += 1
    return {t: (a[0] / a[2], a[1] / a[2], int(a[2])) for t, a in acc.items()}
