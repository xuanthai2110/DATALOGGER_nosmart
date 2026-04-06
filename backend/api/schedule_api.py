from fastapi import APIRouter, Depends, HTTPException
from typing import List

from backend.db_manager.realtime import RealtimeDB
from backend.services.schedule_service import ScheduleService
from backend.models.schedule import ControlScheduleUpdate, ControlScheduleCreate, ControlScheduleResponse
from backend.core import config

router = APIRouter(prefix="/api/control-schedules", tags=["Schedules"])

db = RealtimeDB(config.REALTIME_DB)
schedule_service = ScheduleService(db)

@router.get("/", response_model=List[ControlScheduleResponse])
def get_schedules():
    return schedule_service.get_all()

@router.post("/")
def create_schedule(data: ControlScheduleCreate):
    try:
        res = schedule_service.create(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{schedule_id}")
def update_schedule(schedule_id: int, data: ControlScheduleUpdate):
    try:
        schedule_service.update(schedule_id, data)
        return {"status": "success", "message": f"Updated schedule {schedule_id}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
