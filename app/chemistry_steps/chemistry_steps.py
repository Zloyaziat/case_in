from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Formula, FormulaStep

router = APIRouter(prefix="/api/formulas", tags=["formulas"])


class SensorRange(BaseModel):
    min: float | None = None
    max: float | None = None
    unit: str = "°C"

    @model_validator(mode="after")
    def check(self):
        if self.min is None and self.max is None:
            raise ValueError("нужен min или max")
        if None not in (self.min, self.max) and self.min > self.max:
            raise ValueError("min > max")
        return self


class FormulaStepInput(BaseModel):
    step: int = Field(ge=1)
    step_key: str
    step_value: str                                   # уравнение, напр. "C6H12O6 -> 2C3H6O3"
    in_data: dict[str, SensorRange] = {}              # диапазоны ДО цикла: {sensor_id: {...}}
    out_data: dict[str, SensorRange] = {}             # диапазоны ПОСЛЕ цикла
    dict_PLC_id: list[str] = []                       # какие датчики относятся к шагу
    constant: dict[str, float] = {}                   # {"конверсия": 0.95, ...}
    amount_time: timedelta | None = None

    @model_validator(mode="after")
    def check(self):
        for name, v in self.constant.items():
            if not 0 < v <= 1:
                raise ValueError(f"константа '{name}' должна быть в (0, 1]")
        known = set(self.dict_PLC_id)
        for sid in {*self.in_data, *self.out_data} - known:
            raise ValueError(f"датчик '{sid}' не указан в dict_PLC_id")
        return self


class FormulaCreate(BaseModel):
    name: str
    version: int = Field(1, ge=1)
    steps: list[FormulaStepInput] = Field(min_length=1)


@router.post("")
async def new_chemistry_steps(data: FormulaCreate, db: AsyncSession = Depends(get_db)):
    nums = [s.step for s in data.steps]
    keys = [s.step_key for s in data.steps]
    if len(nums) != len(set(nums)):
        raise HTTPException(422, "Номера этапов должны быть уникальными")
    if len(keys) != len(set(keys)):
        raise HTTPException(422, "Ключи этапов должны быть уникальными")

    try:
        form = Formula(name=data.name, version=data.version)
        db.add(form)
        await db.flush()
        for item in sorted(data.steps, key=lambda s: s.step):
            db.add(FormulaStep(formula_id=form.id, **item.model_dump()))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Формула с таким названием и версией уже существует")
    except Exception:
        await db.rollback()
        raise

    return {"id": form.id, "name": form.name, "version": form.version,
            "steps_count": len(data.steps)}