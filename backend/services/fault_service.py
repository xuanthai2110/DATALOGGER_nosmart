import logging
from typing import Dict, Set, Tuple
from backend.db_manager import RealtimeDB, MetadataDB
from backend.services.fault_mappings import FAULT_MAPS, STATE_MAPS, UNIFIED_FAULTS, UNIFIED_STATES

logger = logging.getLogger(__name__)    

class FaultService:
    """Dịch vụ hợp nhất quản lý Trạng thái và Lỗi Inverter."""
    
    def __init__(self, realtime_db: RealtimeDB = None, metadata_db: MetadataDB = None):
        self.realtime_db = realtime_db
        self.metadata_db = metadata_db
        self.last_status_map: Dict[int, int] = {}
        self.last_fault_code_map: Dict[int, int] = {}
        self.last_severity_map: Dict[int, str] = {}
        self.active_faults_map: Dict[int, Set[int]] = {}
        self.inverter_brands: Dict[int, str] = {}

    def seed_if_needed(self, inv_id: int):
        if inv_id in self.inverter_brands: return
        if self.metadata_db:
            inv_meta = self.metadata_db.get_inverter_by_id(inv_id)
            self.inverter_brands[inv_id] = inv_meta.brand.upper() if inv_meta else "SUNGROW"
        else:
            self.inverter_brands[inv_id] = "SUNGROW"
        self.active_faults_map[inv_id] = set() # Điền vào từ db nếu cần history kỹ hơn

    def get_inverter_status_payload(self, brand: str, raw_state: int, raw_fault: int, polling_time: str) -> list:
        brand = brand.upper()
        state_map = STATE_MAPS.get(brand, {})
        fault_map = FAULT_MAPS.get(brand, {})

        # raw_state is already the vendor status code read from inverter.
        state_info = state_map.get(raw_state, {"id_unified": raw_state, "name": "UNKNOWN_STATE", "severity": "STABLE"})
        state_unified_code = state_info.get("id_unified", raw_state)
        state_name = UNIFIED_STATES.get(state_unified_code, state_info.get("name", "UNKNOWN_STATE"))

        if raw_fault != 0:
            fault_info = fault_map.get(raw_fault, {"id_unified": raw_fault, "name": f"ERROR_{raw_fault}", "severity": "ERROR"})
            fault_unified_code = fault_info.get("id_unified", raw_fault)
            return [{
                "fault_code": fault_unified_code,
                "fault_description": UNIFIED_FAULTS.get(fault_unified_code, fault_info.get("name", f"ERROR_{raw_fault}")),
                "repair_instruction": fault_info.get("repair_instruction", ""),
                "severity": fault_info.get("severity", "ERROR"),
                "created_at": polling_time
            }]

        return [{
            "fault_code": state_unified_code,
            "fault_description": state_name,
            "repair_instruction": state_info.get("description", ""),
            "severity": state_info.get("severity", "STABLE"),
            "created_at": polling_time
        }]

    def get_state_snapshot(self, brand: str, raw_state: int) -> dict:
        brand = brand.upper()
        state_info = STATE_MAPS.get(brand, {}).get(raw_state, {"id_unified": raw_state, "name": "UNKNOWN_STATE", "severity": "STABLE"})
        state_unified_code = state_info.get("id_unified", raw_state)
        return {
            "code": state_unified_code,
            "name": UNIFIED_STATES.get(state_unified_code, state_info.get("name", "UNKNOWN_STATE")),
            "severity": state_info.get("severity", "STABLE"),
            "description": state_info.get("description", "")
        }

    def process(self, inv_id: int, proj_id: int, status_code: int, fault_code: int, polling_time: str) -> Tuple[list, bool, str]:
        self.seed_if_needed(inv_id)
        brand = self.inverter_brands[inv_id]
        
        # Change Detection
        has_changed = (inv_id not in self.last_status_map or self.last_status_map[inv_id] != status_code or self.last_fault_code_map[inv_id] != fault_code)
        
        last_severity = self.last_severity_map.get(inv_id, "STABLE")
        
        self.last_status_map[inv_id] = status_code
        self.last_fault_code_map[inv_id] = fault_code

        payload = self.get_inverter_status_payload(brand, status_code, fault_code, polling_time)
        
        current_severity = "STABLE"
        if payload:
            current_severity = payload[0].get("severity", "STABLE")
        
        self.last_severity_map[inv_id] = current_severity
        
        return payload, has_changed, last_severity
