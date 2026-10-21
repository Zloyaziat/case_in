"""Новые таблицы для симуляции. Создаются автоматически при старте сервера (init_db -> create_all).

Старые таблицы (formula, formula_steps, sensors, instruments) не меняются."""
from sqlalchemy import (
    BigInteger, Boolean, Column, Float, ForeignKey, Index, Integer, String, Text,
    TIMESTAMP, UniqueConstraint, func,
)

from ..database.db import Base

_BIGID = BigInteger().with_variant(Integer, "sqlite")


class ReferenceBatchValue(Base):
    """Эталонная ("хорошая") партия: начальное и конечное значение датчика на стадии."""
    __tablename__ = "reference_batch_values"

    id = Column(Integer, primary_key=True, autoincrement=True)
    formula_step_id = Column(Integer, ForeignKey("formula_steps.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    batch_no = Column(Integer, nullable=False)
    tag = Column(String, nullable=False)
    v_start = Column(Float, nullable=False)
    v_end = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("formula_step_id", "batch_no", "tag", name="uq_ref_step_batch_tag"),
    )


class SimRun(Base):
    """Один запуск симуляции."""
    __tablename__ = "sim_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    formula_id = Column(Integer, ForeignKey("formula.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="running")   # running | finished | stopped | failed
    tick_seconds = Column(Float, nullable=False)
    source_mode = Column(String(20), nullable=False, default="auto")
    started_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)
    note = Column(Text, nullable=True)


class SimStepRun(Base):
    """Одна стадия внутри запуска: сколько секунд длилась и откуда взяты данные."""
    __tablename__ = "sim_step_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("sim_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    formula_step_id = Column(Integer, ForeignKey("formula_steps.id", ondelete="SET NULL"), nullable=True)
    step = Column(Integer, nullable=False)
    step_key = Column(String, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    ticks = Column(Integer, nullable=False)
    sources = Column(Text, nullable=True)            # "F-TT-01=file, F-pH-02=file"
    status = Column(String(20), nullable=False, default="running")   # running | done | aborted
    started_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)


class SensorReading(Base):
    """Каждое принятое показание датчика (ГЛАВНАЯ таблица данных для обучения ИИ)."""
    __tablename__ = "sensor_readings"

    id = Column(_BIGID, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("sim_runs.id", ondelete="CASCADE"), nullable=False)
    step = Column(Integer, nullable=False)
    ts = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    elapsed_s = Column(Float, nullable=False)            # секунды от начала стадии (по таймеру)
    progress = Column(Float, nullable=False)             # 0..1 положение внутри стадии
    tag = Column(String, nullable=False)
    sensor_id = Column(Integer, ForeignKey("sensors.id", ondelete="SET NULL"), nullable=True)
    value = Column(Float, nullable=True)                 # число (NULL, если пришёл мусор)
    raw_value = Column(String, nullable=True)            # как пришло ("ERR", "37.03")
    unit = Column(String, nullable=True)
    quality = Column(String(12), nullable=True)
    source = Column(String(12), nullable=False)          # file | synthetic
    source_row_id = Column(Integer, nullable=True)       # row_id в CSV
    expected = Column(Float, nullable=True)              # эталон в этот момент
    band_min = Column(Float, nullable=True)              # допустимая полоса в этот момент
    band_max = Column(Float, nullable=True)
    status = Column(String(16), nullable=False)          # ok | low | high | bad_value | ...
    label_anomaly = Column(Boolean, nullable=True)       # разметка из файла (для проверки качества)
    label_type = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_sensor_readings_run_step", "run_id", "step", "id"),
        Index("ix_sensor_readings_run_tag", "run_id", "tag", "id"),
    )


class SensorAlert(Base):
    """Сигнал оператору: "Нужно повысить температуру до 39 °C на датчике F-TT-01!"."""
    __tablename__ = "sensor_alerts"

    id = Column(_BIGID, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("sim_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    reading_id = Column(_BIGID, ForeignKey("sensor_readings.id", ondelete="CASCADE"), nullable=True)
    step = Column(Integer, nullable=False)
    ts = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    tag = Column(String, nullable=False)
    kind = Column(String(16), nullable=False)            # low | high | bad_value | sensor_fault | unit_error
    value = Column(Float, nullable=True)
    target = Column(Float, nullable=True)                # рекомендуемое значение
    message = Column(Text, nullable=False)
