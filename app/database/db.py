import os

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

load_dotenv()

default_db_url = "sqlite+aiosqlite:///./database.db?foreign_keys=on"
SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL", default_db_url)

# ЕДИНСТВЕННЫЙ Base в проекте. Все модели импортируют его отсюда.
Base = declarative_base()

connect_args = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=False,
    future=True,
    connect_args=connect_args,
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Создаёт отсутствующие таблицы. Существующие не трогает."""
    # Импорт внутри функции: чтобы модели зарегистрировались в Base.metadata
    # и не было циклического импорта (models импортирует Base из этого файла).
    import app.models  # noqa: F401
    import app.monitoring.models  # noqa: F401
    import app.batches.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "postgresql":
            # колонок по ТЗ нет в sql/case_in.sql - добавляем в уже созданные таблицы
            await conn.execute(text("ALTER TABLE batch ADD COLUMN IF NOT EXISTS quality_unit varchar(16)"))
            await conn.execute(text("ALTER TABLE batch_step_window ADD COLUMN IF NOT EXISTS n_samples integer"))


async def get_db():
    async with async_session() as db:
        yield db