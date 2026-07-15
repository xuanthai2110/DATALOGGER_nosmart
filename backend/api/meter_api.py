"""
backend/api/meter_api.py — API for Meter management (CRUD).
"""
from fastapi import APIRouter, Depends, Body
from fastapi.responses import JSONResponse
from backend.services.project_service import ProjectService
from backend.api.scan_api import get_project_service
from backend.models.meter import MeterCreate, MeterUpdate
from dataclasses import fields
import logging

router = APIRouter(tags=["meters"])
logger = logging.getLogger(__name__)

@router.get("/project/{project_id}")
def get_meters(project_id: int, svc: ProjectService = Depends(get_project_service)):
    """Lấy danh sách meter theo project."""
    try:
        return svc.get_meters_by_project(project_id)
    except Exception as e:
        logger.error(f"get_meters error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@router.post("/")
def create_meter(
    svc: ProjectService = Depends(get_project_service),
    body: dict = Body(..., example={
        "project_id": 1,
        "brand": "Chint",
        "model": "DTSU666",
        "serial_number": "MTR_1_123456",
        "slave_id": 1,
        "comm_id": 1
    })
):
    """Tạo mới meter thủ công."""
    try:
        # Lọc các trường hợp lệ cho MeterCreate
        valid_fields = {f.name for f in fields(MeterCreate)}
        filtered_body = {k: v for k, v in body.items() if k in valid_fields and k != "id"}
        
        logger.info(f"create_meter body: {filtered_body}")
        meter_id = svc.create_meter(MeterCreate(**filtered_body))
        return {"ok": True, "id": meter_id}
    except Exception as e:
        logger.error(f"create_meter error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@router.patch("/{meter_id}")
def update_meter(
    meter_id: int,
    svc: ProjectService = Depends(get_project_service),
    body: dict = Body(..., example={
        "brand": "Chint",
        "model": "DTSU666"
    })
):
    """Cập nhật thông tin meter."""
    try:
        valid_fields = {f.name for f in fields(MeterUpdate)}
        filtered_body = {k: v for k, v in body.items() if k in valid_fields and k != "id"}
        
        svc.update_meter(meter_id, MeterUpdate(**filtered_body))
        return {"ok": True}
    except Exception as e:
        logger.error(f"update_meter error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@router.delete("/{meter_id}")
def delete_meter(meter_id: int, svc: ProjectService = Depends(get_project_service)):
    """Xoá meter."""
    try:
        svc.delete_meter(meter_id)
        return {"ok": True}
    except Exception as e:
        logger.error(f"delete_meter error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
