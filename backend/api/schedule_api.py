from fastapi import APIRouter, Depends, HTTPException
from typing import List

from backend.db_manager.realtime import RealtimeDB
from backend.services.schedule_service import ScheduleService
from backend.models.schedule import ControlScheduleUpdate, ControlScheduleCreate, ControlScheduleResponse
from backend.core import settings

router = APIRouter(tags=["Schedules"])

db = RealtimeDB(settings.REALTIME_DB)
schedule_service = ScheduleService(db)

@router.get("/api/control_schedules/", response_model=List[ControlScheduleResponse])
@router.get("/api/control-schedules/", response_model=List[ControlScheduleResponse], include_in_schema=False)
def get_schedules():
    return schedule_service.get_all()

@router.post("/api/control_schedules/")
@router.post("/api/control-schedules/", include_in_schema=False)
def create_schedule(data: ControlScheduleCreate):
    try:
        res = schedule_service.create(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/api/control_schedules/{schedule_id}")
@router.patch("/api/control-schedules/{schedule_id}", include_in_schema=False)
def update_schedule(schedule_id: int, data: ControlScheduleUpdate):
    try:
        schedule_service.update(schedule_id, data)
        return {"status": "success", "message": f"Updated schedule {schedule_id}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
