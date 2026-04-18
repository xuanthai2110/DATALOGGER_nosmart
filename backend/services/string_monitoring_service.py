import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class StringMonitoringService:
    """Theo dõi dòng điện các String để phát hiện hở mạch."""
    
    def __init__(self, cache_db=None):
        self.cache_db = cache_db
        # Lưu trữ tạm trong RAM để xử lý nhanh
        self.morning_baseline: Dict[int, Dict[int, int]] = {}
        self.zero_current_start_time: Dict[int, Dict[int, float]] = {}
        self.active_faults: Dict[int, set] = {}
        
        # Load lại dữ liệu từ cache nếu có (đề phòng restart lúc đang chạy)
        self._load_from_cache()

    def _load_from_cache(self):
        """Khôi phục trạng thái từ CacheDB."""
        if not self.cache_db: return
        try:
            # Chúng ta sẽ lưu vào bảng error_cache hoặc một cơ chế tương tự 
            # Tuy nhiên để đơn giản và hiệu quả, tôi sẽ dùng cơ chế lưu JSON vào cache_db nếu cần.
            # Ở đây, tôi sẽ khởi tạo trống và ưu tiên lưu baseline vào RAM. 
            # Nếu bạn muốn lưu xuống đĩa, tôi sẽ tạo một bảng riêng.
            pass
        except Exception as e:
            logger.error(f"[StringMonitor] Load cache error: {e}")

    def process_strings(self, inverter_id: int, strings_data: List[Dict], polling_time: str) -> List[Dict]:
        now = datetime.now()
        current_hour = now.hour
        current_ts = time.time()
        
        # 1. Logic chốt baseline lúc 7h sáng
        if current_hour == 7:
            if inverter_id not in self.morning_baseline:
                self.morning_baseline[inverter_id] = {}
            
            for s in strings_data:
                idx = s["string_index"]
                current_i = s.get("I_string", 0)
                if current_i > 0:
                    self.morning_baseline[inverter_id][idx] = 1
                else:
                    self.morning_baseline[inverter_id][idx] = 0
            return []

        # 2. Logic giám sát sau 7h sáng
        if inverter_id not in self.morning_baseline:
            return []

        new_faults = []
        baseline = self.morning_baseline[inverter_id]
        
        if inverter_id not in self.zero_current_start_time:
            self.zero_current_start_time[inverter_id] = {}
        if inverter_id not in self.active_faults:
            self.active_faults[inverter_id] = set()

        for s in strings_data:
            idx = s["string_index"]
            current_i = s.get("I_string", 0)
            
            # Kiểm tra string có trong danh sách baseline "có điện" (1)
            if baseline.get(idx) == 1:
                if current_i <= 0:
                    # Bắt đầu đếm thời gian
                    if idx not in self.zero_current_start_time[inverter_id]:
                        self.zero_current_start_time[inverter_id][idx] = current_ts
                    else:
                        elapsed = current_ts - self.zero_current_start_time[inverter_id][idx]
                        # Nếu mất dòng liên tục quá 5 phút (300 giây)
                        if elapsed >= 300:
                            if idx not in self.active_faults[inverter_id]:
                                logger.warning(f"[StringMonitor] Inverter {inverter_id} String {idx} open circuit confirmed after 5 mins.")
                                self.active_faults[inverter_id].add(idx)
                                
                                # Tạo lỗi gửi lên server
                                new_faults.append({
                                    "fault_code": 23,
                                    "fault_description": "Phát hiện String bị hở mạch",
                                    "repair_instruction": f"Kiểm tra string {idx} có phải bị rút hay hở mạch không.",
                                    "severity": "WARNING",
                                    "created_at": polling_time
                                })
                else:
                    # Nếu có dòng lại (>0A), xóa bộ đếm và trạng thái lỗi
                    self.zero_current_start_time[inverter_id].pop(idx, None)
                    if idx in self.active_faults[inverter_id]:
                        self.active_faults[inverter_id].remove(idx)
                        logger.info(f"[StringMonitor] Inverter {inverter_id} String {idx} recovered (I > 0A).")

        return new_faults

    def reset_daily(self):
        """Reset vào cuối ngày (gọi lúc 00:00)."""
        self.morning_baseline.clear()
        self.zero_current_start_time.clear()
        self.active_faults.clear()
        logger.info("[StringMonitor] Daily reset completed.")
