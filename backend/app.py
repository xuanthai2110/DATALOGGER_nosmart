"""
backend/app.py — FastAPI Backend with WebSocket support
"""
import sys
import logging
from pathlib import Path
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api.config_api import router as config_router
from backend.api.scan_api import router as scan_router
from backend.api.project_api import router as project_router
from backend.api.inverter_api import router as inverter_router
from backend.api.auth_api import router as auth_router, get_current_user_id
from backend.api.user_api import router as user_router
from backend.api.monitoring_api import router as monitoring_router
from backend.api.comm_api import router as comm_router
from backend.api.sync_api import router as sync_router

from backend.db_manager import MetadataDB
from backend.models.user import UserCreate
from backend.services.local_auth_utils import hash_password
from backend.core import config as app_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Solar Datalogger Backend", version="2.0.0")

# API routes
app.include_router(auth_router)
app.include_router(config_router, prefix="/api/config", dependencies=[Depends(get_current_user_id)])
app.include_router(scan_router, prefix="/api/scan", dependencies=[Depends(get_current_user_id)])
app.include_router(project_router, prefix="/api/projects", dependencies=[Depends(get_current_user_id)])
app.include_router(inverter_router, prefix="/api/inverters", dependencies=[Depends(get_current_user_id)])
app.include_router(comm_router, dependencies=[Depends(get_current_user_id)])
app.include_router(user_router) 
app.include_router(monitoring_router, prefix="/api/monitoring", dependencies=[Depends(get_current_user_id)])
app.include_router(sync_router, dependencies=[Depends(get_current_user_id)])

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.on_event("startup")
def startup_event():
    """Initialize system."""
    db = MetadataDB(app_config.METADATA_DB)
    if not db.get_user_by_username("admin"):
        logger.info("Initializing default admin user...")
        # Note: In real app, avoid hardcoded password in code
        pass

# Static files for SPA
STATIC_DIR = Path(__file__).resolve().parent / "static"
if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", include_in_schema=False)
def index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Datalogger API is running. Frontend not found."}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Solar Datalogger Backend on http://0.0.0.0:5000")
    uvicorn.run("backend.app:app", host="0.0.0.0", port=5000, reload=True)
