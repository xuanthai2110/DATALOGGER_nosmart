import time
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import importlib
from backend.db_manager import CacheDB
from backend.services.project_service import ProjectService
from backend.communication.modbus_tcp import ModbusTCP
from backend.communication.modbus_rtu import ModbusRTU
from backend.services.normalization_service import NormalizationService
from backend.services.fault_service import FaultService
from backend.services.string_monitoring_service import StringMonitoringService
from backend.core import settings

logger = logging.getLogger(__name__)

class PollingService:
    def __init__(self, project_svc: ProjectService, cache_db: CacheDB):
        self.project_svc = project_svc
        self.cache_db = cache_db
        self.normalization = NormalizationService()
        self.fault_service = FaultService()
        self.string_monitor = StringMonitoringService(cache_db)
        self.transports = {}
        self._transport_lock = threading.Lock()
        
        # Caching logic
        self._config_cache = []
        self._last_refresh = 0

    def _get_transport(self, brand: str):
        with self._transport_lock:
            if "Huawei" in brand:
                key = f"TCP_{settings.MODBUS_TCP_HOST}"
                if key not in self.transports:
                    t = ModbusTCP(host=settings.MODBUS_TCP_HOST, port=settings.MODBUS_TCP_PORT)
                    t.connect()
                    self.transports[key] = t
                return self.transports[key]
            else:
                key = "RTU"
                if key not in self.transports:
                    t = ModbusRTU(port=settings.MODBUS_PORT, baudrate=settings.MODBUS_BAUDRATE)
                    t.connect()
                    self.transports[key] = t
                return self.transports[key]

    def get_polling_config(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Lấy cấu hình polling (Projects & Inverters) từ RAM Cache hoặc Database"""
        now = time.time()
        if force_refresh or not self._config_cache or (now - self._last_refresh > settings.CONFIG_REFRESH_INTERVAL):
            logger.info("Refreshing Polling Configuration Cache from DB through Service...")
            projects = self.project_svc.get_projects()
            new_cache = []
            
            for project in projects:
                inverters = self.project_svc.get_inverters_by_project(project.id)
                active_inverters = [inv for inv in inverters if inv.is_active]
                
                # EVN: Lấy danh sách meters của project
                from backend.db_manager.metadata import MetadataDB
                meta_db = MetadataDB()
                meters = meta_db.get_meters_by_project(project.id)
                active_meters = [m for m in meters if m.is_active]

                new_cache.append({
                    "project": project,
                    "inverters": active_inverters,
                    "meters": active_meters
                })
            
            self._config_cache = new_cache
            self._last_refresh = now
        
        return self._config_cache

    def _get_driver(self, brand: str, transport, slave_id: int, model: str = None):
        if not brand or not model:
            return None
        
        # Sanitize for filename: brand_model.py (Sungrow_SG110CX -> sungrow_sg110cx.py)
        clean_brand = brand.lower().replace(" ", "_").replace("-", "_")
        clean_model = model.lower().replace(" ", "_").replace("-", "_")
        module_name = f"backend.drivers.{clean_brand}_{clean_model}"
        
        # Sanitize for classname: Brandmodel (Sungrow_SG110CX -> Sungrowsg110cx)
        clean_model_class = model.lower().replace(" ", "").replace("-", "").replace("_", "")
        class_name = f"{brand.capitalize()}{clean_model_class}"
        
        try:
            module = importlib.import_module(module_name)
            driver_class = getattr(module, class_name)
            return driver_class(transport, slave_id=slave_id)
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load driver {class_name} from {module_name}: {e}")
            return None

    def poll_all_inverters(self, project_id: int, inverters: List[Any] = None):
        """Đọc dữ liệu thô từ Inverter, chuẩn hóa và đẩy vào CacheDB."""
        if inverters is None:
            all_invs = self.metadata_db.get_inverters_by_project(project_id)
            active_inverters = [inv for inv in all_invs if inv.is_active]
        else:
            active_inverters = inverters
        
        for inv in active_inverters:
            try:
                transport = self._get_transport(inv.brand)
                driver = self._get_driver(inv.brand, transport, inv.slave_id, inv.model)
                if not driver: continue

                with transport.arbiter.operation("polling"):
                    raw_data = driver.read_all()
                if not raw_data: 
                    logger.warning(f"Inverter {inv.id} (Slave {inv.slave_id}) failed to respond.")
                    continue
                
                clean = self.normalization.normalize(raw_data)
                
                # Lưu vào CacheDB (RAM)
                self.cache_db.upsert_inverter_ac(inv.id, project_id, clean)
                
                # MPPT & String Cache
                for i in range(1, inv.mppt_count + 1):
                    v_mppt = clean.get(f"mppt_{i}_voltage", 0.0)
                    i_mppt = clean.get(f"mppt_{i}_current", 0.0)
                    
                    self.cache_db.upsert_mppt(inv.id, i, project_id, {
                        "v_mppt": v_mppt,
                        "i_mppt": i_mppt,
                        "p_mppt": round(v_mppt * i_mppt, 2)
                    })
                        
                    # String Cache (Mapping: strings 2i-1 and 2i for MPPT i)
                    for s_idx in [2*i-1, 2*i]:
                        i_str = clean.get(f"string_{s_idx}_current", 0.0)
                        self.cache_db.upsert_string(inv.id, s_idx, project_id, i, i_str)

                # Error Cache (Mã trạng thái thô & Mapping JSON)
                status_code = raw_data.get("state_id", 0)
                fault_code = raw_data.get("fault_code", 0)
                
                polling_time = datetime.now().isoformat()
                errors_payload = self.fault_service.get_inverter_status_payload(inv.brand, status_code, fault_code, polling_time)
                
                # --- Custom Logic: Check String Open Circuit ---
                current_strings_data = []
                for i in range(1, inv.mppt_count + 1):
                    for s_idx in [2*i-1, 2*i]:
                        current_strings_data.append({
                            "string_index": s_idx,
                            "I_string": clean.get(f"string_{s_idx}_current", 0.0)
                        })
                
                string_faults = self.string_monitor.process_strings(inv.id, current_strings_data, polling_time)
                if string_faults:
                    # Gộp lỗi string vào payload chung của inverter
                    errors_payload.extend(string_faults)

                state_snapshot = self.fault_service.get_state_snapshot(inv.brand, status_code)
                
                fault_json = json.dumps(errors_payload, ensure_ascii=False) if errors_payload else "[]"
                status_text = state_snapshot["name"]
                
                self.cache_db.upsert_error(inv.id, project_id, status_code, fault_code, status_text=status_text, fault_json=fault_json)
                
                logger.error(f"Poll & Cache Success - Inverter {inv.id}")
                
            except Exception as e:
                logger.error(f"Error polling inverter {inv.id}: {e}")

    def poll_meters(self, project_id: int, meters: List[Any]):
        """Đọc dữ liệu từ Meter (điểm đấu nối lưới) và lưu vào CacheDB."""
        for m in meters:
            try:
                # Meter thường dùng RTU
                transport = self._get_transport(m.brand)
                driver = self._get_meter_driver(m.brand, transport, m.slave_id, m.model)
                if not driver:
                    continue

                with transport.arbiter.operation("polling_meter"):
                    raw_data = driver.read_all()
                
                if not raw_data:
                    logger.warning(f"Meter {m.id} (Slave {m.slave_id}) failed to respond.")
                    continue

                # Lưu vào CacheDB
                self.cache_db.upsert_meter_cache(m.id, project_id, raw_data)
                logger.info(f"Poll & Cache Success - Meter {m.id}")

            except Exception as e:
                logger.error(f"Error polling meter {m.id}: {e}")

    def scan_meters(
        self, 
        brand: str, 
        model: str, 
        comm_type: str, 
        host: Optional[str] = None, 
        port: Optional[int] = None,
        com_port: Optional[str] = None,
        baudrate: int = 9600,
        slave_start: int = 1,
        slave_end: int = 247
    ) -> List[Dict]:
        """
        Quét các thiết bị Meter trong một dải Slave ID.
        Trả về danh sách các meter tìm thấy.
        """
        from backend.communication.modbus_tcp import ModbusTCP
        from backend.communication.modbus_rtu import ModbusRTU
        
        transport = None
        if comm_type.upper() == "TCP":
            transport = ModbusTCP(host, port)
        else:
            transport = ModbusRTU(com_port, baudrate)
            
        if not transport.connect():
            logger.error("[Polling] Scan meters: Failed to connect to %s:%s", host or com_port, port or baudrate)
            return []
            
        found_meters = []
        try:
            for sid in range(slave_start, slave_end + 1):
                logger.info("[Polling] Scanning meter brand=%s model=%s sid=%s", brand, model, sid)
                driver = self._get_meter_driver(brand, transport, sid, model)
                if not driver:
                    continue
                    
                # Thử đọc một tập dữ liệu cơ bản
                data = driver.read_all()
                if data:
                    # Đọc Serial Number (nếu driver hỗ trợ)
                    sn = driver.read_serial_number()
                    found_meters.append({
                        "brand": brand,
                        "model": model,
                        "slave_id": sid,
                        "serial_number": sn, # Có thể là None
                        "data_preview": {
                            "V_a": data.get("v_a"),
                            "P_total": data.get("p_total")
                        }
                    })
        finally:
            transport.close()
            
        return found_meters

    def _get_meter_driver(self, brand: str, transport, slave_id: int, model: str):
        """Tải driver cho Meter."""
        if not brand or not model:
            return None
        
        # Mapping: brand_model.py (Acrel_DTSD1352 -> acrel_dtsd1352.py)
        clean_brand = brand.lower().replace(" ", "_").replace("-", "_")
        clean_model = model.lower().replace(" ", "_").replace("-", "_")
        module_name = f"backend.drivers.{clean_brand}_{clean_model}"
        
        clean_model_class = model.lower().replace(" ", "").replace("-", "").replace("_", "")
        class_name = f"Meter{brand.capitalize()}{clean_model_class}"
        
        try:
            module = importlib.import_module(module_name)
            driver_class = getattr(module, class_name)
            return driver_class(transport, slave_id=slave_id)
        except (ImportError, AttributeError):
            # Fallback về Base class nếu chưa có driver cụ thể (dùng cho testing)
            logger.warning(f"Meter driver {class_name} not found, using MeterDriverBase")
            from backend.drivers.meter_base import MeterDriverBase
            return MeterDriverBase(transport, slave_id=slave_id)
