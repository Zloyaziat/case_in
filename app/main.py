from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .database.db import init_db, engine
from .monitoring.manager import manager
from .routers import formulas, sensors, simulation


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await manager.stop()          # не оставляем симуляцию работать после остановки сервера
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

# uvicorn app.main:app --reload


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/frontend/formulas.html")


app.include_router(formulas.router)
app.include_router(sensors.router)
app.include_router(simulation.router)

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/frontend", StaticFiles(directory=FRONTEND, html=True), name="frontend")
