from fastapi import APIRouter, Depends, HTTPException, Body
from backend.database import MetadataDB
from backend.models.comm import CommConfig
from backend.api.auth_api import get_db
from typing import List
import logging
from backend.core import config as app_config

router = APIRouter(prefix="/api/comm", tags=["comm"])
logger = logging.getLogger(__name__)

@router.get("", response_model=List[CommConfig])
def list_comm_configs(db: MetadataDB = Depends(get_db)):
    """Lấy danh sách cấu hình kết nối."""
    try:
        return db.get_comm()
    except Exception as e:
        logger.error(f"list_comm_configs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{config_id}", response_model=CommConfig)
def get_comm_id(config_id: int, db: MetadataDB = Depends(get_db)):
    """Lấy thông tin một cấu hình kết nối theo ID."""
    try:
        config = db.get_comm_id(config_id)
        if not config:
            raise HTTPException(status_code=404, detail="Communication config not found")
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_comm_config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", response_model=CommConfig)
def create_comm_config(
    db: MetadataDB = Depends(get_db), 
    body: dict = Body(..., example={
        "driver": "Huawei",
        "comm_type": "TCP",
        "host": "192.168.1.10",
        "port": 502,
        "com_port": "/dev/ttyUSB0",
        "baudrate": 9600,
        "databits": 8,
        "parity": "N",
        "stopbits": 1,
        "timeout": 1.0,
        "slave_id_start": 1,
        "slave_id_end": 10
    })
):
    """Tạo cấu hình kết nối mới."""
    try:
        # We use dict for body to allow flex then convert to CommConfig
        comm = CommConfig(**body)
        config_id = db.post_comm(comm)
        return db.get_comm_id(config_id)
    except Exception as e:
        logger.error(f"create_comm_config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{config_id}", response_model=CommConfig)
def patch_comm(
    config_id: int, 
    db: MetadataDB = Depends(get_db),
    body: dict = Body(..., example={
        "host": "192.168.1.20",
        "timeout": 2.0
    })
):
    """Cập nhật từng phần cấu hình kết nối."""
    try:
        db.patch_comm(config_id, body)
        config = db.get_comm_id(config_id)
        if not config:
            raise HTTPException(status_code=404, detail="Communication config not found")
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"patch_comm_config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/reset")
def reset_comm_configs_endpoint(db: MetadataDB = Depends(get_db)):
    """Xoá toàn bộ cấu hình kết nối và đưa ID về 1."""
    try:
        db.reset_comm()
        return {"ok": True, "message": "All communication configurations cleared and sequence reset."}
    except Exception as e:
        logger.error(f"reset_comm_configs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{config_id}")
def delete_comm(config_id: int, db: MetadataDB = Depends(get_db)):
    """Xoá cấu hình kết nối."""
    try:
        db.delete_comm(config_id)
        return {"ok": True, "message": "Deleted successfully"}
    except Exception as e:
        logger.error(f"delete_comm_config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
