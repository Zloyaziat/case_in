"""Работа с БД для симуляции (SQLAlchemy async)."""
from __future__ import annotations

from datetime import timedelta
from typing import Mapping

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import FormulaStep, Sensor
from .engine import SensorSpec, parse_step_sensors
from .models import ReferenceBatchValue as RB
from .models import SensorAlert, SensorReading, SimRun, SimStepRun
from .plan import StepRun, build_sensor_plans, resolve_duration
from .reference import generate_batches, ref_target
from .runner import TickItem


# ---------------------------------------------------------------- чтение

async def get_steps(db: AsyncSession, formula_id: int, only: list[int] | None = None) -> list[FormulaStep]:
    q = select(FormulaStep).where(FormulaStep.formula_id == formula_id).order_by(FormulaStep.step)
    if only:
        q = q.where(FormulaStep.step.in_(only))
    return list((await db.scalars(q)).all())


async def get_specs(db: AsyncSession, tags: set[str]) -> dict[str, SensorSpec]:
    if not tags:
        return {}
    rows = await db.scalars(select(Sensor).where(Sensor.tag.in_(tags)))
    return {
        s.tag: SensorSpec(tag=s.tag, parameter=s.parameter or "", unit=s.unit or "",
                          valid_min=s.valid_min, valid_max=s.valid_max, noise_sd=s.noise_sd,
                          val_start=s.val_start, val_end=s.val_end, sensor_id=s.id)
        for s in rows
    }


async def load_profiles(db: AsyncSession, step_ids: list[int]) -> dict[int, dict[str, tuple[float, float, int]]]:
    """{step_id: {tag: (среднее_начало, среднее_конец, сколько_партий)}} - по эталонным партиям."""
    if not step_ids:
        return {}
    q = (select(RB.formula_step_id, RB.tag, func.avg(RB.v_start), func.avg(RB.v_end), func.count())
         .where(RB.formula_step_id.in_(step_ids))
         .group_by(RB.formula_step_id, RB.tag))
    out: dict[int, dict[str, tuple[float, float, int]]] = {}
    for sid, tag, a, b, c in (await db.execute(q)).all():
        out.setdefault(sid, {})[tag] = (float(a), float(b), int(c))
    return out


def _targets_for_step(step: FormulaStep, specs: Mapping[str, SensorSpec]):
    targets = {}
    for tag, lim in parse_step_sensors(step.dict_PLC_id).items():
        t = ref_target(lim, specs.get(tag) or SensorSpec(tag=tag))
        if t is not None:
            targets[tag] = t
    return targets


# ---------------------------------------------------------------- эталонные партии

async def generate_reference(db: AsyncSession, steps: list[FormulaStep], specs: Mapping[str, SensorSpec],
                             n_batches: int = 30, seed: int | str = 0) -> dict[int, int]:
    """Пересоздаёт эталонные партии для стадий. Возвращает {номер_стадии: сколько строк записано}."""
    created: dict[int, int] = {}
    for st in steps:
        rows = generate_batches(_targets_for_step(st, specs), n_batches, seed, salt=f"{st.step}:{st.step_key}")
        await db.execute(delete(RB).where(RB.formula_step_id == st.id))
        db.add_all([RB(formula_step_id=st.id, batch_no=b, tag=tag, v_start=v0, v_end=v1)
                    for b, tag, v0, v1 in rows])
        created[st.step] = len(rows)
    await db.commit()
    return created


async def ensure_reference(db: AsyncSession, steps: list[FormulaStep], specs: Mapping[str, SensorSpec],
                           n_batches: int = 30, seed: int | str = 0) -> list[int]:
    """Генерирует эталон только для стадий, где его ещё нет. Возвращает номера этих стадий."""
    profiles = await load_profiles(db, [s.id for s in steps])
    missing = [s for s in steps
               if set(_targets_for_step(s, specs)) - set(profiles.get(s.id, {}))]
    if missing:
        await generate_reference(db, missing, specs, n_batches, seed)
    return [s.step for s in missing]


# ---------------------------------------------------------------- план прогона

def make_step_runs(steps: list[FormulaStep], specs: Mapping[str, SensorSpec],
                   profiles: Mapping[int, Mapping[str, tuple[float, float, int]]],
                   step_seconds: float | None, per_step: Mapping[int, float]) -> list[StepRun]:
    """Собирает StepRun. ValueError - если длительность стадии не определить."""
    out = []
    for st in steps:
        amount = st.amount_time.total_seconds() if st.amount_time else None
        dur, how = resolve_duration(st.step, amount, step_seconds, per_step)
        prof = {tag: (a, b) for tag, (a, b, _n) in profiles.get(st.id, {}).items()}
        out.append(StepRun(step=st.step, key=st.step_key, title=st.step_value, duration_s=dur,
                           sensors=build_sensor_plans(st.dict_PLC_id, specs, prof),
                           step_id=st.id, duration_source=how))
    return out


async def save_durations(db: AsyncSession, steps: list[FormulaStep], step_runs: list[StepRun]) -> None:
    """Записывает длительности из запроса в formula_steps.amount_time (как просил тимлид)."""
    by_no = {sr.step: sr for sr in step_runs}
    for st in steps:
        sr = by_no[st.step]
        if sr.duration_source.startswith("запрос"):
            st.amount_time = timedelta(seconds=sr.duration_s)
    await db.commit()


# ---------------------------------------------------------------- запись результатов

class DbSink:
    """Пишет шаги и показания в БД. На каждый тик - отдельная короткая транзакция."""

    def __init__(self, run_id: int, session_factory):
        self.run_id = run_id
        self.sf = session_factory
        self._step_row_id: int | None = None

    async def step_started(self, step: StepRun, sources: dict[str, str], n: int) -> None:
        async with self.sf() as db:
            row = SimStepRun(run_id=self.run_id, formula_step_id=step.step_id, step=step.step,
                             step_key=step.key, duration_seconds=step.duration_s, ticks=n,
                             sources=", ".join(f"{t}={s}" for t, s in sources.items()), status="running")
            db.add(row)
            await db.commit()
            self._step_row_id = row.id

    async def tick(self, step: StepRun, k: int, n: int, elapsed_s: float, items: list[TickItem]) -> None:
        if not items:
            return
        async with self.sf() as db:
            rows = []
            for it in items:
                v, r = it.verdict, it.reading
                rows.append(SensorReading(
                    run_id=self.run_id, step=step.step, elapsed_s=elapsed_s, progress=r.progress,
                    tag=it.plan.tag, sensor_id=it.plan.spec.sensor_id, value=r.value, raw_value=r.raw,
                    unit=r.unit or it.plan.spec.unit or None, quality=r.quality, source=it.source,
                    source_row_id=r.source_row_id, expected=v.expected, band_min=v.band_min,
                    band_max=v.band_max, status=v.status, label_anomaly=r.label_anomaly,
                    label_type=r.label_type))
            db.add_all(rows)
            await db.flush()                      # чтобы у показаний появились id
            for row, it in zip(rows, items):
                if it.verdict.is_alert:
                    db.add(SensorAlert(run_id=self.run_id, reading_id=row.id, step=step.step,
                                       tag=it.plan.tag, kind=it.verdict.status, value=it.reading.value,
                                       target=it.verdict.target, message=it.verdict.message or ""))
            await db.commit()

    async def step_finished(self, step: StepRun, completed: bool) -> None:
        if self._step_row_id is None:
            return
        async with self.sf() as db:
            await db.execute(update(SimStepRun).where(SimStepRun.id == self._step_row_id)
                             .values(status="done" if completed else "aborted", finished_at=func.now()))
            await db.commit()


async def finish_run(session_factory, run_id: int, status: str, note: str | None = None) -> None:
    async with session_factory() as db:
        await db.execute(update(SimRun).where(SimRun.id == run_id)
                         .values(status=status, finished_at=func.now(), note=note))
        await db.commit()
