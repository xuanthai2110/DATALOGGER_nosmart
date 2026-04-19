"""
backend/api/evn_api.py — API for global EVN configuration.
"""
from fastapi import APIRouter, Depends, Body
from backend.services.setup_service import SetupService
from backend.api.scan_api import get_setup_service
import logging

router = APIRouter(tags=["evn"])
logger = logging.getLogger(__name__)

@router.get("/settings")
def get_evn_settings(setup_svc: SetupService = Depends(get_setup_service)):
    """Lấy cấu hình EVN toàn cục."""
    return setup_svc.get_evn_settings()

@router.post("/settings")
def update_evn_settings(
    setup_svc: SetupService = Depends(get_setup_service),
    body: dict = Body(...)
):
    """Cập nhật cấu hình EVN toàn cục."""
    host = body.get("host")
    port = int(body.get("port", 502))
    enabled = body.get("enabled", False)
    
    setup_svc.update_evn_settings(host, port, enabled)
    return {"ok": True, "message": "EVN settings updated successfully"}
