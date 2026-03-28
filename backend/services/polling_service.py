# services/polling_service.py

import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from database.sqlite_manager import MetadataDB, CacheDB
from drivers.huawei_sun2000110KTL import HuaweiSUN2000
from drivers.sungrow_sg110cx import SungrowSG110CXDriver
from communication.modbus_tcp import ModbusTCP
from communication.modbus_rtu import ModbusRTU
from services.normalization_service import NormalizationService
import config

logger = logging.getLogger(__name__)

class PollingService:
    def __init__(self, metadata_db: MetadataDB, cache_db: CacheDB):
        self.metadata_db = metadata_db
        self.cache_db = cache_db
        self.normalization = NormalizationService()
        self.transports = {}

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
        """Đọc dữ liệu thô từ Inverter, chuẩn hóa và đẩy vào CacheDB.
        Có thể truyền danh sách inverters vào để tối ưu (không cần query DB).
        """
        if inverters is None:
            # Fallback nếu không truyền list inverters (không khuyến khích dùng loop này nữa)
            all_invs = self.metadata_db.get_inverters_by_project(project_id)
            active_inverters = [inv for inv in all_invs if inv.is_active]
        else:
            active_inverters = inverters
        
        for inv in active_inverters:
            try:
                transport = self._get_transport(inv.brand)
                driver = self._get_driver(inv.brand, transport, inv.slave_id)
                if not driver: continue
                
                # 1. Đọc dữ liệu thô
                raw_data = driver.read_all()
                if not raw_data: 
                    logger.warning(f"Inverter {inv.id} (Slave {inv.slave_id}) failed to respond.")
                    continue
                
                # 2. Chuẩn hóa dữ liệu (Làm tròn, xử lý scale factor)
                clean = self.normalization.normalize(raw_data)
                
                # 3. Lưu vào CacheDB (RAM)
                # a. AC Cache
                self.cache_db.upsert_inverter_ac(inv.id, project_id, clean)
                
                # b. MPPT Cache
                mppts = []
                for i in range(1, inv.mppt_count + 1):
                    v = clean.get(f"mppt_{i}_voltage", 0.0)
                    curr = clean.get(f"mppt_{i}_current", 0.0)
                    mppts.append({
                        "index": i, "v": v, "i": curr, "p": round(v * curr, 2)
                    })
                if mppts:
                    self.cache_db.upsert_mppt_batch(inv.id, project_id, mppts)

                # c. String Cache
                strings = []
                for i in range(1, inv.string_count + 1):
                    # Tạm thời gán mppt_id dựa trên logic chia đều nếu driver không cung cấp mapping
                    m_id = (i - 1) // (inv.string_count // inv.mppt_count) + 1 if inv.mppt_count > 0 else 1
                    strings.append({
                        "index": i, "mppt_id": m_id, "i": clean.get(f"string_{i}_current", 0.0)
                    })
                if strings:
                    self.cache_db.upsert_string_batch(inv.id, project_id, strings)

                # d. Error Cache (Mã trạng thái thô)
                status_code = raw_data.get("state_id", 0)
                fault_code = raw_data.get("fault_code", 0)
                self.cache_db.upsert_error(inv.id, project_id, status_code, fault_code)
                
                logger.info(f"Poll & Cache Success - Inverter {inv.id} (S/N: {inv.serial_number})")
                
            except Exception as e:
                logger.error(f"Error polling inverter {inv.id}: {e}")

    def run_forever(self):
        logger.info("Dumb Polling Service started (Cache Only Mode)")
        while True:
            t0 = time.time()
            
            # 1. Lấy cấu hình từ cache (hoặc database nếu hết hạn)
            polling_config = self.get_polling_config()
            
            # 2. Quét dữ liệu cho từng project
            for item in polling_config:
                project = item["project"]
                inverters = item["inverters"]
                self.poll_all_inverters(project.id, inverters=inverters)

            # 3. Duy trì chu kỳ POLL_INTERVAL
            elapsed = time.time() - t0
            sleep_time = max(0.1, config.POLL_INTERVAL - elapsed)
            time.sleep(sleep_time)
