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
        
        self.last_reset_date = date.today()

    def sync_from_db(self, inverter_id: int):
        """Khởi tạo trạng thái từ DB nếu chưa có trong memory"""
        if inverter_id in self.e_monthly_map:
            return
            
        last_rec = self.realtime_db.get_latest_inverter_ac_realtime(inverter_id)
        if last_rec:
            try:
                rec_dt = datetime.fromisoformat(last_rec.created_at)
                today = date.today()
                
                if rec_dt.month == today.month and rec_dt.year == today.year:
                    self.e_monthly_map[inverter_id] = last_rec.E_monthly
                else:
                    self.e_monthly_map[inverter_id] = 0.0
                
                self.last_e_total_map[inverter_id] = last_rec.E_total
            except Exception as e:
                logger.error(f"Error parsing last record date for inv {inverter_id}: {e}")
                self.e_monthly_map[inverter_id] = 0.0
                self.last_e_total_map[inverter_id] = None
        else:
            self.e_monthly_map[inverter_id] = 0.0
            self.last_e_total_map[inverter_id] = None # Đánh dấu là chưa có dữ liệu lịch sử

    def check_resets(self):
        """Reset hàng ngày và hàng tháng"""
        today = date.today()
        if today > self.last_reset_date:
            logger.info(f"Checking resets for date {today}")
            # Reset Max Values hàng ngày
            self.mppt_max.clear()
            self.string_max.clear()
            
            # Reset Energy hàng tháng
            if today.month != self.last_reset_date.month:
                logger.info("Monthly reset of energy values.")
                self.e_monthly_map.clear()
                # last_e_total_map giữ nguyên để tính delta liên tục
            
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
        
        # Chống nhảy số ảo (ví dụ > 1000kWh trong 30s)
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

    def log_inverter_error(self, inv: Any, data: dict):
        """Lưu lỗi vào DB nếu severity là lỗi thực sự"""
        severity = data.get("severity", "STABLE")
        fault_code = data.get("fault_code", 0)
        
        # Chỉ lưu nếu là ERROR hoặc cảnh báo quan trọng (tùy user, ở đây tôi ưu tiên ERROR)
        if fault_code != 0 and severity == "ERROR":
            err = InverterErrorCreate(
                project_id=inv.project_id,
                inverter_id=inv.id,
                fault_code=fault_code,
                fault_description=data.get("fault_description", "Unknown Fault"),
                repair_instruction=data.get("repair_instruction", ""),
                severity=severity,
                created_at=datetime.now().isoformat()
            )
            self.realtime_db.post_inverter_error(err)
            logger.warning(f"FAULT Logged: {inv.id} - {err.fault_description}")

    def get_max_data(self, inverter_id: int):
        return {
            "mppt": self.mppt_max.get(inverter_id, {}),
            "string": self.string_max.get(inverter_id, {})
        }
