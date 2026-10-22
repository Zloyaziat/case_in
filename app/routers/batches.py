"""API партий (ТЗ «ядро MVP»): выбрать формулу -> v_in -> старт -> показания/рекомендации -> завершение."""
import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..batches import repo
from ..batches.models import Batch, BatchRecommendation, BatchStep, BatchStepWindow
from ..batches.opc import OpcEmulator
from ..batches.process import BatchProcess
from ..batches.reference import K_STD, REF_LIMIT
from ..batches.session import BatchSession, sessions
from ..database import async_session, get_db
from ..models import Formula

router = APIRouter(prefix="/api/batches", tags=["batches"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = (BASE_DIR / "data").resolve()
OPC_FILE = Path(os.getenv("OPC_FILE", DATA_DIR / "opc_formula15.txt"))


class BatchCreate(BaseModel):
    formula_id: int
    v_in: dict[str, float] | None = Field(None, description='Сырьё, можно ввести позже: {"CaO": 62.5, "H20": 240}')


class VInIn(BaseModel):
    v_in: dict[str, float] = Field(min_length=1, description='{"CaO": 62.5, "H20": 240}')

    @field_validator("v_in")
    @classmethod
    def _positive(cls, v):
        for k, x in v.items():
            if x <= 0:
                raise ValueError(f"v_in['{k}'] должно быть > 0")
        return v


class StartIn(BaseModel):
    opc_file: str | None = Field(None, description="txt с показаниями из папки data/ (по умолчанию opc_formula15.txt)")
    speed: float = Field(1.0, gt=0, le=100, description="Ускорение времени: 10 - партия идёт в 10 раз быстрее")
    window_seconds: float = Field(2.0, gt=0, le=3600, description="Окно усреднения, секунд")
    k: float = Field(K_STD, gt=0, le=20, description="Порог: |delta| > max(k * ref_std, допуск датчика)")
    min_ref_quality: float | None = Field(None, description="Эталоны только с quality >= этого значения")
    ref_limit: int = Field(REF_LIMIT, ge=1, le=100, description="Сколько эталонных партий сравнивать")


class FinishIn(BaseModel):
    v_finish: float = Field(ge=0)
    quality: float = Field(ge=0)
    quality_unit: str = Field("%", max_length=16)
    is_reference: bool = Field(False, description="Сделать партию эталонной")


class ReferenceIn(BaseModel):
    is_reference: bool


# ----------------------------------------------------------------- вспомогательное

async def _get_batch(db: AsyncSession, bid: int) -> Batch:
    b = await db.get(Batch, bid)
    if b is None:
        raise HTTPException(404, "партия не найдена")
    return b


def _require(b: Batch, *statuses: str) -> None:
    if b.status not in statuses:
        raise HTTPException(409, f"партия в статусе {b.status}, нужно: {' / '.join(statuses)}")


def _seconds_to_time(s: float) -> time:
    """t_total_sec в дампе имеет тип time - больше суток не поместится."""
    if s >= 86400:
        raise HTTPException(422, "длительность партии больше суток не помещается в batch.t_total_sec (тип time)")
    td = timedelta(seconds=round(s, 6))
    return (datetime.min + td).time()


def _iso(x: datetime | None) -> str | None:
    return x.isoformat() if x else None


def _phase(b: Batch) -> str:
    """created / running / awaiting_finish (шаги пройдены, ждём v_finish и качество) / finished / aborted."""
    if b.status == "running" and b.current_step is None:
        return "awaiting_finish"
    return b.status


def _batch_out(b: Batch) -> dict:
    return {
        "id": b.id, "formula_id": b.formula_id, "status": b.status, "phase": _phase(b),
        "v_in": b.v_in, "started_at": _iso(b.started_at), "finished_at": _iso(b.finished_at),
        "current_step": b.current_step,
        "t_total_sec": (b.t_total_sec.hour * 3600 + b.t_total_sec.minute * 60 + b.t_total_sec.second
                        + b.t_total_sec.microsecond / 1e6) if b.t_total_sec else None,
        "v_finish": float(b.v_finish) if b.v_finish is not None else None,
        "quality": float(b.quality) if b.quality is not None else None,
        "quality_unit": b.quality_unit, "is_reference": b.is_reference,
    }


# ----------------------------------------------------------------- партии

@router.post("")
async def create_batch(body: BatchCreate, db: AsyncSession = Depends(get_db)):
    """1. Оператор выбрал формулу - создаётся партия (status = created)."""
    if await db.get(Formula, body.formula_id) is None:
        raise HTTPException(404, "формула не найдена")
    if not await repo.load_steps(db, body.formula_id):
        raise HTTPException(422, "у формулы нет шагов")
    b = Batch(formula_id=body.formula_id, status="created", v_in=body.v_in)
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return _batch_out(b)


@router.get("")
async def list_batches(formula_id: int | None = None, only_reference: bool = False,
                       db: AsyncSession = Depends(get_db)):
    q = select(Batch).order_by(Batch.id.desc()).limit(100)
    if formula_id is not None:
        q = q.where(Batch.formula_id == formula_id)
    if only_reference:
        q = q.where(Batch.is_reference.is_(True))
    return [_batch_out(b) for b in (await db.scalars(q)).all()]


@router.get("/{bid}")
async def get_batch(bid: int, db: AsyncSession = Depends(get_db)):
    """Партия, её шаги (таймеры) и живой статус, если показания сейчас принимаются."""
    b = await _get_batch(db, bid)
    steps = (await db.scalars(select(BatchStep).where(BatchStep.batch_id == bid).order_by(BatchStep.step))).all()
    n_recs = await db.scalar(select(func.count()).select_from(BatchRecommendation)
                             .where(BatchRecommendation.batch_id == bid))
    s = sessions.get(bid)
    return {
        **_batch_out(b),
        "steps": [{"step": st.step, "status": st.status, "started_at": _iso(st.started_at),
                   "finished_at": _iso(st.finished_at), "planned_seconds": st.planned_seconds,
                   "ended_by": st.ended_by} for st in steps],
        "recommendations_total": n_recs,
        "live": s.status() if s else None,
    }


@router.put("/{bid}/v_in")
async def set_v_in(bid: int, body: VInIn, db: AsyncSession = Depends(get_db)):
    """2. Ввод данных по сырью."""
    b = await _get_batch(db, bid)
    _require(b, "created")
    b.v_in = body.v_in
    await db.commit()
    return _batch_out(b)


@router.post("/{bid}/start")
async def start_batch(bid: int, body: StartIn, db: AsyncSession = Depends(get_db)):
    """3. Запуск: фиксируем время старта, запускаем таймер 1-го шага и приём показаний из txt (имитация OPC)."""
    b = await _get_batch(db, bid)
    _require(b, "created")
    if not b.v_in:
        raise HTTPException(422, "сначала введите v_in: PUT /api/batches/{id}/v_in")

    path = (DATA_DIR / body.opc_file).resolve() if body.opc_file else OPC_FILE
    if body.opc_file and not path.is_relative_to(DATA_DIR):
        raise HTTPException(422, "opc_file должен лежать в папке data/")
    if not path.is_file():
        raise HTTPException(422, f"файл с показаниями не найден: {path}")
    try:
        emulator = OpcEmulator.from_path(path)
    except ValueError as e:
        raise HTTPException(422, f"{path.name}: {e}")

    steps = await repo.load_steps(db, b.formula_id)
    if not steps:
        raise HTTPException(422, "у формулы нет шагов")
    specs = await repo.load_specs(db, steps)
    if unknown := {t for s in steps for t in s.tags} - set(specs):
        raise HTTPException(422, {"error": "неизвестные датчики (нет в таблице sensors)", "tags": sorted(unknown)})
    refs = await repo.load_references(db, b, body.min_ref_quality, body.ref_limit)

    b.status = "running"
    b.started_at = datetime.now(timezone.utc)
    await db.commit()

    limits = {t: (s.valid_min, s.valid_max) for t, s in specs.items()}
    process = BatchProcess(steps, window_s=body.window_seconds, limits=limits)
    session = BatchSession(b.id, b.started_at, process, emulator, refs, specs, async_session,
                           speed=body.speed, k=body.k)
    sessions[b.id] = session
    await session.begin()
    await db.refresh(b)
    return {**_batch_out(b), "opc_file": str(path), "reference_batches": refs.batch_ids,
            "steps": [{"step": s.step, "planned_seconds": s.planned_s, "sensors": sorted(s.tags)} for s in steps]}


@router.post("/{bid}/next-step")
async def next_step(bid: int, db: AsyncSession = Depends(get_db)):
    """Оператор завершает текущий шаг досрочно - начинается следующий."""
    b = await _get_batch(db, bid)
    _require(b, "running")
    s = sessions.get(bid)
    if s is None or s.process.current is None:
        raise HTTPException(409, "сейчас не идёт ни один шаг")
    await s.next_step()
    await db.refresh(b)
    return {**_batch_out(b), "live": s.status()}


async def _close(db: AsyncSession, b: Batch, ended_by: str) -> None:
    """Останавливает приём показаний и проставляет finished_at / t_total_sec."""
    s = sessions.pop(b.id, None)
    end_at: datetime | None = None
    if s is not None:
        if not s.process.done:
            end_at = s.wall(await s.stop(ended_by))
        else:
            await s.stop(ended_by)
    if end_at is None:
        # шаги уже пройдены (или сервер перезапускался): конец процесса - конец последнего шага
        end_at = await db.scalar(select(func.max(BatchStep.finished_at)).where(BatchStep.batch_id == b.id))
        open_steps = (await db.scalars(select(BatchStep).where(BatchStep.batch_id == b.id,
                                                               BatchStep.finished_at.is_(None)))).all()
        now = datetime.now(timezone.utc)
        for st in open_steps:
            st.finished_at, st.status, st.ended_by = now, "aborted" if ended_by == "abort" else "done", ended_by
        if open_steps or end_at is None:
            end_at = now
    await db.refresh(b)
    b.finished_at = max(end_at, b.started_at)
    b.t_total_sec = _seconds_to_time((b.finished_at - b.started_at).total_seconds())
    b.current_step = None


@router.post("/{bid}/finish")
async def finish_batch(bid: int, body: FinishIn, db: AsyncSession = Depends(get_db)):
    """6. Завершение: v_finish и качество; партию можно сразу сделать эталонной."""
    b = await _get_batch(db, bid)
    _require(b, "running")
    await _close(db, b, "finish")
    b.status = "finished"
    b.v_finish, b.quality, b.quality_unit = body.v_finish, body.quality, body.quality_unit
    b.is_reference = body.is_reference
    await db.commit()
    return _batch_out(b)


@router.post("/{bid}/abort")
async def abort_batch(bid: int, db: AsyncSession = Depends(get_db)):
    b = await _get_batch(db, bid)
    _require(b, "running")
    await _close(db, b, "abort")
    b.status = "aborted"
    await db.commit()
    return _batch_out(b)


@router.put("/{bid}/reference")
async def set_reference(bid: int, body: ReferenceIn, db: AsyncSession = Depends(get_db)):
    """Пометить / снять отметку эталонной партии (только завершённые)."""
    b = await _get_batch(db, bid)
    if body.is_reference:
        _require(b, "finished")
    b.is_reference = body.is_reference
    await db.commit()
    return _batch_out(b)


# ----------------------------------------------------------------- данные партии

@router.get("/{bid}/metrics")
async def batch_metrics(bid: int, step: int | None = None, db: AsyncSession = Depends(get_db)):
    """Усреднённые временные ряды (batch_step_window): time - правая граница окна от начала шага."""
    await _get_batch(db, bid)
    q = select(BatchStepWindow).where(BatchStepWindow.batch_id == bid)
    if step is not None:
        q = q.where(BatchStepWindow.step == step)
    rows = (await db.scalars(q.order_by(BatchStepWindow.step, BatchStepWindow.time))).all()
    return [{"step": r.step, "time_s": r.time.total_seconds(), "V": r.detectors, "n_samples": r.n_samples}
            for r in rows]


@router.get("/{bid}/recommendations")
async def batch_recommendations(bid: int, step: int | None = None, after_id: int = 0,
                                db: AsyncSession = Depends(get_db)):
    """Рекомендации оператору; after_id - чтобы подгружать только новые."""
    await _get_batch(db, bid)
    q = select(BatchRecommendation).where(BatchRecommendation.batch_id == bid, BatchRecommendation.id > after_id)
    if step is not None:
        q = q.where(BatchRecommendation.step == step)
    rows = (await db.scalars(q.order_by(BatchRecommendation.id).limit(1000))).all()
    return [{"id": r.id, "step": r.step, "time_s": r.time.total_seconds(), "tag": r.tag, "value": r.value,
             "ref_avg": r.ref_avg, "ref_std": r.ref_std, "n_refs": r.n_refs, "delta": r.delta,
             "threshold": r.threshold, "message": r.message} for r in rows]
