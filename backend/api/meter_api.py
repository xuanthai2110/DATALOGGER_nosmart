"""
backend/api/meter_api.py — API for Meter management (CRUD).
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from backend.services.project_service import ProjectService
from backend.api.scan_api import get_project_service
from backend.models.meter import MeterCreate, MeterUpdate
import logging

router = APIRouter(tags=["meters"])
logger = logging.getLogger(__name__)

@router.get("/project/{project_id}")
def get_meters(project_id: int, svc: ProjectService = Depends(get_project_service)):
    """Lấy danh sách meter theo project."""
    return svc.get_meters_by_project(project_id)

@router.post("/")
def create_meter(data: MeterCreate, svc: ProjectService = Depends(get_project_service)):
    """Tạo mới meter thủ công."""
    meter_id = svc.create_meter(data)
    return {"ok": True, "id": meter_id}

@router.patch("/{meter_id}")
def update_meter(meter_id: int, data: MeterUpdate, svc: ProjectService = Depends(get_project_service)):
    """Cập nhật thông tin meter."""
    svc.update_meter(meter_id, data)
    return {"ok": True}

@router.delete("/{meter_id}")
def delete_meter(meter_id: int, svc: ProjectService = Depends(get_project_service)):
    """Xoá meter."""
    svc.delete_meter(meter_id)
    return {"ok": True}
