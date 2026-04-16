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
    
    # 2. Gửi yêu cầu đồng bộ Project mới
    if not svc.auth.get_access_token():
        raise HTTPException(status_code=401, detail="Cloud authentication failed. Please check your credentials in .env")

    request_id = svc.initiate_project_sync(project_id)
    if request_id == -1:
        return {"ok": True, "message": "Project is already up-to-date with the server. No changes detected."}
    if not request_id:
        raise HTTPException(status_code=502, detail="Cloud server rejected the project request or is unreachable.")
    
    # 3. Chạy polling trong background để theo dõi kết quả phê duyệt
    background_tasks.add_task(svc.background_poll_status, request_id, project_id)
    
    return {
        "ok": True, 
        "server_request_id": request_id, 
        "message": "Yêu cầu đồng bộ đã gửi. Vui lòng liên hệ Admin (0836684169) để được duyệt nhanh."
    }

@router.post("/inverter/{inverter_id}")
async def sync_inverter(
    inverter_id: int, 
    svc: SetupService = Depends(get_setup_service)
):
    if not svc.auth.get_access_token():
        raise HTTPException(status_code=401, detail="Cloud authentication failed.")

    request_id = svc.initiate_inverter_sync(inverter_id)
    if request_id == -1:
        return {"ok": True, "message": "Inverter is already up-to-date with the server. No changes detected."}
    if not request_id:
        raise HTTPException(status_code=502, detail="Cloud server rejected the inverter request. Ensure project is synced first.")
    
    return {
        "ok": True, 
        "server_request_id": request_id, 
        "message": "Inverter sync request sent."
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

@router.post("/project/{project_id}/delete")
async def sync_delete_project(
    project_id: int, 
    svc: SetupService = Depends(get_setup_service)
):
    if not svc.auth.get_access_token():
        raise HTTPException(status_code=401, detail="Cloud authentication failed.")

    success = svc.request_delete_project_sync(project_id)
    if not success:
        raise HTTPException(status_code=502, detail="Cloud server rejected the delete request.")
    
    return {"ok": True, "message": "Project delete request sent successfully."}

@router.post("/inverter/{inverter_id}/delete")
async def sync_delete_inverter(
    inverter_id: int, 
    svc: SetupService = Depends(get_setup_service)
):
    if not svc.auth.get_access_token():
        raise HTTPException(status_code=401, detail="Cloud authentication failed.")

    success = svc.request_delete_inverter_sync(inverter_id)
    if not success:
        raise HTTPException(status_code=502, detail="Cloud server rejected the delete request.")
    
    return {"ok": True, "message": "Inverter delete request sent successfully."}
