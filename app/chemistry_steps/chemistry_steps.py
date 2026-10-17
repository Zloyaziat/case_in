from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..tabels import Formula, FormulaStep

router = APIRouter(prefix="/api/formulas", tags=["formulas"])


class FormulaStepInput(BaseModel):
    step: int
    step_key: str
    step_value: str
    in_data: dict[str, Any] = Field(default_factory=dict)
    out_data: dict[str, Any] = Field(default_factory=dict)
    dict_PLC_id: list[str] = Field(default_factory=list)


class FormulaCreate(BaseModel):
    name: str
    version: int = 1
    steps: list[FormulaStepInput]


@router.post("/")
async def new_chemistry_steps(
    data: FormulaCreate,
    db: AsyncSession = Depends(get_db),
):
    # Проверяем уникальность названия и версии
    existing = await db.scalar(
        select(Formula).where(
            Formula.name == data.name,
            Formula.version == data.version,
        )
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Формула с таким названием и версией уже существует",
        )

    # Проверяем, что номера этапов уникальны
    step_numbers = [step.step for step in data.steps]

    if len(step_numbers) != len(set(step_numbers)):
        raise HTTPException(
            status_code=422,
            detail="Номера этапов должны быть уникальными",
        )

    step_keys = [step.step_key for step in data.steps]

    if len(step_keys) != len(set(step_keys)):
        raise HTTPException(
            status_code=422,
            detail="Ключи этапов должны быть уникальными",
        )

    try:
        # Создаём формулу
        form = Formula(
            name=data.name,
            version=data.version,
        )
        db.add(form)

        # Получаем ID формулы до создания этапов
        await db.flush()

        # Создаём записи всех этапов
        for item in data.steps:
            db.add(
                FormulaStep(
                    formula_id=form.id,
                    step=item.step,
                    step_key=item.step_key,
                    step_value=item.step_value,
                    in_data=item.in_data,
                    out_data=item.out_data,
                    dict_PLC_id=item.dict_PLC_id,
                )
            )

        await db.commit()
        await db.refresh(form)

        return {
            "id": form.id,
            "name": form.name,
            "version": form.version,
            "steps_count": len(data.steps),
        }

    except Exception:
        await db.rollback()
        raise