import logging
import json
from datetime import datetime
from typing import Dict, Set, List, Tuple
from backend.db_manager import RealtimeDB, MetadataDB
from backend.services.fault_mappings import FAULT_MAPS, STATE_MAPS, HUAWEI_MODBUS_MAP
from backend.models.realtime import InverterErrorCreate

logger = logging.getLogger(__name__)

class FaultService:
    """Dịch vụ hợp nhất quản lý Trạng thái và Lỗi Inverter."""
    
    def __init__(self, realtime_db: RealtimeDB, metadata_db: MetadataDB):
        self.realtime_db = realtime_db
        self.metadata_db = metadata_db
        self.last_status_map: Dict[int, int] = {}
        self.last_fault_code_map: Dict[int, int] = {}
        self.active_faults_map: Dict[int, Set[int]] = {}
        self.inverter_brands: Dict[int, str] = {}

    def seed_if_needed(self, inv_id: int):
        if inv_id in self.inverter_brands: return
        inv_meta = self.metadata_db.get_inverter_by_id(inv_id)
        self.inverter_brands[inv_id] = inv_meta.brand.upper() if inv_meta else "SUNGROW"
        self.active_faults_map[inv_id] = set() # Điền vào từ db nếu cần history kỹ hơn

    def get_inverter_status_payload(self, brand: str, raw_state: int, raw_fault: int, polling_time: str) -> list:
        brand = brand.upper()
        # 1. Map State
        mapped_state_id = raw_state
        if brand == "HUAWEI": mapped_state_id = HUAWEI_MODBUS_MAP.get(raw_state, 5)
        state_info = STATE_MAPS.get(brand, {}).get(mapped_state_id, {"name": "RUNNING", "severity": "STABLE"})
        
        errors = []
        if state_info["severity"] != "STABLE":
            errors.append({
                "fault_code": 0, "fault_description": state_info["name"],
                "repair_instruction": "", "severity": state_info["severity"],
                "created_at": polling_time
            })
        
        # 2. Map Fault
        if raw_fault != 0:
            f_info = FAULT_MAPS.get(brand, {}).get(raw_fault, {"name": f"ERROR {raw_fault}", "severity": "ERROR"})
            errors.append({
                "fault_code": f_info.get("id_unified", raw_fault),
                "fault_description": f_info["name"],
                "repair_instruction": f_info.get("repair_instruction", "Check manual."),
                "severity": f_info["severity"], "created_at": polling_time
            })
        return errors

    def process(self, inv_id: int, proj_id: int, status_code: int, fault_code: int, polling_time: str) -> Tuple[list, bool]:
        self.seed_if_needed(inv_id)
        brand = self.inverter_brands[inv_id]
        
        # Change Detection
        has_changed = (inv_id not in self.last_status_map or self.last_status_map[inv_id] != status_code or self.last_fault_code_map[inv_id] != fault_code)
        self.last_status_map[inv_id] = status_code
        self.last_fault_code_map[inv_id] = fault_code

        payload = self.get_inverter_status_payload(brand, status_code, fault_code, polling_time)
        return payload, has_changed
