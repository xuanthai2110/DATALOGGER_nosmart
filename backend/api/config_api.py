from fastapi import APIRouter, Depends, HTTPException, Body
from backend.config_manager import load_config, save_config
from backend.api.auth_api import get_current_user_id
import logging

router = APIRouter(tags=["config"])
logger = logging.getLogger(__name__)

@router.get("/current")
def get_config(current_user: str = Depends(get_current_user_id)):
    """Trả về cấu hình hiện tại (config.py + DB merged)."""
    try:
        return load_config()
    except Exception as e:
        logger.error(f"get_config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update")
def update_config(data: dict = Body(..., example={
    "project": {
        "name": "Updated Project Name",
        "capacity_kwp": 150.0
    },
    "comm": {
        "host": "192.168.1.100",
        "port": 502
    }
}), current_user: str = Depends(get_current_user_id)):
    """Lưu cấu hình mới vào database."""
    try:
        save_config(data)
        return {"ok": True, "message": "Config saved successfully."}
    except Exception as e:
        logger.error(f"update_config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
