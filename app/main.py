from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .database.db import init_db, engine   # ← вот так
from .routers import formulas, sensors
from fastapi.responses import RedirectResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

# uvicorn app.main:app --reload


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/frontend/formulas.html")
app.include_router(formulas.router)
app.include_router(sensors.router)

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/frontend", StaticFiles(directory=FRONTEND, html=True), name="frontend")