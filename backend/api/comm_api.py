from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List
from backend.models.comm import CommConfig
from backend.services.comm_service import CommService
from backend.core import settings as app_config
import logging

def get_comm_service() -> CommService:
    from backend.db_manager import MetadataDB
    return CommService(metadata_db=MetadataDB(app_config.METADATA_DB))

router = APIRouter(prefix="/api/comm", tags=["comm"])
logger = logging.getLogger(__name__)

@router.get("", response_model=List[CommConfig])
def list_comm_configs(svc: CommService = Depends(get_comm_service)):
    """Lấy danh sách cấu hình kết nối."""
    try:
        return svc.get_comm()
    except Exception as e:
        logger.error(f"list_comm_configs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{config_id}", response_model=CommConfig)
def get_comm_id(config_id: int, svc: CommService = Depends(get_comm_service)):
    """Lấy thông tin một cấu hình kết nối theo ID."""
    try:
        config = svc.get_comm_id(config_id)
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
    svc: CommService = Depends(get_comm_service), 
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
        config_id = svc.post_comm(comm)
        return svc.get_comm_id(config_id)
    except Exception as e:
        logger.error(f"create_comm_config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{config_id}", response_model=CommConfig)
def patch_comm(
    config_id: int, 
    svc: CommService = Depends(get_comm_service),
    body: dict = Body(..., example={
        "host": "192.168.1.20",
        "timeout": 2.0
    })
):
    """Cập nhật từng phần cấu hình kết nối."""
    try:
        svc.patch_comm(config_id, body)
        config = svc.get_comm_id(config_id)
        if not config:
            raise HTTPException(status_code=404, detail="Communication config not found")
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"patch_comm_config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/reset")
def reset_comm_configs_endpoint(svc: CommService = Depends(get_comm_service)):
    """Xoá toàn bộ cấu hình kết nối và đưa ID về 1."""
    try:
        svc.reset_comm()
        return {"ok": True, "message": "All communication configurations cleared and sequence reset."}
    except Exception as e:
        logger.error(f"reset_comm_configs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{config_id}")
def delete_comm(config_id: int, svc: CommService = Depends(get_comm_service)):
    """Xoá cấu hình kết nối."""
    try:
        svc.delete_comm(config_id)
        return {"ok": True, "message": "Deleted successfully"}
    except Exception as e:
        logger.error(f"delete_comm_config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/available-ports")
def get_available_ports(svc: CommService = Depends(get_comm_service)):
    """Lấy danh sách các cổng serial vật lý trên máy."""
    try:
        return svc.get_available_ports()
    except Exception as e:
        logger.error(f"get_available_ports error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
