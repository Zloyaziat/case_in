from sqlalchemy import (
    Column, Integer, String, ForeignKey, UniqueConstraint,
    TIMESTAMP, text, Interval, Float
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, declarative_base
from .database.db import Base  # ← импортируем, НЕ создаём новый declarative_base()


class Formula(Base):
    __tablename__ = "formula"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    version = Column(Integer, nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_formula_name_version"),
    )


class FormulaStep(Base):
    __tablename__ = "formula_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    formula_id = Column(
        Integer,
        ForeignKey("formula.id", ondelete="RESTRICT"),
        nullable=False,
    )

    step = Column(Integer, nullable=False)
    step_key = Column(String, nullable=False)
    step_value = Column(String, nullable=False)

    in_data = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    out_data = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    dict_PLC_id = Column("dict_plc_id",JSONB, nullable=True, server_default=text("'[]'::jsonb"))

    amount_time = Column(Interval, nullable=True)

    constant = Column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        UniqueConstraint("formula_id", "step", name="uq_step_no"),
        UniqueConstraint("formula_id", "step_key", name="uq_step_key"),
    )


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)

    sensors = relationship("Sensor", back_populates="instrument", passive_deletes=True)

    def __repr__(self):
        return f"<Instrument id={self.id} name={self.name!r}>"


class Sensor(Base):
    __tablename__ = "sensors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # stage = Column(String, nullable=False, index=True)
    tag = Column(String, nullable=False, unique=True)
    parameter = Column(String, nullable=False)
    instrument_id = Column(
        Integer,
        ForeignKey("instruments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    unit = Column(String, nullable=False)

    val_start = Column(Float, nullable=True)
    val_mid = Column(Float, nullable=True)
    val_end = Column(Float, nullable=True)
    valid_min = Column(Float, nullable=True)
    valid_max = Column(Float, nullable=True)
    noise_sd = Column(Float, nullable=True)
    norm = Column(String, nullable=True)

    instrument = relationship("Instrument", back_populates="sensors")

    def __repr__(self):
        return f"<Sensor id={self.id} tag={self.tag!r} stage={self.stage!r}>"
