from sqlalchemy import (
    Column, Integer, String, ForeignKey, UniqueConstraint, TIMESTAMP, text, Float, Interval
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Formula(Base):
    __tablename__ = "formula"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    version = Column(Integer, nullable=False)
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

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

    dict_PLC_id = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    amount_time = Column(Interval, nullable=True)

    __table_args__ = (
        UniqueConstraint("formula_id", "step", name="uq_step_no"),
        UniqueConstraint("formula_id", "step_key", name="uq_step_key"),
    )