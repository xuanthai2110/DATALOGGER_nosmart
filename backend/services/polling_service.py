import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from database import MetadataDB, CacheDB
from drivers.huawei_sun2000110KTL import HuaweiSUN2000
from drivers.sungrow_sg110cx import SungrowSG110CXDriver
from communication.modbus_tcp import ModbusTCP
from communication.modbus_rtu import ModbusRTU
from services.normalization_service import NormalizationService
from core import config

logger = logging.getLogger(__name__)

class PollingService:
    def __init__(self, metadata_db: MetadataDB, cache_db: CacheDB):
        self.metadata_db = metadata_db
        self.cache_db = cache_db
        self.normalization = NormalizationService()
        self.transports = {}
        
        # Caching logic
        self._config_cache = []
        self._last_refresh = 0

    def _get_transport(self, brand: str):
        if "Huawei" in brand:
            key = f"TCP_{config.MODBUS_TCP_HOST}"
            if key not in self.transports:
                t = ModbusTCP(host=config.MODBUS_TCP_HOST, port=config.MODBUS_TCP_PORT)
                t.connect()
                self.transports[key] = t
            return self.transports[key]
        else:
            key = "RTU"
            if key not in self.transports:
                t = ModbusRTU(port=config.MODBUS_PORT, baudrate=config.MODBUS_BAUDRATE)
                t.connect()
                self.transports[key] = t
            return self.transports[key]

    def get_polling_config(self) -> List[Dict[str, Any]]:
        """Lấy cấu hình polling (Projects & Inverters) từ RAM Cache hoặc Database"""
        now = time.time()
        if not self._config_cache or (now - self._last_refresh > config.CONFIG_REFRESH_INTERVAL):
            logger.info("Refreshing Polling Configuration Cache from MetadataDB...")
            projects = self.metadata_db.get_projects()
            new_cache = []
            
            for project in projects:
                inverters = self.metadata_db.get_inverters_by_project(project.id)
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
                
                raw_data = driver.read_all()
                if not raw_data: 
                    logger.warning(f"Inverter {inv.id} (Slave {inv.slave_id}) failed to respond.")
                    continue
                
                clean = self.normalization.normalize(raw_data)
                
                # Lưu vào CacheDB (RAM)
                self.cache_db.upsert_inverter_ac(inv.id, project_id, clean)
                
                # MPPT Cache
                mppts = []
                for i in range(1, inv.mppt_count + 1):
                    v = clean.get(f"mppt_{i}_voltage", 0.0)
                    curr = clean.get(f"mppt_{i}_current", 0.0)
                    mppts.append({
                        "index": i, "v": v, "i": curr, "p": round(v * curr, 2)
                    })
                if mppts:
                    with self.cache_db._connect() as conn:
                        # Dùng executemany thủ công hoặc tạo helper trong cache.py sau
                        pass

                # Error Cache (Mã trạng thái thô)
                status_code = raw_data.get("state_id", 0)
                fault_code = raw_data.get("fault_code", 0)
                self.cache_db.upsert_error(inv.id, project_id, status_code, fault_code)
                
                logger.info(f"Poll & Cache Success - Inverter {inv.id}")
                
            except Exception as e:
                logger.error(f"Error polling inverter {inv.id}: {e}")
