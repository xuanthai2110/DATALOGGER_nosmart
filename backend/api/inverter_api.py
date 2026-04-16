"""
web/routes/inverter_route.py — CRUD routes cho Inverters
"""

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from backend.services.project_service import ProjectService
from backend.models.inverter import InverterCreate, InverterUpdate
from dataclasses import asdict, fields
import logging
from backend.core import settings as app_config

router = APIRouter(tags=["inverters"])
logger = logging.getLogger(__name__)

def get_project_service() -> ProjectService:
    from backend.db_manager import MetadataDB, RealtimeDB
    return ProjectService(MetadataDB(app_config.METADATA_DB), RealtimeDB(app_config.REALTIME_DB))


@router.get("")
def list_inverters(svc: ProjectService = Depends(get_project_service)):
    """Trả về tất cả thông tin của tất cả inverter."""
    try:
        inverters = svc.get_inverter()
        return [asdict(i) for i in inverters]
    except Exception as e:
        logger.error(f"list_inverters error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/{inverter_id}")
def get_inverter_id(inverter_id: int, svc: ProjectService = Depends(get_project_service)):
    """Trả về thông tin của inverter có id tương ứng."""
    try:
        inv = svc.get_inverter_id(inverter_id)
        if not inv:
            return JSONResponse(status_code=404, content={"detail": [{"loc": ["path", "inverter_id"], "msg": "Inverter not found", "type": "not_found"}]})
        return asdict(inv)
    except Exception as e:
        logger.error(f"get_inverter error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("")
def create_inverter(
    svc: ProjectService = Depends(get_project_service),
    body: dict = Body(..., example={
    "project_id": 1,
    "brand": "Huawei",
    "model": "SUN2000-110KTL",
    "serial_number": "HV1234567890",
    "capacity_kw": 110.0,
    "mppt_count": 10,
    "phase_count": 3,
    "string_count": 20,
    "rate_dc_kwp": 120.0,
    "rate_ac_kw": 110.0,
    "is_active": True,
    "slave_id": 1
})):
    """Tạo inverter mới trong local DB qua Service."""
    try:
        # Lọc các trường hợp lệ cho InverterCreate
        valid_fields = {f.name for f in fields(InverterCreate)}
        filtered_body = {k: v for k, v in body.items() if k in valid_fields and k != "id"}
        
        inv_id = svc.upsert_inverter(InverterCreate(**filtered_body))
        inv = svc.get_inverter_id(inv_id)
        return asdict(inv)
    except Exception as e:
        logger.error(f"create_inverter error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.patch("/{inverter_id}")
def update_inverter(
    inverter_id: int,
    svc: ProjectService = Depends(get_project_service),
    body: dict = Body(..., example={
    "capacity_kw": 115.0,
    "is_active": False
})):
    """Cập nhật thông tin của inverter có id tương ứng qua Service."""
    try:
        # Lọc các trường hợp lệ cho InverterUpdate
        valid_fields = {f.name for f in fields(InverterUpdate)}
        filtered_body = {k: v for k, v in body.items() if k in valid_fields and k != "id"}
        
        svc.patch_inverter(inverter_id, InverterUpdate(**filtered_body))
        inv = svc.get_inverter_id(inverter_id)
        if not inv:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Inverter not found"})
        return asdict(inv)
    except Exception as e:
        logger.error(f"update_inverter error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.delete("/{inverter_id}")
def delete_inverter(inverter_id: int, svc: ProjectService = Depends(get_project_service)):
    """Xoá inverter có id tương ứng qua Service."""
    try:
        from backend.api.sync_api import get_setup_service
        setup_svc = get_setup_service()
        setup_svc.request_delete_inverter_sync(inverter_id)
        
        svc.delete_inverter(inverter_id)
        return {"message": "Inverter deleted successfully"}
    except Exception as e:
        logger.error(f"delete_inverter error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
