from fastapi import APIRouter, Depends, HTTPException, Body
from backend.db_manager import MetadataDB
from backend.api.auth_api import get_current_user_id
from backend.core import settings as app_config
from backend.models.project import ProjectCreate
from backend.models.comm import CommConfig
from backend.models.inverter import InverterCreate
from backend.services.config_service import ConfigService
import logging

router = APIRouter(tags=["config"])
logger = logging.getLogger(__name__)

def get_config_service() -> ConfigService:
    from backend.db_manager import MetadataDB
    return ConfigService(metadata_db=MetadataDB(app_config.METADATA_DB))

@router.get("/current")
def get_config(svc: ConfigService = Depends(get_config_service)):
    """Trả về cấu hình hiện tại (ánh xạ từ MetadataDB cho Frontend cũ)."""
    try:
        return svc.get_legacy_config()
    except Exception as e:
        logger.error(f"get_config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update")
def update_config(data: dict = Body(...), svc: ConfigService = Depends(get_config_service)):
    """Lưu cấu hình nhận từ Frontend cũ và nhồi vào MetadataDB chuẩn."""
    try:
        svc.update_legacy_config(data)
        return {"ok": True, "message": "Config saved successfully to DB."}
    except Exception as e:
        logger.error(f"update_config error: {e}")
        import sys
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
