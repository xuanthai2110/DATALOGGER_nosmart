"""
web/routes/project_route.py — CRUD routes cho Projects
"""
from fastapi import APIRouter, Depends, Body
from fastapi.responses import JSONResponse
from database.sqlite_manager import MetadataDB
from schemas.project import ProjectCreate, ProjectResponse
from backend.api.auth_api import get_current_user_id
from dataclasses import asdict, fields
import logging
import config as app_config

router = APIRouter(tags=["projects"])
logger = logging.getLogger(__name__)


def get_db() -> MetadataDB:
    return MetadataDB(app_config.METADATA_DB)


@router.get("")
def list_projects(db: MetadataDB = Depends(get_db), current_user = Depends(get_current_user_id)):
    """Trả về toàn bộ danh sách project trong local DB."""
    try:
        projects = db.get_all_projects()
        return {"projects": [asdict(p) for p in projects]}
    except Exception as e:
        logger.error(f"list_projects error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("")
def create_project(body: dict = Body(..., example={
    "name": "Dự án Năng lượng Mặt trời A",
    "elec_meter_no": "MT123456",
    "elec_price_per_kwh": 1783.0,
    "location": "Hà Nội",
    "lat": 21.0285,
    "lon": 105.8542,
    "capacity_kwp": 120.5,
    "ac_capacity_kw": 100.0,
    "inverter_count": 2
})):
    """Tạo project mới trong local DB."""
    try:
        db = get_db()
        # Lọc các trường hợp lệ cho ProjectCreate
        valid_fields = {f.name for f in fields(ProjectCreate)}
        filtered_body = {k: v for k, v in body.items() if k in valid_fields and k != "id"}
        
        proj = db.upsert_project(ProjectCreate(**filtered_body))
        return asdict(proj)
    except Exception as e:
        logger.error(f"create_project error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, db: MetadataDB = Depends(get_db), current_user = Depends(get_current_user_id), body: dict = Body(..., example={
    "name": "Dự án Năng lượng Mặt trời A (Đã sửa)",
    "capacity_kwp": 150.0,
    "elec_price_per_kwh": 1800.0
})):
    """Cập nhật thông tin dự án (PATCH - hỗ trợ cập nhật từng trường)."""
    try:
        # Lọc các trường hợp lệ cho ProjectCreate
        valid_fields = {f.name for f in fields(ProjectCreate)}
        filtered_body = {k: v for k, v in body.items() if k in valid_fields and k != "id"}
        
        proj = db.upsert_project(ProjectCreate(**filtered_body), project_id=project_id)
        return asdict(proj)
    except Exception as e:
        logger.error(f"update_project error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.delete("/{project_id}")
def delete_project(project_id: int):
    """Xoá project và toàn bộ inverters thuộc về nó."""
    try:
        db = get_db()
        db.delete_project(project_id)
        return {"ok": True}
    except Exception as e:
        logger.error(f"delete_project error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
