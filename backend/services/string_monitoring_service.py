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
        self.last_currents: Dict[int, Dict[int, float]] = {}
        self.zero_current_start_time: Dict[int, Dict[int, float]] = {}
        self.active_faults: Dict[int, set] = {}
        
        # Load lại dữ liệu từ cache nếu có (đề phòng restart lúc đang chạy)
        self._load_from_cache()

    def _load_from_cache(self):
        """Khôi phục trạng thái từ CacheDB."""
        if not self.cache_db: return
        try:
            # Hiện tại chưa lưu trạng thái string monitor xuống đĩa để tránh ghi nhiều vào thẻ SD.
            # Trạng thái sẽ được xây dựng lại sau vài phút chạy (polling).
            pass
        except Exception as e:
            logger.error(f"[StringMonitor] Load cache error: {e}")

    def process_strings(self, inverter_id: int, strings_data: List[Dict], polling_time: str) -> List[Dict]:
        now = datetime.now()
        current_hour = now.hour
        current_ts = time.time()

        # =========================================================
        # 1. CHỈ TRACK TỪ 7h → 16h (Thời điểm có nắng)
        # =========================================================
        if current_hour < 7 or current_hour > 16:
            # Xóa các trạng thái đếm thời gian nếu ngoài khung giờ để tránh treo timer
            self.zero_current_start_time.pop(inverter_id, None)
            return []

        # Init dict nếu chưa có
        if inverter_id not in self.last_currents:
            self.last_currents[inverter_id] = {}

        if inverter_id not in self.zero_current_start_time:
            self.zero_current_start_time[inverter_id] = {}

        if inverter_id not in self.active_faults:
            self.active_faults[inverter_id] = set()

        new_faults = []
        lost_strings = []

        # =========================================================
        # 2. GIÁM SÁT SỤT GIẢM DÒNG ĐIỆN (DELTA I > 3A & I < 0.1A)
        # =========================================================
        for s in strings_data:
            idx = s["string_index"]
            current_i = s.get("I_string", 0.0)
            
            # Lấy dòng điện của bản ghi trước đó
            i_prev = self.last_currents[inverter_id].get(idx)

            if current_i < 0.1:
                # Nếu chưa bắt đầu đếm thời gian hở mạch cho string này
                if idx not in self.zero_current_start_time[inverter_id]:
                    # Kiểm tra điều kiện sụt giảm đột ngột (phải có i_prev và delta > 3A)
                    if i_prev is not None and (i_prev - current_i) > 3.0:
                        self.zero_current_start_time[inverter_id][idx] = current_ts
                        logger.info(f"[StringMonitor] Sudden drop detected on Inverter {inverter_id} String {idx} (from {i_prev}A to {current_i}A). Starting 5min timer.")
                else:
                    # Đang trong trạng thái dòng thấp, kiểm tra thời gian duy trì
                    elapsed = current_ts - self.zero_current_start_time[inverter_id][idx]
                    if elapsed >= 300: # 5 phút
                        if idx not in self.active_faults[inverter_id]:
                            self.active_faults[inverter_id].add(idx)
                            lost_strings.append(idx)
            else:
                # Dòng điện đã phục hồi hoặc hoạt động bình thường (>= 0.1A)
                # Reset trạng thái đếm thời gian và trạng thái lỗi
                self.zero_current_start_time[inverter_id].pop(idx, None)
                
                if idx in self.active_faults[inverter_id]:
                    self.active_faults[inverter_id].remove(idx)
                    logger.info(f"[StringMonitor] Inverter {inverter_id} String {idx} recovered (Current: {current_i}A)")

            # Cập nhật giá trị dòng điện vào bộ nhớ cho lần quét sau
            self.last_currents[inverter_id][idx] = current_i

        # 👉 Tổng hợp và trả về bản tin lỗi nếu có string mới bị mất dòng
        if lost_strings:
            str_list = ", ".join(map(str, sorted(lost_strings)))
            logger.warning(f"[StringMonitor] Inverter {inverter_id} Strings {str_list} mất dòng đột ngột >5 phút")

            new_faults.append({
                "fault_code": 23,
                "fault_description": "String mất dòng đột ngột",
                "repair_instruction": f"Kiểm tra string {str_list} (MC4, cầu chì, đứt dây). Dòng giảm >3A về 0A.",
                "severity": "WARNING",
                "created_at": polling_time
            })
    
        return new_faults

    def reset_daily(self):
        """Reset vào cuối ngày (gọi lúc 00:00)."""
        self.last_currents.clear()
        self.zero_current_start_time.clear()
        self.active_faults.clear()
        logger.info("[StringMonitor] Daily reset completed.")
