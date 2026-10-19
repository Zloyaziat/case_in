from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Instrument, Sensor

router = APIRouter(prefix="/api/sensors", tags=["sensors"])


@router.get("")
async def list_sensors(db: AsyncSession = Depends(get_db)):
    """Список датчиков для выбора на фронте (tag = то, что кладётся в dict_PLC_id)."""
    q = (
        select(Sensor, Instrument.name)
        .join(Instrument, Instrument.id == Sensor.instrument_id)
        .order_by(Sensor.tag)
    )
    rows = (await db.execute(q)).all()
    return [
        {
            "id": s.id, "tag": s.tag, "parameter": s.parameter,
            "unit": s.unit, "instrument": iname,
            "valid_min": s.valid_min, "valid_max": s.valid_max,
        }
        for s, iname in rows
    ]
