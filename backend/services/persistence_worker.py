import time
import logging
import threading
from datetime import datetime
from backend.database import CacheDB, RealtimeDB
from backend.services.energy_service import EnergyService
from backend.models.realtime import InverterACRealtimeCreate, mpptRealtimeCreate, stringRealtimeCreate
import config

logger = logging.getLogger(__name__)

class PersistenceWorker(threading.Thread):
    def __init__(self, cache_db: CacheDB, realtime_db: RealtimeDB, energy_service: EnergyService, snapshot_interval: float = 300.0):
        super().__init__()
        self.cache_db = cache_db
        self.realtime_db = realtime_db
        self.energy_service = energy_service
        self.snapshot_interval = snapshot_interval
        self.daemon = True
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        logger.info(f"Persistence Worker started (Snapshot Interval: {self.snapshot_interval}s)")
        
        # Đợi một chút để Polling & Logic có dữ liệu ban đầu
        time.sleep(10) 
        
        while not self._stop_event.is_set():
            t_start = time.time()
            try:
                self._save_snapshots()
            except Exception as e:
                logger.error(f"Error in Persistence Worker cycle: {e}", exc_info=True)
            
            # Tính toán thời gian sleep để chu kỳ snapshot chính xác
            elapsed = time.time() - t_start
            sleep_time = max(1.0, self.snapshot_interval - elapsed)
            time.sleep(sleep_time)

    def _save_snapshots(self):
        logger.info("Executing periodic Snapshot (RAM -> Disk)...")
        now_str = datetime.now().isoformat()
        
        # 1. Lấy toàn bộ Project ID từ Cache
        with self.cache_db._connect() as conn:
            rows = conn.execute("SELECT DISTINCT project_id FROM inverter_ac_cache").fetchall()
            project_ids = [r["project_id"] for r in rows]

        for pid in project_ids:
            # A. Lấy dữ liệu AC đã xử lý
            ac_list = self.cache_db.get_ac_cache_by_project(pid)
            ac_records = []
            for ac in ac_list:
                inv_id = ac["inverter_id"]
                
                ac_records.append(InverterACRealtimeCreate(
                    project_id=pid,
                    inverter_id=inv_id,
                    IR=ac["IR"],
                    Temp_C=ac["Temp_C"],
                    P_ac=ac["P_ac"],
                    Q_ac=ac["Q_ac"],
                    V_a=ac["V_a"],
                    V_b=ac["V_b"],
                    V_c=ac["V_c"],
                    I_a=ac["I_a"],
                    I_b=ac["I_b"],
                    I_c=ac["I_c"],
                    PF=ac["PF"],
                    H=ac["H"],
                    E_daily=ac["E_daily"],
                    E_monthly=ac["E_monthly"],
                    E_total=ac["E_total"],
                    created_at=now_str
                ))
            
            if ac_records:
                self.realtime_db.post_inverter_ac_batch(ac_records)
                # 'Chốt' mốc tham chiếu sau khi đã lưu thành công
                for r in ac_records:
                    self.energy_service.commit_snapshot(r.inverter_id, r.E_total)

            # B. Lấy và ghi MPPT Snapshot
            mppt_list = self.cache_db.get_mppt_cache_by_project(pid)
            mppt_records = []
            for m in mppt_list:
                mppt_records.append(mpptRealtimeCreate(
                    project_id=pid,
                    inverter_id=m["inverter_id"],
                    mppt_index=m["mppt_index"],
                    V_mppt=m["V_mppt"],
                    I_mppt=m["I_mppt"],
                    P_mppt=m["P_mppt"],
                    Max_V=m["Max_V"],
                    Max_I=m["Max_I"],
                    Max_P=m["Max_P"],
                    created_at=now_str
                ))
            if mppt_records:
                self.realtime_db.post_mppt_batch(mppt_records)

            # C. Lấy và ghi String Snapshot
            string_list = self.cache_db.get_string_cache_by_project(pid)
            string_records = []
            for s in string_list:
                string_records.append(stringRealtimeCreate(
                    project_id=pid,
                    inverter_id=s["inverter_id"],
                    mppt_id=s["mppt_id"],
                    string_id=s["string_id"],
                    I_string=s["I_string"],
                    max_I=s["max_I"],
                    created_at=now_str
                ))
            if string_records:
                self.realtime_db.post_string_batch(string_records)

        logger.info(f"Snapshot completed at {now_str}. {len(project_ids)} projects saved.")
