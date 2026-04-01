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
        
        # 1. Fetch all cache data
        ac_rows = self.cache_db.get_all_ac_cache()
        mppt_rows = self.cache_db.get_all_mppt_cache()
        string_rows = self.cache_db.get_all_string_cache()
        
        if not ac_rows:
            logger.info("Persistence Worker: No AC data in cache. Skipping snapshot.")
            return

        project_aggs = {} # project_id -> {metrics}

        # 2. Process Inverter AC & Start Project Aggregation
        ac_records = []
        for ac in ac_rows:
            inv_id = ac["inverter_id"]
            proj_id = ac["project_id"]
            polling_time = ac["updated_at"]
            
            delta_e = ac.get("delta_E_monthly", 0)
            e_month = ac.get("E_monthly", 0)

            p_ac_kw = round(ac.get("P_ac", 0) / 1000.0, 3)
            q_ac_kvar = round(ac.get("Q_ac", 0) / 1000.0, 3)

            ac_records.append(InverterACRealtimeCreate(
                project_id=proj_id, inverter_id=inv_id,
                IR=ac.get("IR", 0), Temp_C=ac.get("Temp_C", 0),
                P_ac=p_ac_kw, Q_ac=q_ac_kvar,
                V_a=ac.get("V_a", 0), V_b=ac.get("V_b", 0), V_c=ac.get("V_c", 0),
                I_a=ac.get("I_a", 0), I_b=ac.get("I_b", 0), I_c=ac.get("I_c", 0),
                PF=ac.get("PF", 0), H=ac.get("H", 0),
                E_daily=ac.get("E_daily", 0), 
                delta_E_monthly=delta_e,
                E_monthly=e_month,
                E_total=ac.get("E_total", 0),
                created_at=polling_time
            ))

            if proj_id not in project_aggs:
                project_aggs[proj_id] = {
                    "Temp_C": 0, "P_ac": 0, "P_dc": 0,
                    "E_daily": 0, "delta_E_monthly": 0, "E_monthly": 0, "E_total": 0,
                    "count": 0, "time": polling_time
                }
            agg = project_aggs[proj_id]
            agg["Temp_C"] += ac.get("Temp_C", 0)
            agg["P_ac"] += p_ac_kw
            agg["E_daily"] += ac.get("E_daily", 0)
            agg["delta_E_monthly"] += delta_e
            agg["E_monthly"] += e_month
            agg["E_total"] += ac.get("E_total", 0)
            agg["count"] += 1

            # Commit energy mốc tham chiếu cho EnergyService
            self.energy_service.commit_snapshot(inv_id, ac.get("E_total", 0))

        # 3. Process MPPT & Aggregate P_dc
        mppt_records = []
        for item in mppt_rows:
            p_mppt_kw = round(item.get("P_mppt", 0) / 1000.0, 3)
            max_p_kw = round(item.get("Max_P", 0) / 1000.0, 3)
            proj_id = item["project_id"]
            
            mppt_records.append(mpptRealtimeCreate(
                project_id=proj_id,
                inverter_id=item["inverter_id"],
                mppt_index=item["mppt_index"],
                string_on_mppt=0,
                V_mppt=item.get("V_mppt", 0),
                I_mppt=item.get("I_mppt", 0),
                P_mppt=p_mppt_kw,
                Max_I=item.get("Max_I", 0),
                Max_V=item.get("Max_V", 0),
                Max_P=max_p_kw,
                created_at=item.get("updated_at", "")
            ))
            
            if proj_id in project_aggs:
                project_aggs[proj_id]["P_dc"] += p_mppt_kw

        # 4. Process String
        string_records = []
        for item in string_rows:
            string_records.append(stringRealtimeCreate(
                project_id=item["project_id"],
                inverter_id=item["inverter_id"],
                mppt_id=item["mppt_id"],
                string_id=item["string_id"],
                I_string=item.get("I_string", 0),
                max_I=item.get("max_I", 0),
                created_at=item.get("updated_at", "")
            ))

        # 5. Final Persist to RealtimeDB
        if ac_records:
            self.realtime_db.post_inverter_ac_batch(ac_records)
            logger.info(f"Persistence Worker: Saved {len(ac_records)} inverter AC records.")

        if mppt_records:
            self.realtime_db.post_mppt_batch(mppt_records)
            logger.info(f"Persistence Worker: Saved {len(mppt_records)} MPPT records.")

        if string_records:
            self.realtime_db.post_string_batch(string_records)
            logger.info(f"Persistence Worker: Saved {len(string_records)} String records.")

        for pid, agg in project_aggs.items():
            if agg["count"] > 0:
                p_rec = ProjectRealtimeCreate(
                    project_id=pid,
                    Temp_C=round(agg["Temp_C"] / agg["count"], 2),
                    P_ac=round(agg["P_ac"], 2),
                    P_dc=round(agg["P_dc"], 2),
                    E_daily=round(agg["E_daily"], 2),
                    delta_E_monthly=round(agg["delta_E_monthly"], 2),
                    E_monthly=round(agg["E_monthly"], 2),
                    E_total=round(agg["E_total"], 2),
                    severity="STABLE", # TODO: Aggregate from inverter severities
                    created_at=agg["time"]
                )
                self.realtime_db.post_project_realtime(p_rec)
        
        if project_aggs:
            logger.info(f"Persistence Worker: Saved {len(project_aggs)} project aggregates.")
