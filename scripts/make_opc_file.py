"""Генерирует txt для эмулятора OPC по эталонным партиям формулы из sql/case_in.sql (БД не нужна).

    python scripts/make_opc_file.py                      # формула 15 -> data/opc_formula15.txt
    python scripts/make_opc_file.py --formula 15 --clean # без намеренных отклонений

Шаги идут друг за другом; длительность шага - последнее окно эталона. Значение датчика в окне =
среднее эталонных партий + шум датчика (sensors.noise_sd), каждые --interval секунд.
Намеренные отклонения (DEVIATIONS) нужны, чтобы увидеть рекомендации; плюс одна строка "ERR"."""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (шаг, датчик, правая граница окна, множитель) - для формулы 15
DEVIATIONS = [
    (1, "D-LAC-04", 6.0, 0.80),      # лактида меньше эталона -> "увеличить"
    (2, "CI-FT-01", 8.0, 1.45),      # расход выше эталона -> "уменьшить"
]


def copy_block(sql: str, table: str) -> tuple[list[str], list[list[str]]]:
    """Строки из блока COPY public.<table> (...) FROM stdin; ... \\."""
    head = f"COPY public.{table} ("
    start = sql.index(head)
    cols_end = sql.index(")", start)
    cols = [c.strip().strip('"') for c in sql[start + len(head):cols_end].split(",")]
    body_start = sql.index("\n", start) + 1
    body_end = sql.index("\n\\.", body_start)
    rows = [line.split("\t") for line in sql[body_start:body_end].splitlines() if line]
    return cols, rows


def interval_s(s: str) -> float:
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def num(x: str) -> float | None:
    """Значение из COPY-блока: \\N - NULL."""
    return None if x == "\\N" else float(x)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--formula", type=int, default=15)
    ap.add_argument("--sql", default=str(ROOT / "sql" / "case_in.sql"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--interval", type=float, default=0.5, help="период опроса датчика, с")
    ap.add_argument("--window", type=float, default=2.0, help="окно эталона, с")
    ap.add_argument("--seed", type=int, default=15)
    ap.add_argument("--clean", action="store_true", help="без намеренных отклонений и ERR")
    args = ap.parse_args()
    out = Path(args.out or ROOT / "data" / f"opc_formula{args.formula}.txt")
    sql = Path(args.sql).read_text(encoding="utf-8")

    cols, rows = copy_block(sql, "batch")
    c = {n: i for i, n in enumerate(cols)}
    refs = {r[c["id"]] for r in rows if r[c["formula_id"]] == str(args.formula) and r[c["is_reference"]] == "t"}
    if not refs:
        raise SystemExit(f"нет эталонных партий формулы {args.formula}")

    cols, rows = copy_block(sql, "sensors")
    c = {n: i for i, n in enumerate(cols)}
    noise = {r[c["tag"]]: num(r[c["noise_sd"]]) or 0.0 for r in rows}
    valid = {r[c["tag"]]: (num(r[c["valid_min"]]), num(r[c["valid_max"]])) for r in rows}

    cols, rows = copy_block(sql, "batch_step_window")
    c = {n: i for i, n in enumerate(cols)}
    acc: dict[int, dict[float, dict[str, list[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        if r[c["batch_id"]] in refs:
            for tag, v in json.loads(r[c["detectors"]]).items():
                acc[int(r[c["step"]])][interval_s(r[c["time"]])][tag].append(float(v))

    deviations = {} if args.clean else {(s, t, w): f for s, t, w, f in DEVIATIONS}
    rnd = random.Random(args.seed)
    t0 = datetime(2026, 10, 20, 10, 0, 0)
    lines = [f"# эмулятор OPC: формула {args.formula}, эталонные партии {sorted(refs, key=int)}",
             f"# start={t0.isoformat()}",
             "# время;датчик;значение"]
    offset = 0.0
    per_window = round(args.window / args.interval)
    for step in sorted(acc):
        windows = acc[step]
        for end in sorted(windows):
            for j in range(per_window):
                t = end - args.window + (j + 1) * args.interval
                for tag in sorted(windows[end]):
                    avg = statistics.fmean(windows[end][tag])
                    v = rnd.gauss(avg, noise.get(tag, 0.0) * 0.5) * deviations.get((step, tag, end), 1.0)
                    lo, hi = valid.get(tag, (None, None))                # датчик не покажет меньше физ. минимума
                    v = max(v, lo) if lo is not None else v
                    v = min(v, hi) if hi is not None else v
                    ts = t0 + timedelta(seconds=offset + t)
                    lines.append(f"{ts.isoformat(timespec='milliseconds').rstrip('0').rstrip('.')};{tag};{v:.4f}")
        offset += max(windows)
    if not args.clean:
        lines.insert(11, lines[10].rsplit(";", 1)[0] + ";ERR")     # датчик отдал мусор
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(1 for x in lines if not x.startswith("#"))
    print(f"{out}: {n} строк, {math.ceil(offset)} с, шаги {sorted(acc)}")


if __name__ == "__main__":
    main()
