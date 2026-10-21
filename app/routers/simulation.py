"""API симуляции: эталонные партии, длительность стадий, запуск/остановка, статус, показания, сигналы."""
import os
from datetime import timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Formula, FormulaStep
from ..monitoring import repo
from ..monitoring.engine import band_at, parse_step_sensors
from ..monitoring.manager import manager
from ..monitoring.models import SensorAlert, SensorReading, SimRun, SimStepRun
from ..monitoring.plan import n_ticks
from ..monitoring.source import FileSource, pick_sources

router = APIRouter(prefix="/api/simulation", tags=["simulation"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_FILE = Path(os.getenv("SENSOR_DATA_FILE", BASE_DIR / "data" / "sensor_data_5000.csv"))


def _file_source() -> FileSource | None:
    return FileSource.from_path(DATA_FILE) if DATA_FILE.is_file() else None


class DurationIn(BaseModel):
    seconds: float = Field(gt=0, description="Длительность стадии в секундах, например 14")


class ReferenceIn(BaseModel):
    formula_id: int
    n_batches: int = Field(30, ge=2, le=1000)
    seed: int | None = Field(None, description="Одинаковый seed - одинаковые эталонные партии")


class StartIn(BaseModel):
    formula_id: int
    steps: list[int] | None = Field(None, description="Какие стадии запустить (по умолчанию все по порядку)")
    tick_seconds: float = Field(0.5, ge=0.05, le=60, description="Период опроса датчиков, секунд")
    step_seconds: float | None = Field(None, gt=0, description="Длительность ВСЕХ стадий в секундах (например 14)")
    step_durations: dict[int, float] = Field(default_factory=dict, description="Длительность по стадиям: {1: 10, 2: 14}")
    save_durations: bool = Field(False, description="Записать эти длительности в formula_steps.amount_time")
    source: Literal["auto", "file", "synthetic"] = "auto"
    fault_rate: float = Field(0.05, ge=0, le=1, description="Доля сбоев в синтетических данных")
    seed: int | None = None
    reference_batches: int = Field(30, ge=2, le=1000, description="Сколько эталонных партий генерировать, если их нет")

    @field_validator("step_durations")
    @classmethod
    def _positive(cls, v):
        for k, x in v.items():
            if x <= 0:
                raise ValueError(f"step_durations[{k}] должна быть > 0")
        return v


async def _get_formula(db: AsyncSession, fid: int) -> Formula:
    f = await db.get(Formula, fid)
    if f is None:
        raise HTTPException(404, "формула не найдена")
    return f


# ----------------------------------------------------------------- длительность стадии

@router.patch("/formulas/{fid}/steps/{step}/duration")
async def set_step_duration(fid: int, step: int, body: DurationIn, db: AsyncSession = Depends(get_db)):
    """Записывает в БД (formula_steps.amount_time), что стадия длится N секунд."""
    row = await db.scalar(select(FormulaStep).where(FormulaStep.formula_id == fid, FormulaStep.step == step))
    if row is None:
        raise HTTPException(404, "стадия не найдена")
    row.amount_time = timedelta(seconds=body.seconds)
    await db.commit()
    return {"formula_id": fid, "step": step, "amount_time_seconds": body.seconds}


# ----------------------------------------------------------------- эталонные партии

@router.post("/reference/generate")
async def generate_reference(body: ReferenceIn, db: AsyncSession = Depends(get_db)):
    """Генерирует эталонные партии (по умолчанию 30) для всех стадий формулы; старые заменяются."""
    await _get_formula(db, body.formula_id)
    steps = await repo.get_steps(db, body.formula_id)
    if not steps:
        raise HTTPException(422, "у формулы нет стадий")
    tags = {t for s in steps for t in parse_step_sensors(s.dict_PLC_id)}
    specs = await repo.get_specs(db, tags)
    created = await repo.generate_reference(db, steps, specs, body.n_batches, body.seed or 0)
    return {"formula_id": body.formula_id, "n_batches": body.n_batches,
            "rows_per_step": created, "total_rows": sum(created.values())}


@router.get("/reference/{fid}")
async def get_reference(fid: int, db: AsyncSession = Depends(get_db)):
    """Средние значения датчиков по эталонным партиям на каждой стадии + допустимые полосы."""
    await _get_formula(db, fid)
    steps = await repo.get_steps(db, fid)
    tags = {t for s in steps for t in parse_step_sensors(s.dict_PLC_id)}
    specs = await repo.get_specs(db, tags)
    profiles = await repo.load_profiles(db, [s.id for s in steps])
    out = []
    for st in steps:
        sensors = []
        for tag, lim in parse_step_sensors(st.dict_PLC_id).items():
            b0, b1 = band_at(lim, 0.0), band_at(lim, 1.0)
            prof = profiles.get(st.id, {}).get(tag)
            sp = specs.get(tag)
            sensors.append({
                "tag": tag, "parameter": sp.parameter if sp else None, "unit": sp.unit if sp else None,
                "band_start": None if b0 is None else {"min": b0.min, "max": b0.max},
                "band_end": None if b1 is None else {"min": b1.min, "max": b1.max},
                "start_mean": None if prof is None else round(prof[0], 4),
                "end_mean": None if prof is None else round(prof[1], 4),
                "n_batches": None if prof is None else prof[2],
            })
        out.append({"step": st.step, "step_key": st.step_key,
                    "amount_time_seconds": st.amount_time.total_seconds() if st.amount_time else None,
                    "sensors": sensors})
    return {"formula_id": fid, "steps": out}


# ----------------------------------------------------------------- запуск / остановка / статус

@router.post("/start")
async def start(body: StartIn, db: AsyncSession = Depends(get_db)):
    """Запускает симуляцию в фоне: стадии по очереди, датчики опрашиваются каждые tick_seconds."""
    if manager.is_running():
        raise HTTPException(409, f"симуляция уже идёт (run_id={manager.run_id}); остановите её: POST /api/simulation/stop")
    await _get_formula(db, body.formula_id)
    steps = await repo.get_steps(db, body.formula_id, body.steps)
    if not steps:
        raise HTTPException(422, "нет стадий для запуска")

    tags = {t for s in steps for t in parse_step_sensors(s.dict_PLC_id)}
    specs = await repo.get_specs(db, tags)
    if unknown := tags - set(specs):
        raise HTTPException(422, {"error": "неизвестные датчики (нет в таблице sensors)", "tags": sorted(unknown)})

    file_source = _file_source()
    if body.source == "file" and file_source is None:
        raise HTTPException(422, f"файл с показаниями не найден: {DATA_FILE}")

    # эталонные партии: если для стадии их ещё нет - генерируем
    generated = await repo.ensure_reference(db, steps, specs, body.reference_batches, body.seed or 0)
    profiles = await repo.load_profiles(db, [s.id for s in steps])
    try:
        step_runs = repo.make_step_runs(steps, specs, profiles, body.step_seconds, body.step_durations)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if body.save_durations:
        await repo.save_durations(db, steps, step_runs)

    run = SimRun(formula_id=body.formula_id, status="running", tick_seconds=body.tick_seconds,
                 source_mode=body.source)
    db.add(run)
    await db.commit()

    await manager.start(run.id, step_runs, tick_seconds=body.tick_seconds, source_mode=body.source,
                        fault_rate=body.fault_rate, seed=body.seed, file_source=file_source)
    return {
        "run_id": run.id,
        "status": "running",
        "reference_generated_for_steps": generated,
        "total_seconds": round(sum(s.duration_s for s in step_runs), 2),
        "steps": [{
            "step": s.step, "key": s.key, "title": s.title,
            "duration_s": s.duration_s, "duration_from": s.duration_source,
            "ticks": n_ticks(s.duration_s, body.tick_seconds),
            "sources": pick_sources(s.sensors, file_source, body.source),
        } for s in step_runs],
        "watch": "GET /api/simulation/status  |  GET /api/simulation/runs/{run_id}/alerts",
    }


@router.post("/stop")
async def stop():
    if not await manager.stop():
        raise HTTPException(409, "сейчас ничего не запущено")
    return {"stopped": True, "run_id": manager.run_id}


@router.get("/status")
async def status():
    return manager.status()


# ----------------------------------------------------------------- результаты

@router.get("/runs")
async def list_runs(db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(SimRun).order_by(SimRun.id.desc()).limit(50))).all()
    return [{"run_id": r.id, "formula_id": r.formula_id, "status": r.status, "tick_seconds": r.tick_seconds,
             "source": r.source_mode, "started_at": r.started_at.isoformat() if r.started_at else None,
             "finished_at": r.finished_at.isoformat() if r.finished_at else None, "note": r.note}
            for r in rows]


@router.get("/runs/{run_id}/steps")
async def run_steps(run_id: int, db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(SimStepRun).where(SimStepRun.run_id == run_id)
                             .order_by(SimStepRun.id))).all()
    return [{"step": r.step, "key": r.step_key, "duration_s": r.duration_seconds, "ticks": r.ticks,
             "sources": r.sources, "status": r.status} for r in rows]


@router.get("/runs/{run_id}/readings")
async def run_readings(run_id: int, step: int | None = None, tag: str | None = None,
                       only_alerts: bool = False, after_id: int = 0,
                       limit: int = Query(200, ge=1, le=2000), db: AsyncSession = Depends(get_db)):
    q = select(SensorReading).where(SensorReading.run_id == run_id, SensorReading.id > after_id)
    if step is not None:
        q = q.where(SensorReading.step == step)
    if tag:
        q = q.where(SensorReading.tag == tag)
    if only_alerts:
        q = q.where(SensorReading.status.notin_(["ok", "no_limits"]))
    rows = (await db.scalars(q.order_by(SensorReading.id).limit(limit))).all()
    return [{"id": r.id, "step": r.step, "elapsed_s": r.elapsed_s, "tag": r.tag, "value": r.value,
             "raw": r.raw_value, "unit": r.unit, "status": r.status, "expected": r.expected,
             "band_min": r.band_min, "band_max": r.band_max, "source": r.source,
             "label_anomaly": r.label_anomaly, "label_type": r.label_type} for r in rows]


@router.get("/runs/{run_id}/alerts")
async def run_alerts(run_id: int, step: int | None = None, db: AsyncSession = Depends(get_db)):
    """Сигналы оператору: 'Нужно повысить температуру до 39 °C на датчике F-TT-01!'."""
    q = select(SensorAlert).where(SensorAlert.run_id == run_id)
    if step is not None:
        q = q.where(SensorAlert.step == step)
    rows = (await db.scalars(q.order_by(SensorAlert.id).limit(2000))).all()
    return [{"id": r.id, "step": r.step, "tag": r.tag, "kind": r.kind, "value": r.value,
             "target": r.target, "message": r.message} for r in rows]
