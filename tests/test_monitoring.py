"""Тесты ядра симуляции. Запуск из корня репозитория:  python -m unittest discover -s tests -v
БД и FastAPI для них не нужны."""
import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.monitoring.engine import (Range, Reading, SensorLimits, SensorPlan, SensorSpec, action_message,  # noqa: E402
                                   band_at, evaluate, parse_step_sensors)
from app.monitoring.plan import StepRun, build_sensor_plans, n_ticks, resolve_duration  # noqa: E402
from app.monitoring.reference import generate_batches, profile_from_rows, ref_target  # noqa: E402
from app.monitoring.runner import run_plan  # noqa: E402
from app.monitoring.source import FileSource, SyntheticSource, load_csv, parse_value, pick_sources  # noqa: E402

CSV = ROOT / "data" / "sensor_data_5000.csv"

SPECS = {
    "F-TT-01": SensorSpec("F-TT-01", "Температура", "°C", 0, 60, 0.15, 37, 37),
    "F-pH-02": SensorSpec("F-pH-02", "pH", "pH", 0, 14, 0.05, 5.8, 5.7),
    "CI-TT-02": SensorSpec("CI-TT-02", "Температура", "°C", 0, 80, 0.4, 30, 40),
}
# как в формуле "Молочная кислота" (id=10) у тимлида
STEP1 = {"F-TT-01": {"pre": {"min": 15, "max": 30}, "post": {"min": 35, "max": 40}}}
STEP2 = {"F-TT-01": {"pre": {"min": 35, "max": 40}, "post": {"min": 30, "max": 42}, "during": {"min": 35, "max": 40}},
         "F-pH-02": {"pre": {"min": 5.5, "max": 6.5}, "post": {"min": 4.0, "max": 5.5}, "during": {"min": 4.5, "max": 6.5}}}
STEP3 = {"CI-TT-02": {"pre": {"min": 20, "max": 40}, "post": {"min": 15, "max": 40}}}


def make_steps(seconds=14.0):
    steps = []
    for i, (key, d) in enumerate([("heat_fermenter", STEP1), ("fermentation", STEP2), ("isolation", STEP3)], 1):
        raw = {t: ref_target(l, SPECS[t]) for t, l in parse_step_sensors(d).items()}
        rows = generate_batches({t: r for t, r in raw.items() if r}, 30, seed=1, salt=f"{i}:{key}")
        prof = {t: (a, b) for t, (a, b, _) in profile_from_rows(rows).items()}
        steps.append(StepRun(i, key, key, seconds, build_sensor_plans(d, SPECS, prof)))
    return steps


class Limits(unittest.TestCase):
    def test_parse_new_and_old_format(self):
        self.assertEqual(set(parse_step_sensors(STEP2)), {"F-TT-01", "F-pH-02"})
        old = parse_step_sensors(["F-TT-01", "F-pH-02"])
        self.assertTrue(old["F-TT-01"].is_empty())
        self.assertEqual(parse_step_sensors(None), {})
        self.assertEqual(parse_step_sensors({"A": {"pre": {"min": 5, "max": 1}}})["A"].pre, None)  # min > max

    def test_band_interpolates_pre_to_post(self):
        lim = parse_step_sensors(STEP1)["F-TT-01"]
        b0, b5, b1 = band_at(lim, 0), band_at(lim, 0.5), band_at(lim, 1)
        self.assertEqual((b0.min, b0.max), (15, 30))
        self.assertEqual((b5.min, b5.max), (25, 35))
        self.assertEqual((b1.min, b1.max), (35, 40))

    def test_during_wins(self):
        lim = parse_step_sensors(STEP2)["F-TT-01"]
        self.assertEqual(band_at(lim, 0.9), Range(35, 40))

    def test_only_one_phase(self):
        self.assertEqual(band_at(SensorLimits(post=Range(1, 2)), 0.3), Range(1, 2))
        self.assertIsNone(band_at(SensorLimits(), 0.3))


class Evaluate(unittest.TestCase):
    def plan(self, step=STEP2, tag="F-TT-01", m=(37.5, 37.5)):
        return SensorPlan(SPECS[tag], parse_step_sensors(step)[tag], *m)

    def test_ok(self):
        v = evaluate(self.plan(), Reading("F-TT-01", "37.1", 37.1, 0.5))
        self.assertEqual(v.status, "ok")
        self.assertFalse(v.is_alert)

    def test_low_gives_raise_message_with_target(self):
        v = evaluate(self.plan(), Reading("F-TT-01", "31.22", 31.22, 0.01))
        self.assertEqual(v.status, "low")
        self.assertEqual(v.target, 37.5)
        self.assertEqual(v.message, "Нужно повысить температуру до 37.5 °C на датчике F-TT-01!")

    def test_high_gives_lower_message(self):
        v = evaluate(self.plan(), Reading("F-TT-01", "44", 44.0, 0.5))
        self.assertEqual(v.message, "Нужно понизить температуру до 37.5 °C на датчике F-TT-01!")

    def test_target_always_inside_band(self):
        p = self.plan(m=(100.0, 100.0))               # эталон "сломан" и вне полосы
        v = evaluate(p, Reading("F-TT-01", "20", 20.0, 0.5))
        self.assertEqual(v.target, 40.0)

    def test_bad_value_and_sensor_fault(self):
        self.assertEqual(evaluate(self.plan(), Reading("F-TT-01", "ERR", None, 0.5)).status, "bad_value")
        v = evaluate(self.plan(), Reading("F-TT-01", "9999.9", 9999.9, 0.5))
        self.assertEqual(v.status, "sensor_fault")
        self.assertIsNone(v.target)

    def test_unit_error(self):
        self.assertEqual(evaluate(self.plan(), Reading("F-TT-01", "37", 37.0, 0.5, unit="K")).status, "unit_error")

    def test_no_ranges_uses_reference_tolerance(self):
        p = SensorPlan(SPECS["F-TT-01"], SensorLimits(), 37.0, 37.0)
        self.assertEqual(evaluate(p, Reading("F-TT-01", "37.2", 37.2, 0.5)).status, "ok")
        self.assertEqual(evaluate(p, Reading("F-TT-01", "41", 41.0, 0.5)).status, "high")

    def test_no_ranges_no_reference(self):
        p = SensorPlan(SensorSpec("X", "Что-то", "u"), SensorLimits())
        self.assertEqual(evaluate(p, Reading("X", "5", 5.0, 0.5)).status, "no_limits")

    def test_messages_grammar(self):
        s = lambda par, un="": SensorSpec("T", par, un)
        self.assertEqual(action_message("up", s("Давление", "бар"), 1.1), "Нужно повысить давление до 1.1 бар на датчике T!")
        self.assertEqual(action_message("up", s("pH", "pH"), 5.8), "Нужно повысить pH до 5.8 на датчике T!")
        self.assertEqual(action_message("down", s("Масса глюкозы", "кг"), 276), "Нужно уменьшить массу глюкозы до 276 кг на датчике T!")
        self.assertEqual(action_message("up", s("Вода", "м³"), 2.3), "Нужно увеличить воду до 2.3 м³ на датчике T!")
        self.assertEqual(action_message("up", s("Температура плавления", "°C"), 96), "Нужно повысить температуру плавления до 96 °C на датчике T!")


class Reference(unittest.TestCase):
    def test_30_batches_mean_close_to_target_and_inside_band(self):
        lim = parse_step_sensors(STEP1)["F-TT-01"]
        t = ref_target(lim, SPECS["F-TT-01"])
        self.assertEqual((t.start, t.end), (22.5, 37.5))
        rows = generate_batches({"F-TT-01": t}, 30, seed=7)
        self.assertEqual(len(rows), 30)
        a, b, n = profile_from_rows(rows)["F-TT-01"]
        self.assertEqual(n, 30)
        self.assertAlmostEqual(a, 22.5, delta=1.5)
        self.assertAlmostEqual(b, 37.5, delta=1.0)
        self.assertTrue(all(15 <= r[2] <= 30 and 35 <= r[3] <= 40 for r in rows))

    def test_deterministic_per_seed(self):
        t = ref_target(parse_step_sensors(STEP1)["F-TT-01"], SPECS["F-TT-01"])
        self.assertEqual(generate_batches({"F-TT-01": t}, 5, seed=3), generate_batches({"F-TT-01": t}, 5, seed=3))
        self.assertNotEqual(generate_batches({"F-TT-01": t}, 5, seed=3), generate_batches({"F-TT-01": t}, 5, seed=4))

    def test_fallback_to_sensor_table_without_ranges(self):
        t = ref_target(SensorLimits(), SPECS["CI-TT-02"])
        self.assertEqual((t.start, t.end), (30, 40))
        self.assertIsNone(ref_target(SensorLimits(), SensorSpec("X")))


class Durations(unittest.TestCase):
    def test_priority(self):
        self.assertEqual(resolve_duration(1, 2700, 14, {1: 5})[0], 5)
        self.assertEqual(resolve_duration(1, 2700, 14, {})[0], 14)
        self.assertEqual(resolve_duration(1, 60, None, {})[0], 60)

    def test_long_db_duration_needs_override(self):
        with self.assertRaises(ValueError):
            resolve_duration(2, 86400)             # "1 day"
        with self.assertRaises(ValueError):
            resolve_duration(2, None)

    def test_ticks(self):
        self.assertEqual(n_ticks(14, 0.5), 28)
        self.assertEqual(n_ticks(0.1, 0.5), 1)


@unittest.skipUnless(CSV.exists(), "нет data/sensor_data_5000.csv")
class Files(unittest.TestCase):
    def test_parse(self):
        self.assertIsNone(parse_value("ERR"))
        self.assertIsNone(parse_value("-----"))
        self.assertIsNone(parse_value(""))
        self.assertEqual(parse_value("37,5"), 37.5)

    def test_load(self):
        t = load_csv(CSV)
        self.assertEqual(len(t), 57)
        self.assertEqual(sum(len(v) for v in t.values()), 5000)
        self.assertTrue(all(0 <= r.progress <= 1 for v in t.values() for r in v))

    def test_every_row_read_exactly_once(self):
        fs = FileSource.from_path(CSV)
        for n in (28, 88, 200):
            got = [r.source_row_id for k in range(n) for r in fs.slice("F-TT-01", k, n)]
            self.assertEqual(got, [r.source_row_id for r in fs.rows("F-TT-01")], n)

    def test_one_row_per_tick_when_enough_ticks(self):
        fs = FileSource.from_path(CSV)
        n = len(fs.rows("F-TT-01"))
        self.assertTrue(all(len(fs.slice("F-TT-01", k, n)) == 1 for k in range(n)))

    def test_auto_source_choice_for_lactic_formula(self):
        fs = FileSource.from_path(CSV)
        steps = make_steps()
        self.assertEqual(pick_sources(steps[0].sensors, fs, "auto"), {"F-TT-01": "synthetic"})  # файл - уже ферментация
        self.assertEqual(pick_sources(steps[1].sensors, fs, "auto"), {"F-TT-01": "file", "F-pH-02": "file"})
        self.assertEqual(pick_sources(steps[2].sensors, fs, "auto"), {"CI-TT-02": "file"})
        self.assertEqual(pick_sources(steps[1].sensors, fs, "synthetic"), {"F-TT-01": "synthetic", "F-pH-02": "synthetic"})
        self.assertEqual(pick_sources(steps[1].sensors, None, "file"), {"F-TT-01": "synthetic", "F-pH-02": "synthetic"})

    def test_file_labels_are_detected(self):
        """Сигналы должны находить большинство размеченных в файле аномалий для датчиков стадии 2."""
        fs = FileSource.from_path(CSV)
        plans = {p.tag: p for p in make_steps()[1].sensors}
        hit = miss = false_alarm = 0
        for tag, p in plans.items():
            for r in fs.rows(tag):
                v = evaluate(p, r)
                if r.label_anomaly:
                    hit += v.is_alert
                    miss += not v.is_alert
                elif v.is_alert:
                    false_alarm += 1
        print(f"\n   найдено {hit}, пропущено {miss}, ложных тревог {false_alarm}")
        self.assertGreater(hit, 0)


class FakeSink:
    def __init__(self):
        self.started, self.ticks, self.finished = [], [], []

    async def step_started(self, step, sources, n):
        self.started.append((step.step, dict(sources), n))

    async def tick(self, step, k, n, elapsed, items):
        self.ticks.append((step.step, k, elapsed, list(items)))

    async def step_finished(self, step, completed):
        self.finished.append((step.step, completed))


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    async def sleep(self, d):
        self.t += d


class Runner(unittest.TestCase):
    def run_it(self, **kw):
        clock, sink, events = Clock(), FakeSink(), []
        fs = FileSource.from_path(CSV) if CSV.exists() else None
        summary = asyncio.run(run_plan(make_steps(), sink=sink, tick_seconds=0.5, file_source=fs,
                                       sleep=clock.sleep, clock=clock.now, emit=events.append, seed=5, **kw))
        return summary, sink, events, clock

    def test_timer_and_ticks(self):
        summary, sink, events, clock = self.run_it()
        self.assertEqual([s[2] for s in sink.started], [28, 28, 28])
        self.assertAlmostEqual(clock.t, 3 * 14.0, places=6)                 # 3 стадии по 14 с
        self.assertEqual([f for f in sink.finished], [(1, True), (2, True), (3, True)])
        elapsed = [t[2] for t in sink.ticks if t[0] == 1]
        self.assertEqual((elapsed[0], elapsed[-1]), (0.5, 14.0))

    def test_stage_two_reads_whole_file_and_alerts(self):
        summary, sink, events, _ = self.run_it()
        fs = FileSource.from_path(CSV)
        read = [it.reading.source_row_id for t in sink.ticks if t[0] == 2 for it in t[3]]
        want = [r.source_row_id for tag in ("F-TT-01", "F-pH-02") for r in fs.rows(tag)]
        self.assertEqual(sorted(read), sorted(want))
        alerts = [e for e in events if e["type"] == "alert" and e["step"] == 2]
        self.assertTrue(alerts)
        self.assertTrue(all(e["message"] for e in alerts))
        self.assertEqual(summary["readings"], sum(len(t[3]) for t in sink.ticks))

    def test_only_active_stage_sensors_are_read(self):
        _, sink, _, _ = self.run_it()
        tags = {s: {it.plan.tag for t in sink.ticks if t[0] == s for it in t[3]} for s in (1, 2, 3)}
        self.assertEqual(tags, {1: {"F-TT-01"}, 2: {"F-TT-01", "F-pH-02"}, 3: {"CI-TT-02"}})

    def test_synthetic_faults(self):
        _, sink, events, _ = self.run_it(source_mode="synthetic", fault_rate=0.5)
        self.assertTrue([e for e in events if e["type"] == "alert"])
        _, sink2, events2, _ = self.run_it(source_mode="synthetic", fault_rate=0.0)
        self.assertEqual([e for e in events2 if e["type"] == "alert"], [])      # без сбоев - тихо

    def test_cancel_marks_step_aborted(self):
        async def go():
            clock, sink = Clock(), FakeSink()

            async def slow_sleep(d):
                await asyncio.sleep(0.01)

            task = asyncio.create_task(run_plan(make_steps(), sink=sink, tick_seconds=0.5,
                                                sleep=slow_sleep, clock=clock.now, source_mode="synthetic"))
            await asyncio.sleep(0.05)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            return sink
        sink = asyncio.run(go())
        self.assertEqual(sink.finished, [(1, False)])


class Synthetic(unittest.TestCase):
    def test_values_follow_reference(self):
        p = make_steps()[0].sensors[0]
        s = SyntheticSource(seed=1, fault_rate=0.0)
        vals = [s.reading(p, k, 28).value for k in range(28)]
        self.assertLess(vals[0], vals[-1])             # нагрев растёт
        self.assertTrue(all(evaluate(p, s.reading(p, k, 28)).status == "ok" for k in range(28)))


if __name__ == "__main__":
    unittest.main()
