# services/tracking_service.py

import logging
from datetime import datetime, date
from typing import Dict, Any, Optional
from database.sqlite_manager import RealtimeDB
from schemas.realtime import InverterErrorCreate

logger = logging.getLogger(__name__)

class TrackingService:
    def __init__(self, realtime_db: RealtimeDB):
        self.realtime_db = realtime_db
        
        # E_monthly tracking
        self.e_monthly_map: Dict[int, float] = {}
        self.last_e_total_map: Dict[int, Optional[float]] = {}
        
        # Max Values tracking
        # {inverter_id: {mppt_index: {"Max_I": val, "Max_V": val, "Max_P": val}}}
        self.mppt_max: Dict[int, Dict[int, Dict[str, float]]] = {}
        # {inverter_id: {string_id: max_I}}
        self.string_max: Dict[int, Dict[int, float]] = {}
        
        # Fault tracking
        # {inverter_id: set(last_fault_codes)}
        self.last_fault_map: Dict[int, set] = {}
        
        self.last_reset_date = date.today()

    def sync_from_db(self, inverter_id: int):
        """Khởi tạo trạng thái từ DB nếu chưa có trong memory"""
        if inverter_id in self.e_monthly_map:
            return
            
        # 1. Energy sync
        last_ac = self.realtime_db.get_latest_inverter_ac_realtime(inverter_id)
        if last_ac:
            try:
                rec_dt = datetime.fromisoformat(last_ac.created_at)
                today = date.today()
                
                if rec_dt.month == today.month and rec_dt.year == today.year:
                    self.e_monthly_map[inverter_id] = last_ac.E_monthly
                else:
                    self.e_monthly_map[inverter_id] = 0.0
                
                self.last_e_total_map[inverter_id] = last_ac.E_total
            except Exception as e:
                logger.error(f"Error parsing last AC record for inv {inverter_id}: {e}")
        
        # 2. Fault sync (Lấy các lỗi hiện tại đang mở từ DB)
        # Sửa: Lấy snapshot lỗi để biết cái nào đang active
        # Ở đây đơn giản là lấy record cuối cùng của từng fault_code
        with self.realtime_db._connect() as conn:
            rows = conn.execute("""
                SELECT fault_code FROM (
                    SELECT fault_code, ROW_NUMBER() OVER (PARTITION BY fault_code ORDER BY created_at DESC) as rn
                    FROM inverter_errors WHERE inverter_id = ?
                ) WHERE rn = 1
            """, (inverter_id,)).fetchall()
            self.last_fault_map[inverter_id] = {r["fault_code"] for r in rows if r["fault_code"] != 0}

    def check_resets(self):
        """Reset hàng ngày và hàng tháng"""
        today = date.today()
        if today > self.last_reset_date:
            logger.info(f"Checking resets for date {today}")
            # Reset Max Values hàng ngày
            self.mppt_max.clear()
            self.string_max.clear()
            # last_fault_map không reset vì nó là trạng thái logic
            
            # Reset Energy hàng tháng
            if today.month != self.last_reset_date.month:
                logger.info("Monthly reset of energy values.")
                self.e_monthly_map.clear()
            
            self.last_reset_date = today

    def update_energy(self, inverter_id: int, current_e_total: float) -> float:
        """Tính toán E_monthly dựa trên delta E_total"""
        self.sync_from_db(inverter_id)
        
        last_e = self.last_e_total_map.get(inverter_id)
        
        # Nếu là lần đầu tiên đọc được (last_e là None), chỉ khởi tạo last_e và trả về E_monthly hiện tại
        if last_e is None:
            logger.info(f"Initializing first E_total for inverter {inverter_id}: {current_e_total}")
            self.last_e_total_map[inverter_id] = current_e_total
            return self.e_monthly_map.get(inverter_id, 0.0)
            
        delta = max(0.0, current_e_total - last_e)
        
        # Chống nhảy số ảo (ví dụ > 100kWh trong 30s)
        if delta > 100.0: 
            logger.warning(f"Large energy delta detected for inv {inverter_id}: {delta}. Capping to 0.")
            delta = 0.0
            
        self.e_monthly_map[inverter_id] = self.e_monthly_map.get(inverter_id, 0.0) + delta
        self.last_e_total_map[inverter_id] = current_e_total
        
        return self.e_monthly_map[inverter_id]

    def update_max_values(self, project_id: int, inverter_id: int, data: dict, mppt_count: int, string_count: int):
        """Cập nhật các giá trị MAX và kiểm tra cắm ngược cực"""
        # MPPT Max & Reverse Polarity check
        if inverter_id not in self.mppt_max: self.mppt_max[inverter_id] = {}
        for i in range(1, mppt_count + 1):
            v = data.get(f"mppt_{i}_voltage", 0.0) or 0.0
            i_val = data.get(f"mppt_{i}_current", 0.0) or 0.0
            p = abs(v * i_val) / 1000.0 # Công suất luôn dương
            
            # Kiểm tra ngược cực
            if v < -1.0 or i_val < -1.0:
                self._log_reverse_polarity(project_id, inverter_id, f"MPPT_{i}", v, i_val)

            if i not in self.mppt_max[inverter_id]:
                self.mppt_max[inverter_id][i] = {"Max_V": v, "Max_I": i_val, "Max_P": p}
            else:
                self.mppt_max[inverter_id][i]["Max_V"] = max(self.mppt_max[inverter_id][i]["Max_V"], v)
                self.mppt_max[inverter_id][i]["Max_I"] = max(self.mppt_max[inverter_id][i]["Max_I"], i_val)
                self.mppt_max[inverter_id][i]["Max_P"] = max(self.mppt_max[inverter_id][i]["Max_P"], p)

        # String Max & Reverse Polarity check
        if inverter_id not in self.string_max: self.string_max[inverter_id] = {}
        for i in range(1, string_count + 1):
            s_i = data.get(f"string_{i}_current", 0.0) or 0.0
            
            if s_i < -1.0:
                self._log_reverse_polarity(project_id, inverter_id, f"String_{i}", current=s_i)

            self.string_max[inverter_id][i] = max(self.string_max[inverter_id].get(i, 0.0), s_i)

    def _log_reverse_polarity(self, project_id: int, inverter_id: int, component: str, voltage: float = 0.0, current: float = 0.0):
        """Ghi log lỗi ngược cực vào database"""
        logger.error(f"REVERSE POLARITY DETECTED: Project {project_id}, Inv {inverter_id}, {component} (V={voltage}, I={current})")
        
        # Chỉ ghi nếu chưa ghi lỗi này trong phiên hiện tại
        last_faults = self.last_fault_map.get(inverter_id, set())
        if 9999 not in last_faults:
            err = InverterErrorCreate(
                project_id=project_id,
                inverter_id=inverter_id,
                fault_code=9999, # Mã code tự định nghĩa cho Reverse Polarity
                fault_description=f"REVERSE POLARITY on {component}",
                repair_instruction="Check DC wiring and connector polarity.",
                severity="ERROR",
                created_at=datetime.now().isoformat()
            )
            self.realtime_db.post_inverter_error(err)
            if inverter_id not in self.last_fault_map: self.last_fault_map[inverter_id] = set()
            self.last_fault_map[inverter_id].add(9999)

    def log_inverter_error(self, inv: Any, data: dict):
        """Lưu lỗi vào DB nếu trạng thái lỗi thay đổi"""
        from datetime import timezone
        self.sync_from_db(inv.id)
        
        current_faults = data.get("fault_codes", []) # Giả định data đã có list các mã lỗi
        if not current_faults and data.get("fault_code"):
            current_faults = [data["fault_code"]]
            
        last_faults = self.last_fault_map.get(inv.id, set())

        # 1. Phát hiện lỗi mới (mã lỗi có trong current nhưng không có trong last)
        new_faults = [fc for fc in current_faults if fc not in last_faults and fc != 0]
        for fc in new_faults:
            err = InverterErrorCreate(
                project_id=inv.project_id,
                inverter_id=inv.id,
                fault_code=fc,
                fault_description=data.get("fault_description") or data.get("fault_name") or f"Fault {fc}",
                repair_instruction=data.get("repair_instruction", "Contact support"),
                severity=data.get("severity", "ERROR"),
                created_at=datetime.now(timezone.utc).isoformat()
            )
            self.realtime_db.post_inverter_error(err)
            self.last_fault_map[inv.id].add(fc)
            logger.warning(f"NEW FAULT Detected: {inv.id} - {err.fault_description}")

        # 2. Phát hiện lỗi kết thúc (có trong last nhưng không có trong current)
        cleared_faults = [fc for fc in last_faults if fc not in current_faults and fc != 9999] # Trừ mã reverse polarity tự định nghĩa
        for fc in cleared_faults:
            # Ghi record lỗi đã clear (severity = STABLE)
            err = InverterErrorCreate(
                project_id=inv.project_id,
                inverter_id=inv.id,
                fault_code=fc,
                fault_description=f"CLEARED: {fc}",
                repair_instruction="Fault resolved.",
                severity="STABLE",
                created_at=datetime.now(timezone.utc).isoformat()
            )
            self.realtime_db.post_inverter_error(err)
            self.last_fault_map[inv.id].remove(fc)
            logger.info(f"FAULT CLEARED: {inv.id} - Code {fc}")

    def get_max_data(self, inverter_id: int):
        return {
            "mppt": self.mppt_max.get(inverter_id, {}),
            "string": self.string_max.get(inverter_id, {})
        }
