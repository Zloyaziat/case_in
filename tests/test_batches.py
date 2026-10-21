"""Тесты ядра партий (ТЗ «ядро MVP»). Запуск из корня репозитория:  python -m unittest discover -s tests -v
БД и FastAPI не нужны: эталонные партии берутся прямо из sql/case_in.sql."""
import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.batches.opc import OpcEmulator, OpcLine, load_file, parse_lines, parse_ts  # noqa: E402
from app.batches.process import (BatchProcess, ProcessDone, StepDef, StepEnded, StepStarted,  # noqa: E402
                                 WindowClosed)
from app.batches.reference import RefBatch, RefIndex, compare, pick_references, v_in_distance  # noqa: E402
from make_opc_file import copy_block, interval_s  # noqa: E402

SQL = ROOT / "sql" / "case_in.sql"
OPC = ROOT / "data" / "opc_formula15.txt"


def line(t, tag, v):
    return OpcLine(t, tag, str(v), v)


def kinds(events):
    return [type(e).__name__ for e in events]


class OpcTest(unittest.TestCase):
    def test_parse_ts_fraction(self):
        self.assertEqual(parse_ts("2026-10-20T10:00:00.5"), datetime(2026, 10, 20, 10, 0, 0, 500000))
        self.assertEqual(parse_ts("2026-10-20T10:00:01"), datetime(2026, 10, 20, 10, 0, 1))

    def test_offsets_from_start_header(self):
        rows = parse_lines("# start=2026-10-20T10:00:00\n"
                           "2026-10-20T10:00:00.5;temp_1;36.4\n\n"
                           "2026-10-20T10:00:01;temp_1;ERR\n")
        self.assertEqual([(r.offset_s, r.tag, r.value) for r in rows],
                         [(0.5, "temp_1", 36.4), (1.0, "temp_1", None)])

    def test_offsets_from_first_line_without_header(self):
        rows = parse_lines("2026-10-20T10:00:00.5;t;1\n2026-10-20T10:00:02;t;2\n")
        self.assertEqual([r.offset_s for r in rows], [0.0, 1.5])

    def test_bad_line(self):
        with self.assertRaisesRegex(ValueError, "строка 2"):
            parse_lines("2026-10-20T10:00:00;t;1\nмусор\n")

    def test_poll_returns_each_line_once(self):
        emu = OpcEmulator([line(0.5, "a", 1), line(1.0, "a", 2), line(1.5, "a", 3)])
        self.assertEqual(len(emu.poll(0.4)), 0)
        self.assertEqual(len(emu.poll(1.0)), 2)
        self.assertEqual(len(emu.poll(1.0)), 0)
        self.assertEqual(len(emu.poll(9)), 1)
        self.assertTrue(emu.exhausted)


class ProcessTest(unittest.TestCase):
    def setUp(self):
        self.steps = [StepDef(1, frozenset({"a"}), 4.0), StepDef(2, frozenset({"b"}), 4.0)]

    def test_windows_of_four_samples(self):
        p = BatchProcess(self.steps, window_s=2.0)
        self.assertEqual(kinds(p.start()), ["StepStarted"])
        ev = p.advance(2.0, [line(0.5, "a", 1), line(1.0, "a", 2), line(1.5, "a", 3), line(2.0, "a", 4)])
        self.assertEqual(ev, [])                                     # окно (0; 2] ещё открыто
        ev = p.advance(2.1)
        self.assertEqual(ev, [WindowClosed(1, 2.0, {"a": 2.5}, {"a": 4})])

    def test_step_timer_and_time_from_step_start(self):
        p = BatchProcess(self.steps, window_s=2.0)
        p.start()
        lines = [line(t / 2, "a", 10) for t in range(1, 9)] + [line(4 + t / 2, "b", 20) for t in range(1, 9)]
        ev = p.advance(9.0, lines)
        self.assertEqual(kinds(ev), ["WindowClosed", "WindowClosed", "StepEnded", "StepStarted",
                                     "WindowClosed", "WindowClosed", "StepEnded", "ProcessDone"])
        wins = [e for e in ev if isinstance(e, WindowClosed)]
        self.assertEqual([(w.step, w.end_s) for w in wins], [(1, 2.0), (1, 4.0), (2, 2.0), (2, 4.0)])
        self.assertEqual(ev[2], StepEnded(1, 4.0, "timer"))
        self.assertEqual(ev[3], StepStarted(2, 4.0))
        self.assertTrue(p.done)

    def test_other_tags_and_garbage_are_not_averaged(self):
        p = BatchProcess(self.steps, window_s=2.0, limits={"a": (0, 100)})
        p.start()
        ev = p.advance(2.5, [line(0.5, "a", 10), line(0.6, "b", 99), OpcLine(1.0, "a", "ERR", None),
                             line(1.5, "a", 500), line(2.0, "a", 20)])
        self.assertEqual(ev[0].values, {"a": 15.0})
        c = p.counters
        self.assertEqual((c.accepted, c.ignored, c.bad_value, c.out_of_range), (2, 1, 1, 1))

    def test_operator_next_step_cuts_window(self):
        p = BatchProcess([StepDef(1, frozenset({"a"}), None), StepDef(2, frozenset({"a"}), None)])
        p.start()
        p.advance(1.2, [line(0.5, "a", 1), line(1.0, "a", 3)])
        ev = p.next_step(1.2)
        self.assertEqual(ev, [WindowClosed(1, 1.2, {"a": 2.0}, {"a": 2}), StepEnded(1, 1.2, "operator"),
                              StepStarted(2, 1.2)])
        p.advance(2.0, [line(1.7, "a", 7)])                          # 0.5 с от начала 2-го шага
        self.assertEqual(p.stop(3.5, "finish"),
                         [WindowClosed(2, 2.0, {"a": 7.0}, {"a": 1}), StepEnded(2, 3.5, "finish"), ProcessDone(3.5)])

    def test_step_without_duration_waits_for_operator(self):
        p = BatchProcess([StepDef(1, frozenset({"a"}), None)])
        p.start()
        p.advance(1000.0)
        self.assertEqual(p.current.step, 1)


class ReferenceTest(unittest.TestCase):
    def test_v_in_distance(self):
        self.assertEqual(v_in_distance({"CaO": 60}, {"CaO": 60}), 0)
        self.assertAlmostEqual(v_in_distance({"CaO": 60}, {"CaO": 50}), 10 / 60)
        self.assertEqual(v_in_distance({"CaO": 60}, {"H2O": 60}), 1)

    def test_pick_closest_then_newest(self):
        d = datetime(2026, 10, 1)
        cands = [RefBatch(1, {"x": 100}, d), RefBatch(2, {"x": 70}, d + timedelta(days=5)),
                 RefBatch(3, {"x": 100}, d + timedelta(days=1)), RefBatch(4, {"x": 101}, d)]
        self.assertEqual([b.id for b in pick_references(cands, {"x": 100}, 3)], [3, 1, 4])

    def test_threshold_is_max_of_k_std_and_tolerance(self):
        refs = {"t": [10.0, 10.2, 9.8, 10.0]}                       # std ~0.163, 3*std ~0.49
        self.assertEqual(compare({"t": 10.4}, refs, {}, 3.0), [])
        dev, = compare({"t": 9.0}, refs, {}, 3.0)
        self.assertEqual((dev.direction, dev.ref_avg, dev.delta), ("up", 10.0, -1.0))
        self.assertEqual(compare({"t": 9.0}, refs, {"t": 2.0}, 3.0), [])   # допуск датчика шире
        self.assertEqual(compare({"t": 99.0}, {}, {}, 3.0), [])             # эталона на это время нет


def dump_references(formula_id=15):
    """RefIndex из COPY-блоков sql/case_in.sql и noise_sd датчиков."""
    sql = SQL.read_text(encoding="utf-8")
    cols, rows = copy_block(sql, "batch")
    c = {n: i for i, n in enumerate(cols)}
    refs = {r[c["id"]] for r in rows if r[c["formula_id"]] == str(formula_id) and r[c["is_reference"]] == "t"}
    cols, rows = copy_block(sql, "batch_step_window")
    c = {n: i for i, n in enumerate(cols)}
    index = RefIndex()
    for r in rows:
        if r[c["batch_id"]] in refs:
            index.add(int(r[c["step"]]), interval_s(r[c["time"]]), json.loads(r[c["detectors"]]))
    cols, rows = copy_block(sql, "sensors")
    c = {n: i for i, n in enumerate(cols)}
    noise = {r[c["tag"]]: float(r[c["noise_sd"]]) for r in rows if r[c["noise_sd"]] != "\\N"}
    return index, noise


@unittest.skipUnless(SQL.exists() and OPC.exists(), "нет sql/case_in.sql или data/opc_formula15.txt")
class Formula15EndToEnd(unittest.TestCase):
    """Файл эмулятора формулы 15 через ядро: окна совпадают с эталоном, кроме намеренных отклонений."""

    def test_run(self):
        index, noise = dump_references()
        steps = [StepDef(1, frozenset({"D-LAC-04", "M-GLU-WT", "P-H2O-03", "A-GYPS-05"}), 10.0),
                 StepDef(2, frozenset({"C-FT-03", "CI-FT-01", "M-H2O-FT"}), 10.0),
                 StepDef(3, frozenset({"F-PT-04", "M-STER-PT"}), 10.0)]
        p = BatchProcess(steps, window_s=2.0)
        emu = OpcEmulator(load_file(OPC))
        events = p.start()
        t = 0.0
        while not p.done:                                         # тики по 0.1 с, как в BatchSession
            t = round(t + 0.1, 6)
            events += p.advance(t, emu.poll(t))

        wins = [e for e in events if isinstance(e, WindowClosed)]
        self.assertEqual([(w.step, w.end_s) for w in wins],
                         [(s, float(e)) for s in (1, 2, 3) for e in (2, 4, 6, 8, 10)])
        self.assertTrue(all(sum(w.counts.values()) == 4 * len(w.values) for w in wins))
        self.assertEqual(p.counters.bad_value, 1)                 # строка ERR
        self.assertEqual(p.counters.ignored, 0)

        alerts = [(w.step, w.end_s, d.tag, d.direction)
                  for w in wins for d in compare(w.values, index.at(w.step, w.end_s), noise)]
        self.assertEqual(alerts, [(1, 6.0, "D-LAC-04", "up"), (2, 8.0, "CI-FT-01", "down")])


if __name__ == "__main__":
    unittest.main()
