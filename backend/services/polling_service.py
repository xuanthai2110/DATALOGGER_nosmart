import time
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from backend.db_manager import CacheDB
from backend.services.project_service import ProjectService
from backend.drivers.huawei_sun2000110KTL import HuaweiSUN2000
from backend.drivers.sungrow_sg110cx import SungrowSG110CXDriver
from backend.communication.modbus_tcp import ModbusTCP
from backend.communication.modbus_rtu import ModbusRTU
from backend.services.normalization_service import NormalizationService
from backend.services.fault_service import FaultService
from backend.core import settings

logger = logging.getLogger(__name__)

class PollingService:
    def __init__(self, project_svc: ProjectService, cache_db: CacheDB):
        self.project_svc = project_svc
        self.cache_db = cache_db
        self.normalization = NormalizationService()
        self.fault_service = FaultService()
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
                new_cache.append({
                    "project": project,
                    "inverters": active_inverters
                })
            
            self._config_cache = new_cache
            self._last_refresh = now
        
        return self._config_cache

    def _get_driver(self, brand: str, transport, slave_id: int):
        if "Huawei" in brand:
            return HuaweiSUN2000(transport, slave_id=slave_id)
        elif "Sungrow" in brand:
            return SungrowSG110CXDriver(transport, slave_id=slave_id)
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
                driver = self._get_driver(inv.brand, transport, inv.slave_id)
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
                state_snapshot = self.fault_service.get_state_snapshot(inv.brand, status_code)
                
                fault_json = json.dumps(errors_payload, ensure_ascii=False) if errors_payload else "[]"
                status_text = state_snapshot["name"]
                
                self.cache_db.upsert_error(inv.id, project_id, status_code, fault_code, status_text=status_text, fault_json=fault_json)
                
                logger.info(f"Poll & Cache Success - Inverter {inv.id}")
                
            except Exception as e:
                logger.error(f"Error polling inverter {inv.id}: {e}")
