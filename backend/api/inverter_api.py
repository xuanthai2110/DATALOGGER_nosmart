"""
web/routes/inverter_route.py — CRUD routes cho Inverters
"""

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from backend.services.project_service import ProjectService
from backend.models.inverter import InverterCreate, InverterUpdate
from dataclasses import asdict, fields
import logging
from backend.core import settings as app_config

router = APIRouter(tags=["inverters"])
logger = logging.getLogger(__name__)

def get_project_service() -> ProjectService:
    from backend.db_manager import MetadataDB, RealtimeDB
    return ProjectService(MetadataDB(app_config.METADATA_DB), RealtimeDB(app_config.REALTIME_DB))


def get_inverter_model_specs(brand: str, model: str, capacity_kw: float = None) -> dict:
    """Tra cứu thông số kỹ thuật tiêu chuẩn từ thư viện detect_service và catalog."""
    brand_lower = (brand or "").lower().strip()
    model_clean = (model or "").upper().strip()

    from backend.services.detect_service import SUNGROW_MODEL, HUAWEI_MODEL, GOODWE_MODEL
    target_list = []
    if "sungrow" in brand_lower:
        target_list = SUNGROW_MODEL
    elif "huawei" in brand_lower:
        target_list = HUAWEI_MODEL
    elif "goodwe" in brand_lower:
        target_list = GOODWE_MODEL
    else:
        target_list = SUNGROW_MODEL + HUAWEI_MODEL + GOODWE_MODEL

    matched = next((item for item in target_list if item["model"].upper() == model_clean), None)
    if not matched and model_clean:
        matched = next((item for item in target_list if model_clean in item["model"].upper() or item["model"].upper() in model_clean), None)

    specs = {
        "mppt_count": None,
        "strings_per_mppt": None,
        "string_count": None,
        "rate_ac_kw": None,
        "rate_dc_kwp": None,
        "phase_count": 3,
        "firmware_version": "V1.0"
    }

    if matched:
        try:
            mppt = matched.get("mppt", 1)
            str_mppt = str(matched.get("string_mppt", "1"))
            if ";" in str_mppt:
                total_strings = sum(int(x) for x in str_mppt.split(";") if x.isdigit())
                spm = None
            else:
                spm = int(str_mppt)
                total_strings = spm * mppt
            specs["mppt_count"] = mppt
            specs["strings_per_mppt"] = spm
            specs["string_count"] = total_strings
            specs["rate_ac_kw"] = float(matched.get("p_ac")) if matched.get("p_ac") is not None else None
            specs["rate_dc_kwp"] = float(matched.get("p_dc")) if matched.get("p_dc") is not None else None
        except Exception:
            pass

    if not specs["mppt_count"]:
        if "solis" in brand_lower:
            specs.update({"mppt_count": 10, "strings_per_mppt": 2, "string_count": 20, "rate_ac_kw": capacity_kw or 100.0, "rate_dc_kwp": (capacity_kw or 100.0) * 1.2})
        elif "goodwe" in brand_lower:
            specs.update({"mppt_count": 4, "strings_per_mppt": 2, "string_count": 8, "rate_ac_kw": capacity_kw or 80.0, "rate_dc_kwp": (capacity_kw or 80.0) * 1.25})
        elif "canadian" in brand_lower:
            specs.update({"mppt_count": 10, "strings_per_mppt": 2, "string_count": 20, "rate_ac_kw": capacity_kw or 110.0, "rate_dc_kwp": (capacity_kw or 110.0) * 1.2})

    if specs["rate_ac_kw"] is None and capacity_kw:
        specs["rate_ac_kw"] = float(capacity_kw)
    if specs["rate_dc_kwp"] is None and capacity_kw:
        specs["rate_dc_kwp"] = float(capacity_kw) * 1.2

    return specs


def _format_inverter_response(inv) -> dict:
    if inv is None:
        return None
    data = asdict(inv)
    # Ép kiểu is_active về bool chuẩn (True nếu = 1/True, False nếu = 0/False)
    data["is_active"] = bool(inv.is_active) if inv.is_active else False
    # Bổ sung alias status tương thích Web UI
    data["status"] = "Ngưng hoạt động" if not data["is_active"] else "Đang hoạt động"

    # Tự động bổ sung các thông số kỹ thuật nếu bị trống trong DB
    brand = data.get("brand")
    model = data.get("model")
    cap = data.get("capacity_kw")
    if brand or model:
        specs = get_inverter_model_specs(brand, model, cap)
        for field in ("mppt_count", "strings_per_mppt", "string_count", "rate_ac_kw", "rate_dc_kwp", "phase_count", "firmware_version"):
            val = data.get(field)
            if (val is None or val == "" or val == 0 or val == 0.0) and specs.get(field) is not None:
                data[field] = specs[field]

    return data


def _normalize_inverter_body(body: dict) -> dict:
    """Chuẩn hóa dữ liệu body truyền vào API (xử lý status, is_active, datetime string)."""
    normalized = body.copy()

    # 1. Ánh xạ các tên trường trạng thái
    status_val = None
    for k in ("is_active", "status", "state", "trang_thai"):
        if k in normalized and normalized[k] is not None:
            status_val = normalized[k]
            break

    if status_val is not None:
        if isinstance(status_val, bool):
            normalized["is_active"] = status_val
        elif isinstance(status_val, (int, float)):
            normalized["is_active"] = (status_val != 0)
        elif isinstance(status_val, str):
            s_lower = status_val.strip().lower()
            if s_lower in ("false", "0", "off", "disabled", "inactive", "ngưng hoạt động", "ngung hoat dong", "ngừng hoạt động", "tắt", "tat", "stopped"):
                normalized["is_active"] = False
            elif s_lower in ("true", "1", "on", "enabled", "active", "đang hoạt động", "dang hoat dong", "bật", "bat", "running"):
                normalized["is_active"] = True
            else:
                normalized["is_active"] = bool(status_val)

    # 2. Chuẩn hóa datetime & foreign keys
    for field in ("usage_start_at", "usage_end_at"):
        if field in normalized:
            val = normalized[field]
            if val in ("", 0, None):
                normalized[field] = None
            elif isinstance(val, str):
                s = val.strip().replace("Z", "").replace("T", " ")
                if "." in s:
                    s = s.split(".")[0]
                normalized[field] = s

    # Nếu ngưng hoạt động (is_active = False) mà chưa có usage_end_at, tự động điền thời gian hiện tại
    if normalized.get("is_active") is False and not normalized.get("usage_end_at"):
        from datetime import datetime
        normalized["usage_end_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if "replaced_by_id" in normalized:
        val = normalized["replaced_by_id"]
        if val == "" or val == 0 or val is None:
            normalized["replaced_by_id"] = None
        else:
            try:
                normalized["replaced_by_id"] = int(val)
            except (ValueError, TypeError):
                normalized["replaced_by_id"] = None

    return normalized


def _notify_polling_cache_refresh(svc: ProjectService):
    """Phát tín hiệu đặt cờ làm mới RAM Cache cho PollingWorker."""
    try:
        if svc and svc.metadata_db:
            svc.metadata_db.set_setting("clear_polling_cache", "true")
            logger.info("[InverterAPI] Triggered clear_polling_cache flag in DB.")
    except Exception as e:
        logger.warning(f"[InverterAPI] Failed to trigger clear_polling_cache: {e}")


@router.get("")
def list_inverters(svc: ProjectService = Depends(get_project_service)):
    """Trả về tất cả thông tin của tất cả inverter."""
    try:
        inverters = svc.get_all_inverters()
        return [_format_inverter_response(i) for i in inverters]
    except Exception as e:
        logger.error(f"list_inverters error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/specs")
def get_model_specs_endpoint(brand: str = "", model: str = "", capacity_kw: float = None):
    """API tra cứu thông số kỹ thuật chuẩn của Inverter theo Model & Brand."""
    specs = get_inverter_model_specs(brand, model, capacity_kw)
    return {"ok": True, "specs": specs}


@router.get("/{inverter_id}")
def get_inverter_id(inverter_id: int, svc: ProjectService = Depends(get_project_service)):
    """Trả về thông tin của inverter có id tương ứng."""
    try:
        inv = svc.get_inverter_by_id(inverter_id)
        if not inv:
            return JSONResponse(status_code=404, content={"detail": [{"loc": ["path", "inverter_id"], "msg": "Inverter not found", "type": "not_found"}]})
        return _format_inverter_response(inv)
    except Exception as e:
        logger.error(f"get_inverter error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("")
def create_inverter(
    svc: ProjectService = Depends(get_project_service),
    body: dict = Body(..., example={
    "project_id": 1,
    "brand": "Huawei",
    "model": "SUN2000-110KTL",
    "serial_number": "HV1234567890",
    "capacity_kw": 110.0,
    "mppt_count": 10,
    "phase_count": 3,
    "string_count": 20,
    "rate_dc_kwp": 120.0,
    "rate_ac_kw": 110.0,
    "is_active": True,
    "slave_id": 1
})):
    """Tạo inverter mới trong local DB qua Service."""
    try:
        norm_body = _normalize_inverter_body(body)
        valid_fields = {f.name for f in fields(InverterCreate)}
        filtered_body = {k: v for k, v in norm_body.items() if k in valid_fields and k != "id"}
        
        inv_id = svc.upsert_inverter(InverterCreate(**filtered_body))
        _notify_polling_cache_refresh(svc)
        inv = svc.get_inverter_by_id(inv_id)
        return _format_inverter_response(inv)
    except Exception as e:
        logger.error(f"create_inverter error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.patch("/{inverter_id}")
def update_inverter(
    inverter_id: int,
    svc: ProjectService = Depends(get_project_service),
    body: dict = Body(..., example={
    "capacity_kw": 115.0,
    "is_active": False
})):
    """Cập nhật thông tin của inverter có id tương ứng qua Service."""
    try:
        norm_body = _normalize_inverter_body(body)
        valid_fields = {f.name for f in fields(InverterUpdate)}
        filtered_body = {k: v for k, v in norm_body.items() if k in valid_fields and k != "id"}
        
        svc.patch_inverter(inverter_id, InverterUpdate(**filtered_body))
        _notify_polling_cache_refresh(svc)
        inv = svc.get_inverter_by_id(inverter_id)
        if not inv:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Inverter not found"})
        return _format_inverter_response(inv)
    except Exception as e:
        logger.error(f"update_inverter error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.delete("/{inverter_id}")
def delete_inverter(inverter_id: int, svc: ProjectService = Depends(get_project_service)):
    """Xoá inverter có id tương ứng qua Service."""
    try:
        from backend.api.sync_api import get_setup_service
        setup_svc = get_setup_service()
        setup_svc.request_delete_inverter_sync(inverter_id)
        
        svc.delete_inverter(inverter_id)
        _notify_polling_cache_refresh(svc)
        return {"message": "Inverter deleted successfully"}
    except Exception as e:
        logger.error(f"delete_inverter error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
