from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from backend.services.setup_service import SetupService
from backend.core import settings as app_config

def get_setup_service() -> SetupService:
    from backend.db_manager import MetadataDB, RealtimeDB
    from backend.services.project_service import ProjectService
    from backend.services.auth_service import AuthService
    
    metadata_db = MetadataDB(app_config.METADATA_DB)
    realtime_db = RealtimeDB(app_config.REALTIME_DB)
    project_svc = ProjectService(metadata_db, realtime_db)
    auth_svc = AuthService()
    return SetupService(auth_svc, project_svc)

router = APIRouter(prefix="/api/sync", tags=["sync"])

@router.post("/project/{project_id}")
async def sync_project(
    project_id: int, 
    background_tasks: BackgroundTasks, 
    svc: SetupService = Depends(get_setup_service)
):
    # 1. Kiểm tra xem đã có trên server chưa (Pre-sync check)
    if svc.pre_sync_check(project_id):
        return {"ok": True, "message": "Project matched and approved automatically from server."}
    
    # 2. Nếu chưa có, gửi yêu cầu đồng bộ mới (Dự án + Biến tần)
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
async def stop_sync(
    project_id: int, 
    svc: SetupService = Depends(get_setup_service)
):
    success = svc.cancel_sync(project_id)
    if not success:
        raise HTTPException(status_code=400, detail="Could not cancel sync (maybe no pending request exists).")
    return {"ok": True, "message": "Sync request cancelled and local status reset."}
