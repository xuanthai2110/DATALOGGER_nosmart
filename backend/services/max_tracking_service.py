import logging
from datetime import date
from typing import Dict, Any
from backend.db_manager import RealtimeDB

logger = logging.getLogger(__name__)

class MaxTrackingService:
    def __init__(self, realtime_db: RealtimeDB):
        self.realtime_db = realtime_db
        # RAM state: {inverter_id: {mppt_index: {"Max_V": val, "Max_I": val, "Max_P": val}}}
        self.mppt_max: Dict[int, Dict[int, Dict[str, float]]] = {}
        # RAM state: {inverter_id: {string_id: max_I}}
        self.string_max: Dict[int, Dict[int, float]] = {}
        self.seed_date: Dict[int, date] = {}

    def seed_if_needed(self, inverter_id: int):
        """Seed max trong ngày từ snapshot mới nhất đã được ghi vào Disk"""
        today = date.today()
        if self.seed_date.get(inverter_id) == today:
            return

        self.mppt_max[inverter_id] = {}
        self.string_max[inverter_id] = {}

        # 1. MPPT Max Seed
        latest_mppts = self.realtime_db.get_latest_mppt_batch(inverter_id)
        if latest_mppts:
            try:
                from datetime import datetime
                record_date = datetime.fromisoformat(latest_mppts[0].created_at).date()
                if record_date == today:
                    self.mppt_max[inverter_id] = {
                        r.mppt_index: {"Max_V": r.Max_V, "Max_I": r.Max_I, "Max_P": r.Max_P}
                        for r in latest_mppts
                    }
            except Exception as e:
                logger.error(f"Error seeding MPPT max: {e}")

        # 2. String Max Seed
        latest_strings = self.realtime_db.get_latest_string_batch(inverter_id)
        if latest_strings:
            try:
                from datetime import datetime
                record_date = datetime.fromisoformat(latest_strings[0].created_at).date()
                if record_date == today:
                    self.string_max[inverter_id] = {r.string_id: r.max_I for r in latest_strings}
            except Exception as e:
                pass

        self.seed_date[inverter_id] = today
        logger.info(f"Max tracking state seeded for inv {inverter_id}")

    def update(self, inverter_id: int, mppt_rows: list, string_rows: list):
        """Cập nhật mốc Max hàng ngày từ dữ liệu thô vừa đọc được"""
        self.seed_if_needed(inverter_id)
        
        # 1. MPPT Max
        if inverter_id not in self.mppt_max: self.mppt_max[inverter_id] = {}
        for m in mppt_rows:
            idx = m["mppt_index"]
            v, i, p = m["V_mppt"], m["I_mppt"], m["P_mppt"]
            if idx not in self.mppt_max[inverter_id]:
                self.mppt_max[inverter_id][idx] = {"Max_V": v, "Max_I": i, "Max_P": p}
            else:
                curr = self.mppt_max[inverter_id][idx]
                curr["Max_V"] = max(curr["Max_V"], v)
                curr["Max_I"] = max(curr["Max_I"], i)
                curr["Max_P"] = max(curr["Max_P"], p)
                
        # 2. String Max
        if inverter_id not in self.string_max: self.string_max[inverter_id] = {}
        for s in string_rows:
            sid = s["string_id"]
            val = s["I_string"]
            self.string_max[inverter_id][sid] = max(self.string_max[inverter_id].get(sid, 0.0), val)
            
        return {
            "mppt": self.mppt_max.get(inverter_id, {}),
            "string": self.string_max.get(inverter_id, {})
        }
