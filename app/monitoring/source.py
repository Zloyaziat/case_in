"""Откуда берутся показания: строки CSV-файла или синтетический генератор (чистый Python)."""
from __future__ import annotations

import csv
import math
import os
import random

from .engine import Reading, SensorPlan, clamp01, evaluate

_CACHE: dict[str, tuple[float, dict[str, list[Reading]]]] = {}


def parse_value(raw) -> float | None:
    """'37.03' -> 37.03; 'ERR', '-----', '' -> None."""
    if raw is None:
        return None
    s = str(raw).strip().replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _opt_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load_csv(path: str | os.PathLike) -> dict[str, list[Reading]]:
    """sensor_data_5000.csv -> {tag: [Reading, ...]} в порядке строк файла."""
    path = str(path)
    mtime = os.path.getmtime(path)
    hit = _CACHE.get(path)
    if hit and hit[0] == mtime:
        return hit[1]

    by_tag: dict[str, list[dict]] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            tag = (row.get("tag") or "").strip()
            if tag:
                by_tag.setdefault(tag, []).append(row)

    out: dict[str, list[Reading]] = {}
    for tag, rows in by_tag.items():
        n = len(rows)
        readings = []
        for i, row in enumerate(rows):
            pr = _opt_float(row.get("progress_pct"))
            progress = clamp01(pr / 100.0) if pr is not None else (i + 0.5) / n
            raw = row.get("value")
            rid = _opt_float(row.get("row_id"))
            lab = row.get("is_anomaly")
            readings.append(Reading(
                tag=tag,
                raw=raw if raw not in (None, "") else None,
                value=parse_value(raw),
                progress=progress,
                unit=(row.get("unit") or None),
                quality=(row.get("quality") or None),
                source_row_id=int(rid) if rid is not None else None,
                label_anomaly=(lab.strip() == "1") if lab not in (None, "") else None,
                label_type=(row.get("anomaly_type") or None),
            ))
        out[tag] = readings
    _CACHE[path] = (mtime, out)
    return out


class FileSource:
    """Читает строки файла. За стадию из n тиков каждая строка датчика читается ровно один раз:
    если строк больше, чем тиков, за тик читается несколько; если меньше - не на каждом тике."""

    def __init__(self, table: dict[str, list[Reading]]):
        self.table = table

    @classmethod
    def from_path(cls, path) -> "FileSource":
        return cls(load_csv(path))

    def rows(self, tag: str) -> list[Reading]:
        return self.table.get(tag, [])

    def slice(self, tag: str, k: int, n: int) -> list[Reading]:
        rows = self.rows(tag)
        total = len(rows)
        return rows[k * total // n:(k + 1) * total // n]


class SyntheticSource:
    """Генерирует показания рядом с эталоном; с вероятностью fault_rate - отклонение или сбой датчика."""

    def __init__(self, seed: int | str | None = None, fault_rate: float = 0.05):
        self.rnd = random.Random(seed)
        self.fault_rate = fault_rate

    def reading(self, plan: SensorPlan, k: int, n: int) -> Reading:
        p = (k + 1) / n
        band = plan.band(p)
        exp = plan.expected(p)
        if exp is None and band is not None:
            exp = band.center()
        if exp is None:
            exp = 0.0
        noise = plan.spec.noise_sd or max(0.005 * abs(exp), 1e-6)
        x = self.rnd.gauss(exp, noise)
        if band is not None:
            x = band.clip(x)

        if self.rnd.random() < self.fault_rate:
            roll = self.rnd.random()
            if roll < 0.15:                                    # датчик отдал мусор
                return Reading(plan.tag, "ERR", None, p, plan.spec.unit, "BAD", None, True, "error_string")
            width = band.width() if band and band.width() else max(abs(exp) * 0.1, 1.0)
            push = (0.2 + 0.8 * self.rnd.random()) * width
            go_up = self.rnd.random() < 0.5
            if band is not None and band.min is None:
                go_up = True
            if band is not None and band.max is None:
                go_up = False
            if band is not None:
                x = (band.max + push) if go_up and band.max is not None else (band.min - push if band.min is not None else x)
            else:
                x = exp + (push if go_up else -push)
            return Reading(plan.tag, f"{x:.4f}", x, p, plan.spec.unit, "GOOD", None, True, "process_violation")
        return Reading(plan.tag, f"{x:.4f}", x, p, plan.spec.unit, "GOOD", None, False, None)


def pick_sources(sensors: list[SensorPlan], file_source: FileSource | None, mode: str = "auto",
                 threshold: float = 0.7) -> dict[str, str]:
    """Для каждого датчика стадии выбирает 'file' или 'synthetic'.

    mode='synthetic' - всегда генератор; 'file' - файл, а если строк датчика в нём нет - генератор;
    'auto' - файл, только если его значения в основном ложатся в допустимую полосу этой стадии
    (иначе файл относится к другой стадии процесса, и сравнивать с ним бессмысленно)."""
    out: dict[str, str] = {}
    for sp in sensors:
        rows = file_source.rows(sp.tag) if file_source else []
        if mode == "synthetic" or not rows:
            out[sp.tag] = "synthetic"
        elif mode == "file":
            out[sp.tag] = "file"
        else:
            nums = [r for r in rows if r.value is not None]
            ok = sum(1 for r in nums if evaluate(sp, r).status in ("ok", "no_limits"))
            out[sp.tag] = "file" if (not nums or ok / len(nums) >= threshold) else "synthetic"
    return out
