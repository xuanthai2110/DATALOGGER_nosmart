"""
web/routes/scan_route.py — POST /api/scan
Refactored to support background scanning and cancellation.
"""
from fastapi import APIRouter, Body, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from backend.services.setup_service import SetupService
from dataclasses import asdict
from backend.models.inverter import InverterCreate
import logging
import time
import threading
import os
import importlib
from backend.core import settings as app_config

def get_project_service():
    from backend.db_manager import MetadataDB, RealtimeDB
    from backend.services.project_service import ProjectService
    return ProjectService(MetadataDB(app_config.METADATA_DB), RealtimeDB(app_config.REALTIME_DB))

router = APIRouter(tags=["scan"])
logger = logging.getLogger(__name__)

def _get_driver_filename(brand: str, model: str) -> str:
    clean_model = model.lower().replace("-", "_").replace(".", "_")
    return f"{brand.lower()}_{clean_model}.py"

def normalize_type_code(tc):
    if tc is None: return None
    if isinstance(tc, int): return tc
    if isinstance(tc, str):
        tc = tc.strip()
        if tc.lower().startswith("0x"):
            try: return int(tc, 16)
            except: pass
        else:
            try: return int(tc)
            except: pass
    return tc

@router.get("/models")
def get_models():
    try:
        from backend.services.detect_service import SUNGROW_MODEL, HUAWEI_MODEL
        drivers_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "drivers")
        existing_files = set(os.listdir(drivers_dir))

        valid_sungrow = [m["model"] for m in SUNGROW_MODEL if _get_driver_filename("Sungrow", m["model"]) in existing_files]
        valid_huawei = [m["model"] for m in HUAWEI_MODEL if _get_driver_filename("Huawei", m["model"]) in existing_files]

        return {
            "Sungrow": sorted(list(set(valid_sungrow))),
            "Huawei": sorted(list(set(valid_huawei)))
        }
    except Exception as e:
        logger.error(f"[scan/models] Error: {e}")
        return {"Sungrow": [], "Huawei": []}

# Global state for scanning
class ScanState:
    def __init__(self):
        self.is_running = False
        self.stop_requested = False
        self.progress = 0  # Current Slave ID
        self.total = 0     # End Slave ID
        self.results = []
        self.error = None
        self.lock = threading.Lock()

scan_state = ScanState()

def _get_driver_class(driver_name: str, brand: str = None, model: str = None):
    if brand and model:
        # Dynamic import: e.g. sungrow_sg110cx.py -> Sungrowsg110cx
        clean_model_mod = model.lower().replace("-", "_").replace(".", "_")
        module_name = f"backend.drivers.{brand.lower()}_{clean_model_mod}"
        clean_model_class = model.replace("-", "").replace(".", "").lower()
        class_name = f"{brand.capitalize()}{clean_model_class}"
        try:
            module = importlib.import_module(module_name)
            return getattr(module, class_name)
        except Exception as e:
            logger.error(f"Cannot load dynamic driver {module_name}.{class_name}: {e}")
            # Fallback will raise error below if we can't load it
            raise ValueError(f"Driver logic class not found for {brand} {model}")

    # Fallback to old behavior
    if driver_name == "Huawei":
        from backend.drivers.huawei_sun2000_110ktl import Huaweisun2000110ktl
        return Huaweisun2000110ktl
    elif driver_name == "Sungrow":
        from backend.drivers.sungrow_sg110cx import Sungrowsg110cx
        return Sungrowsg110cx
    raise ValueError(f"Unknown driver: {driver_name}")

def _get_transport(comm: dict):
    if comm["comm_type"] == "TCP":
        from backend.communication.modbus_tcp import ModbusTCP
        t = ModbusTCP(
            host=comm["host"], 
            port=comm.get("port", 502),
            timeout=comm.get("timeout", 1.0)
        )
        t.connect()
        return t
    else:
        from backend.communication.modbus_rtu import ModbusRTU
        t = ModbusRTU(
            port=comm["com_port"],
            baudrate=comm.get("baudrate", 9600),
            bytesize=comm.get("databits", 8),
            parity=comm.get("parity", "N"),
            stopbits=comm.get("stopbits", 1),
            timeout=comm.get("timeout", 1.0),
        )
        t.connect()
        return t

def background_scan(comm: dict):
    global scan_state
    
    driver_name = comm.get("driver", "Huawei")
    brand_selected = comm.get("brand")
    model_selected = comm.get("model")
    slave_start = int(comm.get("slave_id_start", 1))
    slave_end = int(comm.get("slave_id_end", 30))
    
    # Retrieve detect info if specified
    detect_info = None
    if brand_selected and model_selected:
        try:
            from backend.services.detect_service import SUNGROW_MODEL, HUAWEI_MODEL
            if brand_selected.lower() == "sungrow":
                detect_info = next((m for m in SUNGROW_MODEL if m["model"] == model_selected), None)
            elif brand_selected.lower() == "huawei":
                detect_info = next((m for m in HUAWEI_MODEL if m["model"] == model_selected), None)
        except Exception as e:
            logger.error(f"Error loading models from detect_service: {e}")

    with scan_state.lock:
        scan_state.is_running = True
        scan_state.stop_requested = False
        scan_state.progress = slave_start
        scan_state.total = slave_end
        scan_state.results = []
        scan_state.error = None

    transport = None
    try:
        DriverClass = _get_driver_class(driver_name, brand_selected, model_selected)
        transport = _get_transport(comm)
        
        for slave_id in range(slave_start, slave_end + 1):
            with scan_state.lock:
                if scan_state.stop_requested:
                    logger.info("[Scan] Cancellation requested by user.")
                    break
                scan_state.progress = slave_id

            success = False
            for attempt in range(2):
                try:
                    driver = DriverClass(transport, slave_id=slave_id)
                    info = driver.read_info()
                    # Check serial_number AND is_active (Huawei driver returns is_active=False on error)
                    if info and info.get("serial_number") and info.get("is_active", True):
                        
                        # If detect info exists, match type_code before appending
                        if detect_info:
                            hw_tc = normalize_type_code(info.get("type_code"))
                            ex_tc = normalize_type_code(detect_info.get("type_code"))
                            
                            if hw_tc is not None and ex_tc is not None and hw_tc != ex_tc:
                                logger.warning(f"[Scan] Slave {slave_id} rejected: Hardware TypeCode {info.get('type_code')} != Expected {detect_info.get('type_code')}")
                                continue  # Reject and move to next iteration
                            
                            try:
                                str_mppt = detect_info.get("string_mppt", "1")
                                total_strings = sum(int(x) for x in str_mppt.split(";") if x.isdigit())
                            except Exception:
                                total_strings = 1
                            
                            info["mppt_count"] = detect_info.get("mppt")
                            info["string_count"] = total_strings
                            info["capacity_kw"] = detect_info.get("p_ac")
                            info["rate_ac_kw"] = detect_info.get("p_ac")
                            info["rate_dc_kwp"] = detect_info.get("p_dc")
                            # override brand and model if user manually selected them
                            info["brand"] = brand_selected
                            info["model"] = model_selected
                            
                            logger.info(f"[Scan] TypeCode valid: {ex_tc}")

                        info["slave_id"] = slave_id
                        with scan_state.lock:
                            scan_state.results.append(info)
                        logger.info(f"[Scan] Found inverter at slave {slave_id}: {info.get('serial_number')}")
                        success = True
                        break
                except Exception as e:
                    logger.debug(f"[Scan] No inverter at slave {slave_id} (Attempt {attempt+1}): {e}")
                
                if not success and attempt == 0:
                    time.sleep(0.5)

    except Exception as e:
        logger.error(f"[Scan] Critical error: {e}", exc_info=True)
        with scan_state.lock:
            scan_state.error = str(e)
    finally:
        if transport:
            try: transport.close()
            except: pass
        with scan_state.lock:
            scan_state.is_running = False
            logger.info(f"[Scan] Finished. Found {len(scan_state.results)} inverters.")

@router.post("/start")
def start_scan(background_tasks: BackgroundTasks, body: dict = Body(default=None)):
    global scan_state
    
    with scan_state.lock:
        if scan_state.is_running:
            return JSONResponse(status_code=400, content={"ok": False, "error": "A scan is already in progress."})
    
    from backend.api.comm_api import get_comm_service
    svc = get_comm_service()
    comms = svc.get_comm_config()
    comm = asdict(comms[-1]) if comms else {
        "comm_type": "TCP", "host": "127.0.0.1", "port": 502, "driver": "Huawei",
        "slave_id_start": 1, "slave_id_end": 30
    }
    
    if body and "comm" in body:
        comm.update(body["comm"])

    background_tasks.add_task(background_scan, comm)
    return {"ok": True, "message": "Scan started in background."}

@router.get("/status")
def get_scan_status():
    global scan_state
    with scan_state.lock:
        return {
            "is_running": scan_state.is_running,
            "progress": scan_state.progress,
            "total": scan_state.total,
            "found_count": len(scan_state.results),
            "inverters": scan_state.results,
            "error": scan_state.error,
            "stop_requested": scan_state.stop_requested
        }

@router.post("/stop")
def stop_scan():
    global scan_state
    with scan_state.lock:
        if scan_state.is_running:
            scan_state.stop_requested = True
            return {"ok": True, "message": "Stop requested."}
        return {"ok": False, "message": "No scan running."}

@router.post("/save")
def save_inverters(body: dict = Body(...)):
    try:
        svc = get_project_service()
        inverters_in = body.get("inverters", [])
        saved = 0
        for inv in inverters_in:
            project_id = inv.get("project_id")
            if not project_id: continue
            
            # Gán inverter_index tự động nếu chưa có
            if not inv.get("inverter_index"):
                existing = svc.metadata_db.get_inverters_by_project(project_id)
                next_idx = max((x.inverter_index for x in existing if x.inverter_index is not None), default=0) + 1
                inv["inverter_index"] = next_idx
                logger.info(f"[Scan] Auto-assigned inverter_index={next_idx} for inverter SN={inv.get('serial_number')}")

            svc.metadata_db.upsert_inverter(InverterCreate(**inv))
            saved += 1
        return {"ok": True, "saved": saved}
    except Exception as e:
        logger.error(f"[save-inverters] Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

def get_setup_service() -> SetupService:
    from backend.services.auth_service import AuthService
    svc = get_project_service()
    auth = AuthService()
    return SetupService(auth, svc)

@router.post("/sync")
def sync_to_server(setup_svc: SetupService = Depends(get_setup_service)):
    try:
        svc = get_project_service()
        all_projects = svc.get_projects()
        total_inverters = 0
        for project in all_projects:
            # Sử dụng các hàm tương thích mới thêm vào SetupService
            setup_svc.sync_project_to_server(project.id)
            total_inverters += setup_svc.sync_inverters_to_server(project.id)
        return {"ok": True, "synced_projects": len(all_projects), "synced_inverters": total_inverters}
    except Exception as e:
        logger.error(f"[Sync] Error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@router.get("/setup/status")
def get_setup_status():
    try:
        from dataclasses import asdict
        svc = get_project_service()
        all_projects = svc.get_projects()
        all_inverters = []
        for p in all_projects:
            invs = svc.metadata_db.get_inverters_by_project(p.id)
            for inv in invs:
                d = asdict(inv)
                d["project_id"] = p.id
                all_inverters.append(d)
        return {"projects": [asdict(p) for p in all_projects], "inverters": all_inverters}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
