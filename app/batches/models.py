"""Таблицы партий по ТЗ «ядро MVP».

batch и batch_step_window уже есть в sql/case_in.sql - модели повторяют их схему.
batch_step и batch_recommendations - новые, создаются при старте сервера (init_db -> create_all).
Колонки batch.quality_unit и batch_step_window.n_samples в дампе нет - их добавляет init_db."""
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Column, Float, ForeignKey, Integer, Interval, Numeric,
    PrimaryKeyConstraint, String, Text, Time, TIMESTAMP, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB

from ..database.db import Base

_BIGID = BigInteger().with_variant(Integer, "sqlite")

BATCH_STATUSES = ("created", "running", "finished", "aborted")


class Batch(Base):
    """Партия - один производственный цикл по формуле."""
    __tablename__ = "batch"

    id = Column(_BIGID, primary_key=True, autoincrement=True)
    formula_id = Column(_BIGID, ForeignKey("formula.id", onupdate="CASCADE", ondelete="RESTRICT"),
                        nullable=False, index=True)
    status = Column(String(16), nullable=False, default="created", server_default=text("'created'"))
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)
    v_in = Column(JSONB, nullable=True)                  # сырьё: {"CaO": 62.5, "H20": 240}
    v_finish = Column(Numeric(14, 4), nullable=True)     # объём/масса на выходе
    quality = Column(Numeric(12, 4), nullable=True)
    quality_unit = Column(String(16), nullable=True)     # "%" или единица концентрации
    is_reference = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    current_step = Column(Integer, nullable=True)        # NULL - шаг не идёт (ещё не начат или все пройдены)
    t_total_sec = Column(Time, nullable=True)            # длительность цикла (в дампе тип time)

    __table_args__ = (
        CheckConstraint("status IN ('created', 'running', 'finished', 'aborted')", name="batch_status_check"),
    )


class BatchStepWindow(Base):
    """Усреднённые показания: одна строка на окно шага. time - правая граница окна от начала шага."""
    __tablename__ = "batch_step_window"

    batch_id = Column(_BIGID, ForeignKey("batch.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    step = Column(Integer, nullable=False)
    time = Column(Interval, nullable=False)
    detectors = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))   # {"D-LAC-04": 20.1, ...}
    n_samples = Column(Integer, nullable=True)           # сколько показаний попало в средние

    __table_args__ = (
        PrimaryKeyConstraint("batch_id", "step", "time", name="batch_step_window_pkey"),
    )


class BatchStep(Base):
    """Таймер шага: от started_at отсчитывается время показаний этого шага."""
    __tablename__ = "batch_step"

    batch_id = Column(_BIGID, ForeignKey("batch.id", ondelete="CASCADE"), nullable=False)
    step = Column(Integer, nullable=False)
    started_at = Column(TIMESTAMP(timezone=True), nullable=False)
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)
    status = Column(String(16), nullable=False, default="running")   # running | done | aborted
    planned_seconds = Column(Float, nullable=True)       # formula_steps.amount_time
    ended_by = Column(String(16), nullable=True)         # timer | operator | finish | abort

    __table_args__ = (
        PrimaryKeyConstraint("batch_id", "step", name="batch_step_pkey"),
    )


class BatchRecommendation(Base):
    """Рекомендация оператору по итогам сравнения окна с эталонными партиями."""
    __tablename__ = "batch_recommendations"

    id = Column(_BIGID, primary_key=True, autoincrement=True)
    batch_id = Column(_BIGID, ForeignKey("batch.id", ondelete="CASCADE"), nullable=False, index=True)
    step = Column(Integer, nullable=False)
    time = Column(Interval, nullable=False)
    tag = Column(String, nullable=False)
    value = Column(Float, nullable=False)                # среднее за окно
    ref_avg = Column(Float, nullable=False)
    ref_std = Column(Float, nullable=False)
    n_refs = Column(Integer, nullable=False)
    delta = Column(Float, nullable=False)                # value - ref_avg
    threshold = Column(Float, nullable=False)            # max(k * ref_std, допуск датчика)
    message = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
