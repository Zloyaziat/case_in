"""Эмулятор OPC-сервера: txt-файл, одна строка на показание (чистый Python).

Формат строки:  2026-10-20T10:00:00.5;temp_1;36.4
Файл "проигрывается" с момента старта партии: строка отдаётся, когда с начала проигрывания прошло
столько же секунд, сколько между ней и началом файла ('# start=...' или первая строка)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

from ..monitoring.source import parse_value


@dataclass(frozen=True)
class OpcLine:
    offset_s: float        # секунды от первой строки файла
    tag: str
    raw: str
    value: float | None    # None, если пришёл мусор ("ERR", "")


def parse_ts(s: str) -> datetime:
    """'2026-10-20T10:00:00.5' -> datetime (дробная часть любой длины до микросекунд)."""
    s = s.strip()
    head, dot, frac = s.partition(".")
    if dot:
        s = f"{head}.{(frac + '000000')[:6]}"
    return datetime.fromisoformat(s)


def parse_lines(text: str) -> list[OpcLine]:
    """Пустые строки и строки с '#' в начале пропускаются; битые строки - ValueError с номером строки.

    '# start=2026-10-20T10:00:00' задаёт момент старта партии (иначе им считается первая строка)."""
    rows: list[tuple[datetime, str, str]] = []
    start: datetime | None = None
    for no, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if line.startswith("#"):
            key, eq, val = line[1:].strip().partition("=")
            if eq and key.strip() == "start":
                try:
                    start = parse_ts(val)
                except ValueError:
                    raise ValueError(f"строка {no}: не разобрать время {val.strip()!r}") from None
            continue
        if not line:
            continue
        parts = line.split(";")
        if len(parts) != 3 or not parts[1].strip():
            raise ValueError(f"строка {no}: ожидается 'время;тег;значение', получено {line!r}")
        try:
            ts = parse_ts(parts[0])
        except ValueError:
            raise ValueError(f"строка {no}: не разобрать время {parts[0]!r}") from None
        rows.append((ts, parts[1].strip(), parts[2].strip()))
    if not rows:
        return []
    t0 = start or rows[0][0]
    out = [OpcLine((ts - t0).total_seconds(), tag, raw, parse_value(raw)) for ts, tag, raw in rows]
    out.sort(key=lambda r: r.offset_s)          # sort стабилен - порядок строк с одним временем сохраняется
    return out


def load_file(path: str | os.PathLike) -> list[OpcLine]:
    with open(path, encoding="utf-8-sig") as f:
        return parse_lines(f.read())


class OpcEmulator:
    """Отдаёт строки файла по мере наступления их времени: poll(t) - всё, что "пришло" к моменту t."""

    def __init__(self, lines: list[OpcLine]):
        self.lines = lines
        self.pos = 0

    @classmethod
    def from_path(cls, path) -> "OpcEmulator":
        return cls(load_file(path))

    def poll(self, t: float) -> list[OpcLine]:
        start = self.pos
        while self.pos < len(self.lines) and self.lines[self.pos].offset_s <= t:
            self.pos += 1
        return self.lines[start:self.pos]

    @property
    def exhausted(self) -> bool:
        return self.pos >= len(self.lines)

    @property
    def duration_s(self) -> float:
        return self.lines[-1].offset_s if self.lines else 0.0
