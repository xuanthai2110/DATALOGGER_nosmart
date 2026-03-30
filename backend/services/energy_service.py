import logging
from datetime import date
from typing import Dict
from database import RealtimeDB

logger = logging.getLogger(__name__)

class EnergyService:
    def __init__(self, realtime_db: RealtimeDB):
        self.realtime_db = realtime_db
        # RAM state: {inverter_id: {"base_monthly": float, "last_snap_total": float, "current_delta": float, "E_monthly": float}}
        self.energy_state: Dict[int, Dict[str, float]] = {}
        self.seed_date: Dict[int, date] = {}

    def seed_if_needed(self, inverter_id: int):
        """Nạp mốc thế năng từ RealtimeDB (Disk) vào RAM khi khởi động"""
        today = date.today()
        if self.seed_date.get(inverter_id) == today:
            return

        # 1. Lấy snapshot cuối cùng trên Disk
        last_snap = self.realtime_db.get_latest_inverter_ac_realtime(inverter_id)
        
        # 2. Tính tổng delta trong tháng hiện tại từ Disk
        start_month = today.replace(day=1).isoformat()
        with self.realtime_db._connect() as conn:
            row = conn.execute("""
                SELECT SUM(delta_E_monthly) as total 
                FROM inverter_ac_realtime 
                WHERE inverter_id = ? AND created_at >= ?
            """, (inverter_id, start_month)).fetchone()
            current_month_delta_sum = row["total"] or 0.0

        self.energy_state[inverter_id] = {
            "base_monthly": current_month_delta_sum,
            "last_snap_total": last_snap.E_total if last_snap else 0.0,
            "current_delta": 0.0,
            "E_monthly": current_month_delta_sum
        }
        self.seed_date[inverter_id] = today
        logger.info(f"Energy seeded for inv {inverter_id}: Base={current_month_delta_sum}, LastSnap={last_snap.E_total if last_snap else 0}")

    def calculate(self, inverter_id: int, current_e_total: float) -> dict:
        """
        Tính toán E_monthly dựa trên hiệu số Delta từ mốc Snapshot cuối.
        Chỉ thực hiện trên RAM.
        """
        self.seed_if_needed(inverter_id)
        state = self.energy_state[inverter_id]
        
        delta = max(0.0, round(current_e_total - state["last_snap_total"], 2))
        
        # Chống nhảy số ảo (> 100kWh trong 10s là bất thường)
        if delta > 100.0:
            logger.warning(f"Abnormal large delta on inv {inverter_id}: {delta}. Capping.")
            delta = 0.0

        state["current_delta"] = delta
        state["E_monthly"] = round(state["base_monthly"] + delta, 2)
        
        return state

    def commit_snapshot(self, inverter_id: int, current_total: float):
        """Chốt mốc tham chiếu mới sau khi ghi Disk xong"""
        if inverter_id not in self.energy_state:
            return
            
        state = self.energy_state[inverter_id]
        state["base_monthly"] = round(state["base_monthly"] + state["current_delta"], 2)
        state["last_snap_total"] = current_total
        state["current_delta"] = 0.0
        
        logger.debug(f"Energy committed for inv {inverter_id}: New Base={state['base_monthly']}")
