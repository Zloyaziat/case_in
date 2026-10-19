import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..calc import run_formula
from ..database import get_db
from ..models import Formula, FormulaStep, Sensor

router = APIRouter(prefix="/api/formulas", tags=["formulas"])

PHASES = ("pre", "during", "post")
KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


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
    step_key: str                                    # формула: "CO + 2H2 -> CH3OH"
    step_value: str                                  # результат формулы: "CH3OH"
    in_data: dict[str, float] = {}                   # кг до реакции: {"H2": 4.0, "CO": 28.0}
    out_data: dict[str, float] = {}                  # кг после; ключи задаёт пользователь: {"CH3OH": 27.2}
    dict_PLC_id: dict[str, SensorLimits] = {}        # {sensors.tag: {pre/during/post: {min,max}}}
    constant: dict[str, float] = {}                  # {"density": 0.79, "strength": 0.9} - множители к теор. массе
    amount_time: float | None = Field(None, gt=0)    # длительность процесса, минуты

    @model_validator(mode="after")
    def check(self):
        for k, v in self.in_data.items():
            if v <= 0:
                raise ValueError(f"in_data['{k}']: масса (кг) должна быть > 0")
        for k, v in self.out_data.items():
            if v < 0:
                raise ValueError(f"out_data['{k}']: масса (кг) не может быть < 0")
        for k, v in self.constant.items():
            if not KEY_RE.match(k):
                raise ValueError(f"constant['{k}']: ключ латиницей (буквы, цифры, _), например density")
            if v <= 0:
                raise ValueError(f"constant['{k}'] должна быть > 0")
        return self


class CalcIn(BaseModel):
    inputs: dict[str, float] | None = None       # подмена масс реагентов 1-го шага, кг
    constants: dict[str, float] | None = None    # подмена констант по имени (во всех шагах)
    spread_pct: float = Field(0, ge=0, le=50)    # >0: диапазон итоговой массы при +-N% к константам
    tolerance_pct: float = Field(10, gt=0, le=100)


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
            payload = item.model_dump(exclude_none=True)
            if "amount_time" in payload:
                payload["amount_time"] = timedelta(minutes=payload["amount_time"])
            db.add(FormulaStep(formula_id=form.id, **payload))
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
            info[sn.tag] = {"parameter": sn.parameter, "unit": sn.unit}
    return {
        "id": form.id, "name": form.name, "version": form.version,
        "steps": [{
            "step": s.step, "step_key": s.step_key, "step_value": s.step_value,
            "in_data": s.in_data, "out_data": s.out_data, "constant": s.constant,
            "amount_time_min": s.amount_time.total_seconds() / 60 if s.amount_time else None,
            "sensors": {t: {"limits": lim, **info.get(t, {"parameter": "?"})}
                        for t, lim in (s.dict_PLC_id or {}).items()},
        } for s in steps],
    }


@router.post("/{fid}/calculate")
async def calculate(fid: int, body: CalcIn, db: AsyncSession = Depends(get_db)):
    """Прогон цепочки шагов: масса конечного продукта + оценка совпадения с ожиданием."""
    form = await db.get(Formula, fid)
    if not form:
        raise HTTPException(404, "формула не найдена")
    rows = (await db.scalars(
        select(FormulaStep).where(FormulaStep.formula_id == fid).order_by(FormulaStep.step)
    )).all()
    steps = [{"step": r.step, "step_key": r.step_key, "step_value": r.step_value,
              "in_data": r.in_data or {}, "out_data": r.out_data or {}, "constant": r.constant or {}}
             for r in rows]
    try:
        res = run_formula(steps, body.inputs, body.constants, body.spread_pct, body.tolerance_pct)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"formula": {"id": form.id, "name": form.name, "version": form.version}, **res}
