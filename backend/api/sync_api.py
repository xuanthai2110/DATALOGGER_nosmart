from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from backend.db_manager import MetadataDB
from backend.api.auth_api import get_current_user, get_db
from backend.core import config as app_config
import requests
import logging
from dataclasses import asdict

router = APIRouter(prefix="/api/sync", tags=["sync"])
logger = logging.getLogger(__name__)

SERVER_URL = app_config.API_BASE_URL

@router.post("/project/{project_id}")
async def sync_project(project_id: int, current_user = Depends(get_current_user), db: MetadataDB = Depends(get_db)):
    # 1. Get project data
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 2. Get inverters for this project
    inverters = db.get_inverters_by_project(project_id)
    
    # 3. Prepare payload
    # Note: The server expects a specific format. Based on instructions:
    # Admin -> /api/project/
    # User -> /api/inverters/requests/
    
    payload = {
        "project": asdict(project),
        "inverters": [asdict(inv) for inv in inverters]
    }
    
    # Remove local IDs from payload to avoid confusion on server
    payload["project"].pop("id", None)
    for inv in payload["inverters"]:
        inv.pop("id", None)
        inv.pop("project_id", None)

    headers = {
        "Content-Type": "application/json"
    }
    # In a real scenario, we might need a server-side token here.
    # The uploader_service uses AuthService to get a token for the central server.
    from backend.services.auth_service import AuthService
    auth_service = AuthService()
    server_token = auth_service.get_access_token()
    if server_token:
        headers["Authorization"] = f"Bearer {server_token}"

    try:
        if current_user["role"] == "admin":
            url = f"{SERVER_URL}/api/project/"
            logger.info(f"Admin syncing project {project_id} to {url}")
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code in [200, 201]:
                res_data = response.json()
                server_id = res_data.get("server_id") or res_data.get("id")
                if server_id:
                    db.update_project_sync(project_id, server_id=server_id, status='approved')
                    # Also update inverters if server returned their IDs, or just mark as approved
                    for inv in inverters:
                        db.update_inverter_sync(inv.id, status='approved')
                    return {"ok": True, "server_id": server_id, "message": "Project synced and approved by Admin"}
            
            logger.error(f"Sync failed (Admin): {response.status_code} - {response.text}")
            raise HTTPException(status_code=response.status_code, detail=f"Server error: {response.text}")
            
        else: # User role
            url = f"{SERVER_URL}/api/inverters/requests/"
            logger.info(f"User syncing project {project_id} to {url}")
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code in [200, 201, 202]:
                res_data = response.json()
                request_id = res_data.get("server_request_id") or res_data.get("id")
                if request_id:
                    db.update_project_sync(project_id, server_request_id=request_id, status='pending')
                    for inv in inverters:
                        db.update_inverter_sync(inv.id, status='pending')
                    return {"ok": True, "server_request_id": request_id, "message": "Project sync request sent, pending approval"}

            logger.error(f"Sync failed (User): {response.status_code} - {response.text}")
            raise HTTPException(status_code=response.status_code, detail=f"Server error: {response.text}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Connection error during sync: {e}")
        raise HTTPException(status_code=503, detail="Could not connect to central server")
