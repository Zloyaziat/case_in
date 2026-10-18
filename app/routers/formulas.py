from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Formula, FormulaStep, Sensor

router = APIRouter(prefix="/api/formulas", tags=["formulas"])

PHASES = ("pre", "during", "post")


class Range(BaseModel):
    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def check(self):
        if self.min is None and self.max is None:
            raise ValueError("нужен min или max")
        if None not in (self.min, self.max) and self.min > self.max:
            raise ValueError("min > max")
        return self


class SensorLimits(BaseModel):
    """Допустимый диапазон датчика: до цикла / во время / после цикла."""
    pre: Range | None = None
    during: Range | None = None
    post: Range | None = None


class FormulaStepInput(BaseModel):
    step: int = Field(ge=1)
    step_key: str
    step_value: str                                  # уравнение или описание шага
    in_data: dict[str, float] = {}                   # {"C6H12O6": 1000}  граммовка веществ на входе
    out_data: dict[str, float] = {}                  # {"C3H6O3": 1000}   граммовка на выходе (теор.)
    dict_PLC_id: dict[str, SensorLimits] = {}        # {sensors.tag: {pre/during/post: {min,max}}}
    constant: dict[str, float] = {}                  # {"конверсия": 0.95, ...}
    amount_time: timedelta | None = None             # "PT30M", "PT24H" или секунды

    @model_validator(mode="after")
    def check(self):
        for k, v in self.in_data.items():
            if v <= 0:
                raise ValueError(f"in_data['{k}']: масса должна быть > 0")
        for k, v in self.out_data.items():
            if v < 0:
                raise ValueError(f"out_data['{k}']: масса не может быть < 0")
        for k, v in self.constant.items():
            if not 0 < v <= 1:
                raise ValueError(f"constant['{k}'] должна быть в (0, 1]")
        return self


class FormulaCreate(BaseModel):
    name: str
    version: int = Field(1, ge=1)
    steps: list[FormulaStepInput] = Field(min_length=1)


async def check_sensors(db: AsyncSession, steps: list[FormulaStepInput]):
    """Связь с БД: каждый ключ dict_PLC_id должен быть sensors.tag, диапазон - в физ. пределах датчика."""
    tags = {t for s in steps for t in s.dict_PLC_id}
    if not tags:
        return
    rows = (await db.execute(
        select(Sensor.tag, Sensor.valid_min, Sensor.valid_max).where(Sensor.tag.in_(tags))
    )).all()
    known = {t: (lo, hi) for t, lo, hi in rows}
    if missing := tags - set(known):
        raise HTTPException(422, {"error": "неизвестные датчики", "tags": sorted(missing)})
    problems = []
    for s in steps:
        for tag, limits in s.dict_PLC_id.items():
            lo, hi = known[tag]
            for ph in PHASES:
                r = getattr(limits, ph)
                if r is None:
                    continue
                if lo is not None and r.min is not None and r.min < lo:
                    problems.append(f"шаг {s.step}, {tag}/{ph}: min {r.min} < valid_min {lo}")
                if hi is not None and r.max is not None and r.max > hi:
                    problems.append(f"шаг {s.step}, {tag}/{ph}: max {r.max} > valid_max {hi}")
    if problems:
        raise HTTPException(422, {"error": "диапазон вне физических пределов датчика", "items": problems})


@router.post("")
async def new_chemistry_steps(data: FormulaCreate, db: AsyncSession = Depends(get_db)):
    nums = [s.step for s in data.steps]
    keys = [s.step_key for s in data.steps]
    if len(nums) != len(set(nums)):
        raise HTTPException(422, "Номера этапов должны быть уникальными")
    if len(keys) != len(set(keys)):
        raise HTTPException(422, "Ключи этапов должны быть уникальными")

    await check_sensors(db, data.steps)

    try:
        form = Formula(name=data.name, version=data.version)
        db.add(form)
        await db.flush()
        for item in sorted(data.steps, key=lambda s: s.step):
            db.add(FormulaStep(formula_id=form.id, **item.model_dump(exclude_none=True)))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Формула с таким названием и версией уже существует")
    except Exception:
        await db.rollback()
        raise

    return {"id": form.id, "name": form.name, "version": form.version,
            "steps_count": len(data.steps)}


@router.get("")
async def list_formulas(db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Formula).order_by(Formula.name, Formula.version))).all()
    return [{"id": f.id, "name": f.name, "version": f.version,
             "created_at": f.created_at.isoformat() if f.created_at else None} for f in rows]


@router.get("/{fid}")
async def get_formula(fid: int, db: AsyncSession = Depends(get_db)):
    """Формула со всеми шагами; датчики из dict_PLC_id раскрыты данными из таблицы sensors."""
    form = await db.get(Formula, fid)
    if not form:
        raise HTTPException(404, "формула не найдена")
    steps = (await db.scalars(
        select(FormulaStep).where(FormulaStep.formula_id == fid).order_by(FormulaStep.step)
    )).all()
    tags = {t for s in steps for t in (s.dict_PLC_id or {})}
    info = {}
    if tags:
        for sn in await db.scalars(select(Sensor).where(Sensor.tag.in_(tags))):
            info[sn.tag] = {"parameter": sn.parameter, "unit": sn.unit, "stage": sn.stage}
    return {
        "id": form.id, "name": form.name, "version": form.version,
        "steps": [{
            "step": s.step, "step_key": s.step_key, "step_value": s.step_value,
            "in_data": s.in_data, "out_data": s.out_data, "constant": s.constant,
            "amount_time_sec": s.amount_time.total_seconds() if s.amount_time else None,
            "sensors": {t: {"limits": lim, **info.get(t, {"parameter": "?"})}
                        for t, lim in (s.dict_PLC_id or {}).items()},
        } for s in steps],
    }
