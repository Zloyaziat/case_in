"""Ядро проверки датчиков (чистый Python, без БД и FastAPI - поэтому легко тестируется).

Что здесь есть:
  Range / SensorLimits   допустимые диапазоны датчика на стадии (pre / during / post из dict_PLC_id)
  band_at(limits, p)     допустимая "полоса" значения в момент p (0..1) стадии
  SensorPlan             датчик на конкретной стадии: диапазоны + эталонные среднее начала/конца
  evaluate(plan, r)      проверка одного показания -> Verdict (ok / low / high / bad_value / ...)
  action_message(...)    текст сигнала: "Нужно повысить температуру до 39 °C на датчике F-TT-01!"
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

EPS = 1e-9
PHASES = ("pre", "during", "post")


# ---------------------------------------------------------------- диапазоны

@dataclass(frozen=True)
class Range:
    min: float | None = None
    max: float | None = None

    def center(self) -> float | None:
        if self.min is not None and self.max is not None:
            return (self.min + self.max) / 2
        return self.min if self.min is not None else self.max

    def width(self) -> float | None:
        if self.min is not None and self.max is not None:
            return self.max - self.min
        return None

    def clip(self, x: float) -> float:
        if self.min is not None and x < self.min:
            return self.min
        if self.max is not None and x > self.max:
            return self.max
        return x


@dataclass(frozen=True)
class SensorLimits:
    """Допустимый диапазон датчика: до цикла / во время / после цикла."""
    pre: Range | None = None
    during: Range | None = None
    post: Range | None = None

    def is_empty(self) -> bool:
        return self.pre is None and self.during is None and self.post is None


def _num(x: Any) -> float | None:
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def parse_range(obj: Any) -> Range | None:
    if not isinstance(obj, dict):
        return None
    lo, hi = _num(obj.get("min")), _num(obj.get("max"))
    if lo is None and hi is None:
        return None
    if lo is not None and hi is not None and lo > hi:
        return None
    return Range(lo, hi)


def parse_step_sensors(dict_plc_id: Any) -> dict[str, SensorLimits]:
    """formula_steps.dict_plc_id -> {tag: SensorLimits}.

    Понимает новый формат {"F-TT-01": {"pre": {...}, "during": {...}, "post": {...}}}
    и старый - просто список тегов ["F-TT-01", ...] (тогда диапазонов нет)."""
    out: dict[str, SensorLimits] = {}
    if isinstance(dict_plc_id, dict):
        for tag, lim in dict_plc_id.items():
            if not isinstance(tag, str):
                continue
            if isinstance(lim, dict):
                out[tag] = SensorLimits(
                    pre=parse_range(lim.get("pre")),
                    during=parse_range(lim.get("during")),
                    post=parse_range(lim.get("post")),
                )
            else:
                out[tag] = SensorLimits()
    elif isinstance(dict_plc_id, (list, tuple)):
        for tag in dict_plc_id:
            if isinstance(tag, str):
                out[tag] = SensorLimits()
    return out


def clamp01(p: float) -> float:
    return 0.0 if p < 0 else 1.0 if p > 1 else p


def _mix(a: float | None, b: float | None, p: float) -> float | None:
    if a is not None and b is not None:
        return a + (b - a) * p
    return a if a is not None else b


def band_at(limits: SensorLimits, p: float) -> Range | None:
    """Допустимая полоса в момент p (0 - начало стадии, 1 - конец).

    * есть "during"        -> она действует всю стадию;
    * есть "pre" и "post"  -> полоса плавно переходит от pre (p=0) к post (p=1);
    * есть только одна     -> она и действует;
    * ничего нет           -> None."""
    p = clamp01(p)
    if limits.during is not None:
        return limits.during
    pre, post = limits.pre, limits.post
    if pre is not None and post is not None:
        lo, hi = _mix(pre.min, post.min, p), _mix(pre.max, post.max, p)
        return Range(lo, hi) if (lo is not None or hi is not None) else None
    return pre or post


# ---------------------------------------------------------------- датчик на стадии

@dataclass(frozen=True)
class SensorSpec:
    """Паспорт датчика из таблицы sensors."""
    tag: str
    parameter: str = ""
    unit: str = ""
    valid_min: float | None = None
    valid_max: float | None = None
    noise_sd: float | None = None
    val_start: float | None = None
    val_end: float | None = None
    sensor_id: int | None = None


@dataclass
class SensorPlan:
    spec: SensorSpec
    limits: SensorLimits
    start_mean: float | None = None   # среднее начальное значение по эталонным партиям
    end_mean: float | None = None     # среднее конечное значение по эталонным партиям

    @property
    def tag(self) -> str:
        return self.spec.tag

    def expected(self, p: float) -> float | None:
        """Эталонное значение в момент p: прямая от среднего начала к среднему концу."""
        if self.start_mean is None and self.end_mean is None:
            return None
        a = self.start_mean if self.start_mean is not None else self.end_mean
        b = self.end_mean if self.end_mean is not None else self.start_mean
        return a + (b - a) * clamp01(p)

    def band(self, p: float) -> Range | None:
        """Допустимая полоса. Если диапазонов в формуле нет - эталон +-допуск."""
        b = band_at(self.limits, p)
        if b is not None:
            return b
        e = self.expected(p)
        if e is None:
            return None
        half = max(4 * (self.spec.noise_sd or 0.0), 0.03 * abs(e), 1e-6)
        return Range(e - half, e + half)

    def target(self, p: float, band: Range | None = None) -> float | None:
        """Число, которое стоит показать оператору: эталон, зажатый в допустимую полосу."""
        band = band if band is not None else self.band(p)
        e = self.expected(p)
        if e is None and band is not None:
            e = band.center()
        if e is None:
            return None
        return band.clip(e) if band is not None else e


# ---------------------------------------------------------------- показания и вердикты

@dataclass(frozen=True)
class Reading:
    tag: str
    raw: str | None
    value: float | None
    progress: float = 0.0               # 0..1, положение внутри стадии
    unit: str | None = None
    quality: str | None = None
    source_row_id: int | None = None
    label_anomaly: bool | None = None   # разметка из файла (если есть) - для проверки качества
    label_type: str | None = None


@dataclass(frozen=True)
class Verdict:
    status: str                          # ok | low | high | bad_value | unit_error | sensor_fault | no_limits
    expected: float | None = None
    target: float | None = None
    band_min: float | None = None
    band_max: float | None = None
    message: str | None = None

    @property
    def is_alert(self) -> bool:
        return self.status not in ("ok", "no_limits")


def fmt(x: float) -> str:
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


_RAISE_WORDS = {"температура", "давление", "ph", "вакуум", "обороты", "скорость",
                "момент", "проводимость", "кислород", "вибрация", "перепад"}


def _accusative_first_word(parameter: str) -> str:
    words = parameter.strip().split()
    if not words:
        return "значение"
    w = words[0]
    if len(w) > 1 and w[0].isupper() and w[1:].islower():
        w = w[0].lower() + w[1:]
        if w.endswith("ая"):
            w = w[:-2] + "ую"
        elif w.endswith("а"):
            w = w[:-1] + "у"
        elif w.endswith("я"):
            w = w[:-1] + "ю"
    return " ".join([w] + words[1:])


def action_message(direction: str, spec: SensorSpec, target: float | None) -> str:
    """direction: 'up' - значение мало, надо поднять; 'down' - велико, надо опустить."""
    first = (spec.parameter.strip().split() or [""])[0].lower()
    if first in _RAISE_WORDS:
        verb = "повысить" if direction == "up" else "понизить"
    else:
        verb = "увеличить" if direction == "up" else "уменьшить"
    param = _accusative_first_word(spec.parameter)
    if target is None:
        return f"Нужно {verb} {param} на датчике {spec.tag}!"
    unit = "" if spec.unit.strip().lower() == param.strip().lower() else f" {spec.unit}".rstrip()
    return f"Нужно {verb} {param} до {fmt(target)}{unit} на датчике {spec.tag}!"


def _norm_unit(u: str | None) -> str:
    return (u or "").strip().casefold()


def evaluate(plan: SensorPlan, r: Reading) -> Verdict:
    spec = plan.spec
    p = clamp01(r.progress)
    band = plan.band(p)
    expected = plan.expected(p)
    bmin = band.min if band else None
    bmax = band.max if band else None

    def v(status: str, message: str | None = None, target: float | None = None) -> Verdict:
        return Verdict(status, expected, target, bmin, bmax, message)

    if r.value is None:
        got = r.raw if r.raw not in (None, "") else "пусто"
        return v("bad_value", f"Датчик {spec.tag}: нет корректного значения (получено «{got}») - проверьте датчик!")

    if r.unit and spec.unit and _norm_unit(r.unit) != _norm_unit(spec.unit):
        return v("unit_error", f"Датчик {spec.tag}: единица «{r.unit}» вместо «{spec.unit}» - проверьте настройки датчика!")

    lo, hi = spec.valid_min, spec.valid_max
    if (lo is not None and r.value < lo - EPS) or (hi is not None and r.value > hi + EPS):
        return v("sensor_fault",
                 f"Датчик {spec.tag}: показание {fmt(r.value)} {spec.unit} вне физических пределов датчика "
                 f"[{fmt(lo) if lo is not None else '-'}; {fmt(hi) if hi is not None else '-'}] - проверьте датчик!")

    if band is None:
        return v("no_limits")

    if bmin is not None and r.value < bmin - EPS:
        t = plan.target(p, band)
        return v("low", action_message("up", spec, t), t)
    if bmax is not None and r.value > bmax + EPS:
        t = plan.target(p, band)
        return v("high", action_message("down", spec, t), t)
    return v("ok", None, plan.target(p, band))
