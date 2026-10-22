"""Чтение из БД того, что нужно для запуска партии: шаги формулы, датчики, эталонные партии."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import FormulaStep
from ..monitoring.engine import SensorSpec, parse_step_sensors
from ..monitoring.repo import get_specs
from .models import Batch, BatchStepWindow
from .process import StepDef
from .reference import REF_LIMIT, RefBatch, RefIndex, pick_references

REF_POOL = 100        # из скольких последних эталонных партий выбираем ближайшие по v_in


async def load_steps(db: AsyncSession, formula_id: int) -> list[StepDef]:
    rows = (await db.scalars(select(FormulaStep).where(FormulaStep.formula_id == formula_id)
                             .order_by(FormulaStep.step))).all()
    return [StepDef(step=r.step, tags=frozenset(parse_step_sensors(r.dict_PLC_id)),
                    planned_s=r.amount_time.total_seconds() if r.amount_time else None)
            for r in rows]


async def load_specs(db: AsyncSession, steps: list[StepDef]) -> dict[str, SensorSpec]:
    return await get_specs(db, {t for s in steps for t in s.tags})


async def load_references(db: AsyncSession, batch: Batch, min_quality: float | None = None,
                          limit: int = REF_LIMIT) -> RefIndex:
    """Эталонные партии той же формулы (завершённые, is_reference) -> окна их шагов."""
    q = (select(Batch.id, Batch.v_in, Batch.started_at)
         .where(Batch.formula_id == batch.formula_id, Batch.is_reference.is_(True),
                Batch.status == "finished", Batch.id != batch.id)
         .order_by(Batch.started_at.desc().nulls_last()).limit(REF_POOL))
    if min_quality is not None:
        q = q.where(Batch.quality >= min_quality)
    cands = [RefBatch(i, v, s) for i, v, s in (await db.execute(q)).all()]
    chosen = pick_references(cands, batch.v_in, limit)

    index = RefIndex()
    index.batch_ids = [b.id for b in chosen]
    if chosen:
        rows = await db.execute(select(BatchStepWindow.step, BatchStepWindow.time, BatchStepWindow.detectors)
                                .where(BatchStepWindow.batch_id.in_(index.batch_ids)))
        for step, t, det in rows.all():
            index.add(step, t.total_seconds(), det or {})
    return index
