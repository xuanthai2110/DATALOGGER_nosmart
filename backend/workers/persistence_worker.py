import time
import logging
import threading
from backend.db_manager import CacheDB, RealtimeDB
from backend.services.energy_service import EnergyService
from backend.services.telemetry_service import TelemetryService
from backend.models.realtime import (
    InverterACRealtimeCreate, mpptRealtimeCreate, 
    stringRealtimeCreate, ProjectRealtimeCreate
)
from backend.core import settings

logger = logging.getLogger(__name__)


def _num(value, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

class PersistenceWorker(threading.Thread):
    def __init__(self, cache_db: CacheDB, realtime_db: RealtimeDB, energy_service: EnergyService, interval: float = 300.0, string_monitor=None):
        super().__init__()
        self.cache_db = cache_db
        self.realtime_db = realtime_db
        self.energy_service = energy_service
        self.string_monitor = string_monitor # Tham chiếu đến service theo dõi string
        self.telemetry = TelemetryService(realtime_db)
        self.interval = interval
        self.daemon = True
        self._stop_event = threading.Event()
        self._last_purge_date = None

    def run(self):
        logger.info(f"Persistence Worker started (Interval: {self.interval}s)")
        while not self._stop_event.is_set():
            try:
                self._save_snapshot()
            except Exception as e:
                logger.error(f"Error in Persistence Worker snapshot: {e}")
            time.sleep(self.interval)

    def _save_snapshot(self):
        # 0. Thực hiện dọn dẹp dữ liệu cũ (Purge) vào lúc 00:00 hàng ngày
        now = time.localtime()
        if now.tm_hour == 0:
            current_date = f"{now.tm_year}-{now.tm_mon}-{now.tm_mday}"
            if self._last_purge_date != current_date:
                try:
                    self.realtime_db.purge_old_data(settings.DATA_RETENTION_DAYS)
                    if self.string_monitor:
                        self.string_monitor.reset_daily()
                    self._last_purge_date = current_date
                except Exception as e:
                    logger.error(f"Persistence Worker: Error during daily purge at 00:00: {e}")

        logger.info("Persistence Worker: Saving snapshot to disk...")
        
        # 1. Fetch all cache data (wrapped in batch_lock for consistency)
        with self.cache_db.batch_lock:
            ac_rows = self.cache_db.get_all_ac_cache()
            mppt_rows = self.cache_db.get_all_mppt_cache()
            string_rows = self.cache_db.get_all_string_cache()
        
        if not ac_rows:
            logger.info("Persistence Worker: No AC data in cache. Skipping snapshot.")
            return

        project_inverter_ids = {}
        for ac in ac_rows:
            project_inverter_ids.setdefault(ac["project_id"], []).append(ac["inverter_id"])

        sleep_projects = {
            project_id
            for project_id, inverter_ids in project_inverter_ids.items()
            if self.telemetry.is_all_inverters_sleep(inverter_ids, self.cache_db)
        }

        if sleep_projects:
            logger.info(f"Persistence Worker: Skipping snapshot for all-sleep projects: {sorted(sleep_projects)}")

        project_aggs = {} # project_id -> {metrics}

        # 2. Process Inverter AC & Start Project Aggregation
        ac_records = []
        for ac in ac_rows:
            inv_id = ac["inverter_id"]
            proj_id = ac["project_id"]
            if proj_id in sleep_projects:
                continue
            polling_time = ac["updated_at"]
            
            delta_e = _num(ac.get("delta_E_monthly"))
            e_month = _num(ac.get("E_monthly"))
            e_total = _num(ac.get("E_total"))
            e_daily = _num(ac.get("E_daily"))
            temp_c = _num(ac.get("Temp_C"))

            p_ac_kw = round(_num(ac.get("P_ac")) / 1000.0, 3)
            q_ac_kvar = round(_num(ac.get("Q_ac")) / 1000.0, 3)

            ac_records.append(InverterACRealtimeCreate(
                project_id=proj_id, inverter_id=inv_id,
                IR=_num(ac.get("IR")), Temp_C=temp_c,
                P_ac=p_ac_kw, Q_ac=q_ac_kvar,
                V_a=_num(ac.get("V_a")), V_b=_num(ac.get("V_b")), V_c=_num(ac.get("V_c")),
                I_a=_num(ac.get("I_a")), I_b=_num(ac.get("I_b")), I_c=_num(ac.get("I_c")),
                PF=_num(ac.get("PF")), H=_num(ac.get("H")),
                E_daily=e_daily,
                delta_E_monthly=delta_e,
                E_monthly=e_month,
                E_total=e_total,
                created_at=polling_time
            ))

            if proj_id not in project_aggs:
                project_aggs[proj_id] = {
                    "Temp_C": 0, "P_ac": 0, "P_dc": 0,
                    "E_daily": 0, "delta_E_monthly": 0, "E_monthly": 0, "E_total": 0,
                    "count": 0, "time": polling_time
                }
            agg = project_aggs[proj_id]
            agg["Temp_C"] += temp_c
            agg["P_ac"] += p_ac_kw
            agg["E_daily"] += e_daily
            agg["delta_E_monthly"] += delta_e
            agg["E_monthly"] += e_month
            agg["E_total"] += e_total
            agg["count"] += 1

            # Commit energy mốc tham chiếu cho EnergyService
            self.energy_service.commit_snapshot(inv_id, ac.get("E_total"))

        # 3. Process MPPT & Aggregate P_dc
        mppt_records = []
        for item in mppt_rows:
            p_mppt_kw = round(_num(item.get("P_mppt")) / 1000.0, 3)
            max_p_kw = round(_num(item.get("Max_P")) / 1000.0, 3)
            proj_id = item["project_id"]
            if proj_id in sleep_projects:
                continue
            
            mppt_records.append(mpptRealtimeCreate(
                project_id=proj_id,
                inverter_id=item["inverter_id"],
                mppt_index=item["mppt_index"],
                string_on_mppt=0,
                V_mppt=_num(item.get("V_mppt")),
                I_mppt=_num(item.get("I_mppt")),
                P_mppt=p_mppt_kw,
                Max_I=_num(item.get("Max_I")),
                Max_V=_num(item.get("Max_V")),
                Max_P=max_p_kw,
                created_at=item.get("updated_at", "")
            ))
            
            if proj_id in project_aggs:
                project_aggs[proj_id]["P_dc"] += p_mppt_kw

        # 4. Process String
        string_records = []
        for item in string_rows:
            if item["project_id"] in sleep_projects:
                continue
            string_records.append(stringRealtimeCreate(
                project_id=item["project_id"],
                inverter_id=item["inverter_id"],
                mppt_id=item["mppt_id"],
                string_id=item["string_id"],
                I_string=_num(item.get("I_string")),
                max_I=_num(item.get("max_I")),
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
