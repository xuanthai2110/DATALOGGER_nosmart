import logging
import json
from datetime import datetime
from typing import Dict, Set, List, Tuple
from backend.database import RealtimeDB, MetadataDB
from backend.services.fault_state_service import FaultStateService
from backend.models.realtime import InverterErrorCreate

logger = logging.getLogger(__name__)

class FaultLogicService:
    def __init__(self, realtime_db: RealtimeDB, metadata_db: MetadataDB, fault_state_service: FaultStateService):
        self.realtime_db = realtime_db
        self.metadata_db = metadata_db
        self.faults = fault_state_service
        
        # RAM state để phát hiện biến động tức thời (Change Detection)
        self.last_status_map: Dict[int, int] = {}
        self.last_fault_code_map: Dict[int, int] = {}
        
        # RAM state cho việc ghi log sự kiện lỗi vào RealtimeDB (History)
        self.active_faults_map: Dict[int, Set[int]] = {}
        
        # Cache brand: {inverter_id: brand}
        self.inverter_brands: Dict[int, str] = {}

    def seed_if_needed(self, inverter_id: int):
        """Khởi tạo trạng thái từ RealtimeDB (Disk) khi mới khởi động hệ thống"""
        if inverter_id in self.inverter_brands:
            return

        # 1. Lấy Brand Inverter từ MetadataDB
        inv_meta = self.metadata_db.get_inverter_by_id(inverter_id)
        brand = inv_meta.brand.upper() if inv_meta else "SUNGROW"
        self.inverter_brands[inverter_id] = brand

        # 2. Lấy trạng thái lỗi cuối cùng để điền vào active_faults_map (Dùng cho history log)
        with self.realtime_db._connect() as conn:
            rows = conn.execute("""
                SELECT fault_code FROM (
                    SELECT fault_code, ROW_NUMBER() OVER (PARTITION BY fault_code ORDER BY created_at DESC) as rn
                    FROM inverter_errors WHERE inverter_id = ?
                ) WHERE rn = 1
            """, (inverter_id,)).fetchall()
            self.active_faults_map[inverter_id] = {r["fault_code"] for r in rows if r["fault_code"] != 0}
        
        logger.info(f"Fault logic seeded for inv {inverter_id} ({brand})")

    def process(self, inverter_id: int, project_id: int, status_code: int, fault_code: int, polling_time: str) -> Tuple[list, bool]:
        """
        Xử lý Mapping và Phát hiện biến động:
        - Trả về: (errors_list, has_changed)
        - errors_list: Danh sách payload chuẩn server (State + Fault)
        - has_changed: True nếu status hoặc fault thay đổi so với lần đọc trước
        """
        self.seed_if_needed(inverter_id)
        brand = self.inverter_brands[inverter_id]
        
        # 1. Phát hiện biến động (Change Detection)
        has_changed = False
        if (inverter_id not in self.last_status_map or 
            self.last_status_map[inverter_id] != status_code or 
            self.last_fault_code_map[inverter_id] != fault_code):
            has_changed = True
            
        # Cập nhật mốc cũ
        self.last_status_map[inverter_id] = status_code
        self.last_fault_code_map[inverter_id] = fault_code

        # 2. Tạo Payload thống nhất (Unified Payload)
        errors_payload = self.faults.get_inverter_status_payload(brand, status_code, fault_code, polling_time)
        
        # 3. Ghi log sự kiện lỗi vào RealtimeDB (History) nếu có lỗi mới/clear
        self._sync_history_log(inverter_id, project_id, fault_code, errors_payload, polling_time)
        
        return errors_payload, has_changed

    def _sync_history_log(self, inv_id, proj_id, current_fault_code, errors_payload, polling_time):
        """Ghi nhận sự kiện NEW FAULT hoặc CLEARED vào database Realtime (Disk) để làm báo cáo lỗi"""
        active_faults = self.active_faults_map.get(inv_id, set())
        
        # Lấy thông tin fault từ payload (nếu có)
        fault_info = None
        if len(errors_payload) > 1:
            fault_info = errors_payload[1]

        # A. Phát hiện lỗi MỚI
        if current_fault_code != 0 and current_fault_code not in active_faults:
            if fault_info:
                err = InverterErrorCreate(
                    project_id=proj_id,
                    inverter_id=inv_id,
                    fault_code=current_fault_code,
                    fault_description=fault_info["fault_description"],
                    repair_instruction=fault_info["repair_instruction"],
                    severity=fault_info["severity"],
                    created_at=polling_time
                )
                self.realtime_db.post_inverter_error(err)
                active_faults.add(current_fault_code)
                logger.warning(f"HISTORY: NEW FAULT logged for inv {inv_id} - code {current_fault_code}")

        # B. Phát hiện lỗi đã HẾT (Cleared)
        if current_fault_code == 0 and active_faults:
            for fc in list(active_faults):
                err = InverterErrorCreate(
                    project_id=proj_id,
                    inverter_id=inv_id,
                    fault_code=fc,
                    fault_description=f"CLEARED: {fc}",
                    repair_instruction="Fault resolved.",
                    severity="STABLE",
                    created_at=polling_time
                )
                self.realtime_db.post_inverter_error(err)
                active_faults.remove(fc)
                logger.info(f"HISTORY: FAULT CLEARED logged for inv {inv_id} - code {fc}")
        
        self.active_faults_map[inv_id] = active_faults
