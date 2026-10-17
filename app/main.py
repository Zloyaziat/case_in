from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from dateutil.relativedelta import relativedelta  
from pydantic import BaseModel
import sys
from prophet import Prophet
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import  get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_,select, func, desc, and_
from app import models
from datetime import datetime, timedelta, date
from typing import Optional
import pandas as pd

# uvicorn app.main:app --reload

app = FastAPI()



BASE_DIR = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")
app.mount("/html", StaticFiles(directory=FRONTEND_DIR / "js"), name="html")

