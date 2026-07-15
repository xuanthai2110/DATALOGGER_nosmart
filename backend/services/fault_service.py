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

    @staticmethod
    def format_repair_instruction(brand: str, raw_fault: int, instruction: str) -> str:
        brand = brand.upper()
        if not instruction:
            return f"mã lỗi {brand}: +{raw_fault}+"
        return f"mã lỗi {brand}: +{raw_fault}+{instruction}"

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
            raw_inst = fault_info.get("repair_instruction", "")
            return [{
                "fault_code": fault_unified_code,
                "fault_description": UNIFIED_FAULTS.get(fault_unified_code, fault_info.get("name", f"ERROR_{raw_fault}")),
                "repair_instruction": FaultService.format_repair_instruction(brand, raw_fault, raw_inst),
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

    def process(self, inv_id: int, proj_id: int, status_code: int, fault_code: int, polling_time: str, fault_json: str = None) -> Tuple[list, bool, str]:
        self.seed_if_needed(inv_id)
        brand = self.inverter_brands[inv_id]
        
        # Parse payload từ fault_json nếu có, nếu không thì tự sinh từ status_code/fault_code
        payload = []
        if fault_json:
            try:
                import json
                payload = json.loads(fault_json)
            except Exception as e:
                logger.error(f"Failed to parse fault_json in FaultService.process for inverter {inv_id}: {e}")
                
        if not payload:
            payload = self.get_inverter_status_payload(brand, status_code, fault_code, polling_time)
            
        # Lấy tập hợp các mã lỗi hiện tại để so sánh sự thay đổi
        current_codes = {item.get("fault_code") for item in payload if item.get("fault_code") is not None}
        
        # Phát hiện thay đổi dựa trên tập hợp mã lỗi
        last_codes = self.active_faults_map.get(inv_id, set())
        has_changed = (inv_id not in self.last_status_map or last_codes != current_codes)
        
        last_severity = self.last_severity_map.get(inv_id, "STABLE")
        
        self.last_status_map[inv_id] = status_code
        self.last_fault_code_map[inv_id] = fault_code
        self.active_faults_map[inv_id] = current_codes
        
        current_severity = "STABLE"
        if payload:
            # Lấy mức độ nghiêm trọng cao nhất trong các lỗi hiện tại
            severity_priority = {"DISCONNECT": 4, "ERROR": 3, "WARNING": 2, "STABLE": 1}
            max_sev = "STABLE"
            for item in payload:
                sev = item.get("severity", "STABLE")
                if severity_priority.get(sev, 0) > severity_priority.get(max_sev, 0):
                    max_sev = sev
            current_severity = max_sev
            
        self.last_severity_map[inv_id] = current_severity
        
        return payload, has_changed, last_severity
