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
from backend.models.polling import ProjectPollBatch
from backend.db_manager import CacheDB, RealtimeDB
from backend.core import settings

logger = logging.getLogger(__name__)

class PollingService:
    def __init__(self, project_svc: ProjectService, cache_db: CacheDB, realtime_db: RealtimeDB = None):
        self.project_svc = project_svc
        self.cache_db = cache_db
        self.realtime_db = realtime_db
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
                meters = self.project_svc.get_meters_by_project(project.id)
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

    def poll_project_batch(self, project_id: int, inverters: List[Any] = None) -> ProjectPollBatch:
        """Đọc dữ liệu từ tất cả Inverter của Project, gom vào một Batch object."""
        if inverters is None:
            all_invs = self.project_svc.get_inverters_by_project(project_id)
            active_inverters = [inv for inv in all_invs if inv.is_active]
        else:
            active_inverters = inverters
        
        batch = ProjectPollBatch(project_id=project_id, timestamp=datetime.now().isoformat())
        
        for inv in active_inverters:
            try:
                transport = self._get_transport(inv.brand)
                driver = self._get_driver(inv.brand, transport, inv.slave_id, inv.model)
                
                raw_data = None
                if driver:
                    try:
                        with transport.arbiter.operation("polling"):
                            raw_data = driver.read_all()
                    except Exception as e:
                        logger.warning(f"Driver read error for Inverter {inv.id}: {e}")

                if not raw_data:
                    # --- LOGIC XỬ LÝ MẤT KẾT NỐI (TIMEOUT/DISCONNECT) ---
                    logger.warning(f"Inverter {inv.id} (Slave {inv.slave_id}) failed to respond. Generating zero-payload.")
                    
                    # 1. Lấy dữ liệu cũ từ Cache hoặc RealtimeDB để bảo toàn sản lượng E
                    last_ac = self.cache_db.get_ac_cache(inv.id)
                    e_daily, e_total, e_monthly, delta_e = 0.0, 0.0, 0.0, 0.0
                    last_ts_str = None
                    
                    if last_ac:
                        e_daily = last_ac.get("E_daily", 0.0)
                        e_total = last_ac.get("E_total", 0.0)
                        e_monthly = last_ac.get("E_monthly", 0.0)
                        delta_e = last_ac.get("delta_E_monthly", 0.0)
                        last_ts_str = last_ac.get("updated_at")
                    else:
                        # Fallback to RealtimeDB if Cache is empty
                        last_real = self.realtime_db.get_latest_inverter_ac_realtime(inv.id)
                        if last_real:
                            e_daily = last_real.E_daily
                            e_total = last_real.E_total
                            e_monthly = last_real.E_monthly
                            delta_e = last_real.delta_E_monthly
                            last_ts_str = last_real.created_at

                    # --- KIỂM TRA RESET E THEO NGÀY/THÁNG ---
                    now = datetime.now()
                    if last_ts_str:
                        try:
                            # Xử lý format timestamp (có thể có hoặc không có T)
                            if "T" not in last_ts_str:
                                last_ts = datetime.fromisoformat(last_ts_str.replace(" ", "T"))
                            else:
                                last_ts = datetime.fromisoformat(last_ts_str)
                            
                            # Nếu qua ngày mới -> Reset E_daily
                            if last_ts.date() < now.date():
                                logger.info(f"New day detected for disconnected Inverter {inv.id}. Resetting E_daily.")
                                e_daily = 0.0
                            
                            # Nếu qua tháng mới -> Reset E_monthly
                            if last_ts.year < now.year or last_ts.month < now.month:
                                logger.info(f"New month detected for disconnected Inverter {inv.id}. Resetting E_monthly.")
                                e_monthly = 0.0
                                delta_e = 0.0
                        except Exception as e:
                            logger.warning(f"Failed to parse timestamp {last_ts_str} for Inverter {inv.id}: {e}")

                    # 2. Tạo bản tin AC "Zero" (P, U, I = 0) - Sử dụng các key mà CacheDB.upsert_inverter_ac mong đợi
                    clean = {
                        "p_inv_w": 0.0, "q_inv_var": 0.0, "pf": 0.0, "grid_hz": 0.0,
                        "v_a": 0.0, "v_b": 0.0, "v_c": 0.0,
                        "i_a": 0.0, "i_b": 0.0, "i_c": 0.0,
                        "e_daily": e_daily, "e_total": e_total,
                        "e_monthly": e_monthly, "delta_E_monthly": delta_e,
                        "ir": 0.0, "temp_c": 0.0
                    }
                    batch.ac_data.append({"inverter_id": inv.id, "data": clean})

                    # 3. Tạo bản tin MPPT & String "Zero"
                    for i in range(1, inv.mppt_count + 1):
                        batch.mppt_data.append({"inverter_id": inv.id, "mppt_index": i, "data": {"v_mppt": 0.0, "i_mppt": 0.0, "p_mppt": 0.0}})
                        for s_idx in [2*i-1, 2*i]:
                            batch.string_data.append({"inverter_id": inv.id, "string_id": s_idx, "mppt_id": i, "i_string": 0.0})

                    # 4. Gán lỗi mất kết nối (Mã 9: LỖI TRUYỀN THÔNG)
                    status_code = 9 
                    fault_code = 1501
                    errors_payload = [{
                        "fault_code": 1501,
                        "fault_description": "LỖI TRUYỀN THÔNG",
                        "repair_instruction": "Kiểm tra cáp RS485/Ethernet và địa chỉ Slave ID",
                        "severity": "DISCONNECT",
                        "created_at": batch.timestamp
                    }]
                    batch.error_data.append({
                        "inverter_id": inv.id, "status_code": status_code, "fault_code": fault_code,
                        "status_text": "LỖI TRUYỀN THÔNG", "fault_json": json.dumps(errors_payload, ensure_ascii=False)
                    })
                    continue

                # --- LOGIC XỬ LÝ KHI CÓ DỮ LIỆU THÀNH CÔNG ---
                clean = self.normalization.normalize(raw_data)
                batch.ac_data.append({"inverter_id": inv.id, "data": clean})
                
                # MPPT & String
                for i in range(1, inv.mppt_count + 1):
                    v_mppt = clean.get(f"mppt_{i}_voltage", 0.0)
                    i_mppt = clean.get(f"mppt_{i}_current", 0.0)
                    batch.mppt_data.append({
                        "inverter_id": inv.id, "mppt_index": i, 
                        "data": {"v_mppt": v_mppt, "i_mppt": i_mppt, "p_mppt": round(v_mppt * i_mppt, 2)}
                    })
                    for s_idx in [2*i-1, 2*i]:
                        i_str = clean.get(f"string_{s_idx}_current", 0.0)
                        batch.string_data.append({"inverter_id": inv.id, "string_id": s_idx, "mppt_id": i, "i_string": i_str})

                # Error Logic
                status_code = raw_data.get("state_id", 0)
                fault_code = raw_data.get("fault_code", 0)
                errors_payload = self.fault_service.get_inverter_status_payload(inv.brand, status_code, fault_code, batch.timestamp)
                
                # Check String Open Circuit
                current_strings_data = [{"string_index": s["string_id"], "I_string": s["i_string"]} for s in batch.string_data if s["inverter_id"] == inv.id]
                string_faults = self.string_monitor.process_strings(inv.id, current_strings_data, batch.timestamp)
                if string_faults:
                    errors_payload.extend(string_faults)

                state_snapshot = self.fault_service.get_state_snapshot(inv.brand, status_code)
                batch.error_data.append({
                    "inverter_id": inv.id, "status_code": status_code, "fault_code": fault_code,
                    "status_text": state_snapshot["name"], "fault_json": json.dumps(errors_payload, ensure_ascii=False)
                })
                
            except Exception as e:
                logger.error(f"Critical error polling inverter {inv.id}: {e}", exc_info=True)
        
        logger.info(f"Project {project_id}: Polled {len(batch.ac_data)} inverters in this batch.")
        return batch

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
