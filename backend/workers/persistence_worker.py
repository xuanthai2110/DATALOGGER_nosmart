import time
import logging
import threading
from backend.db_manager import CacheDB, RealtimeDB
from backend.services.energy_service import EnergyService
from backend.models.realtime import (
    InverterACRealtimeCreate, mpptRealtimeCreate, 
    stringRealtimeCreate, ProjectRealtimeCreate
)
from backend.core import config

logger = logging.getLogger(__name__)

class PersistenceWorker(threading.Thread):
    def __init__(self, cache_db: CacheDB, realtime_db: RealtimeDB, energy_service: EnergyService, interval: float = 300.0):
        super().__init__()
        self.cache_db = cache_db
        self.realtime_db = realtime_db
        self.energy_service = energy_service
        self.interval = interval
        self.daemon = True
        self._stop_event = threading.Event()

    def run(self):
        logger.info(f"Persistence Worker started (Interval: {self.interval}s)")
        while not self._stop_event.is_set():
            try:
                self._save_snapshot()
            except Exception as e:
                logger.error(f"Error in Persistence Worker snapshot: {e}")
            time.sleep(self.interval)

    def _save_snapshot(self):
        logger.info("Persistence Worker: Saving snapshot to disk...")
        ac_rows = self.cache_db.get_all_ac_cache()
        if not ac_rows: return

        # 1. AC & Error Snapshot
        ac_records = []
        for ac in ac_rows:
            inv_id = ac["inverter_id"]
            proj_id = ac["project_id"]
            polling_time = ac["updated_at"]
            
            # Ghi AC
            rec = InverterACRealtimeCreate(
                project_id=proj_id, inverter_id=inv_id,
                IR=ac.get("IR", 0), Temp_C=ac.get("Temp_C", 0),
                P_ac=ac.get("P_ac", 0), Q_ac=ac.get("Q_ac", 0),
                V_a=ac.get("V_a", 0), V_b=ac.get("V_b", 0), V_c=ac.get("V_c", 0),
                I_a=ac.get("I_a", 0), I_b=ac.get("I_b", 0), I_c=ac.get("I_c", 0),
                PF=ac.get("PF", 0), H=ac.get("H", 0),
                E_daily=ac.get("E_daily", 0), 
                E_monthly=ac.get("E_monthly", 0),
                E_total=ac.get("E_total", 0),
                created_at=polling_time
            )
            ac_records.append(rec)
            # Commit energy mốc tham chiếu
            self.energy_service.commit_snapshot(inv_id, ac.get("E_total", 0))

        if ac_records:
            self.realtime_db.post_inverter_ac_batch(ac_records)
            logger.info(f"Persistence Worker: Saved {len(ac_records)} inverter records to disk.")

        # 2. MPPT Snapshot
        mppt_rows = self.cache_db.get_all_mppt_cache()
        if mppt_rows:
            mppt_records = []
            for item in mppt_rows:
                rec = mpptRealtimeCreate(
                    project_id=item["project_id"],
                    inverter_id=item["inverter_id"],
                    mppt_index=item["mppt_index"],
                    string_on_mppt=0,
                    V_mppt=item.get("V_mppt", 0),
                    I_mppt=item.get("I_mppt", 0),
                    P_mppt=item.get("P_mppt", 0),
                    Max_I=item.get("Max_I", 0),
                    Max_V=item.get("Max_V", 0),
                    Max_P=item.get("Max_P", 0),
                    created_at=item.get("updated_at", "")
                )
                mppt_records.append(rec)
            self.realtime_db.post_mppt_batch(mppt_records)
            logger.info(f"Persistence Worker: Saved {len(mppt_records)} MPPT records to disk.")

        # 3. String Snapshot
        string_rows = self.cache_db.get_all_string_cache()
        if string_rows:
            string_records = []
            for item in string_rows:
                rec = stringRealtimeCreate(
                    project_id=item["project_id"],
                    inverter_id=item["inverter_id"],
                    mppt_id=item["mppt_id"],
                    string_id=item["string_id"],
                    I_string=item.get("I_string", 0),
                    max_I=item.get("max_I", 0),
                    created_at=item.get("updated_at", "")
                )
                string_records.append(rec)
            self.realtime_db.post_string_batch(string_records)
            logger.info(f"Persistence Worker: Saved {len(string_records)} String records to disk.")
