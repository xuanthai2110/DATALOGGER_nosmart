from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from backend.services.project_service import ProjectService
from backend.api.auth_api import get_current_user
from backend.core import config as app_config

def get_project_service() -> ProjectService:
    from backend.db_manager import MetadataDB, RealtimeDB
    return ProjectService(MetadataDB(app_config.METADATA_DB), RealtimeDB(app_config.REALTIME_DB))
import requests
import logging
from dataclasses import asdict

router = APIRouter(prefix="/api/sync", tags=["sync"])
logger = logging.getLogger(__name__)

SERVER_URL = app_config.API_BASE_URL

@router.post("/project/{project_id}")
async def sync_project(project_id: int, background_tasks: BackgroundTasks, svc: ProjectService = Depends(get_project_service)):
    # 1. Kiểm tra xem đã có trên server chưa (Pre-sync check)
    # So khớp bằng elec_meter_no và serial_number
    if svc.pre_sync_check(project_id):
        return {"ok": True, "message": "Project matched and approved automatically from server."}
    
    # 2. Nếu chưa có, gửi yêu cầu đồng bộ mới
    request_id = svc.initiate_sync_request(project_id)
    if not request_id:
        raise HTTPException(status_code=500, detail="Failed to initiate sync request to server.")
    
    # 3. Chạy polling trong background để theo dõi kết quả phê duyệt
    background_tasks.add_task(svc.background_poll_status, request_id, project_id)
    
    return {
        "ok": True, 
        "server_request_id": request_id, 
        "message": "Sync request sent. Waiting for Admin approval. Polling started in background."
    }

@router.delete("/project/{project_id}/stop")
async def stop_sync(project_id: int, svc: ProjectService = Depends(get_project_service)):
    success = svc.cancel_sync(project_id)
    if not success:
        raise HTTPException(status_code=400, detail="Could not cancel sync (maybe no pending request exists).")
    return {"ok": True, "message": "Sync request cancelled and local status reset."}
