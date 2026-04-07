import time
import json
import logging
import threading
from backend.db_manager import CacheDB, RealtimeDB
from backend.services.project_service import ProjectService
from backend.services.energy_service import EnergyService
from backend.services.max_tracking_service import MaxTrackingService
from backend.services.fault_service import FaultService
from backend.services.telemetry_service import TelemetryService
from backend.services.uploader_service import UploaderService
from backend.models.realtime import (
    InverterErrorCreate
)
from backend.core import settings

logger = logging.getLogger(__name__)

class LogicWorker(threading.Thread):
    def __init__(self, cache_db, project_svc: ProjectService, realtime_db, fault_service, build_tele_worker=None):
        super().__init__()
        self.cache_db = cache_db
        self.project_svc = project_svc
        self.realtime_db = realtime_db
        self.fault_logic = fault_service
        self.energy_service = EnergyService(realtime_db)
        self.max_service = MaxTrackingService(realtime_db)
        self.telemetry = TelemetryService(realtime_db)
        self.build_tele_worker = build_tele_worker
        self.daemon = True
        self._stop_event = threading.Event()

    def run(self):
        logger.info("Logic worker started.")
        while not self._stop_event.is_set():
            try:
                self._process()
            except Exception as e:
                logger.error(f"Logic loop error: {e}")
            time.sleep(1)

    def _process(self):
        ac_rows = self.cache_db.get_all_ac_cache()
        if not ac_rows: return
        projects_to_trigger = set()
        project_inverter_ids = {}
        for ac in ac_rows:
            project_inverter_ids.setdefault(ac["project_id"], []).append(ac["inverter_id"])

        sleep_projects = {
            project_id
            for project_id, inverter_ids in project_inverter_ids.items()
            if self.telemetry.is_all_inverters_sleep(inverter_ids, self.cache_db)
        }

        for ac in ac_rows:
            inv_id, proj_id = ac["inverter_id"], ac["project_id"]
            polling_time = ac["updated_at"]
            e_state = self.energy_service.calculate(inv_id, ac["E_total"])
            mppts = self.cache_db.get_mppt_cache_by_inverter(inv_id)
            strings = self.cache_db.get_string_cache_by_inverter(inv_id)
            
            # Update Max Tracking (Vmax, Pmax, Imax)
            hold_zero_max = self.max_service.prepare_for_poll(inv_id, polling_time)
            if hold_zero_max:
                self.cache_db.reset_mppt_max(inv_id)
                self.cache_db.reset_string_max(inv_id)
            self.max_service.update(inv_id, mppts, strings, polling_time=polling_time) if not hold_zero_max else None
            
            # Process Faults and States
            err_cache = self.cache_db.get_error_cache(inv_id)
            s_code = err_cache["status_code"] if err_cache else 0
            f_code = err_cache["fault_code"] if err_cache else 0
            
            errors, changed = self.fault_logic.process(inv_id, proj_id, s_code, f_code, polling_time)
            
            # Skip inverter_errors only when the whole project is sleeping.
            if changed:
                if proj_id not in sleep_projects:
                    for err_dict in errors:
                        err_rec = InverterErrorCreate(
                            project_id=proj_id,
                            inverter_id=inv_id,
                            fault_code=err_dict["fault_code"],
                            fault_description=err_dict["fault_description"],
                            repair_instruction=err_dict["repair_instruction"],
                            severity=err_dict["severity"],
                            created_at=err_dict["created_at"]
                        )
                        self.realtime_db.post_inverter_error(err_rec)

            # Update cache with calculated energy values
            self.cache_db.update_ac_processed(inv_id, e_state["E_monthly"], e_state["current_delta"])
            
            if changed: 
                projects_to_trigger.add(proj_id)
                
        for pid in projects_to_trigger:
            self._trigger_immediate(pid)

    def _trigger_immediate(self, project_id: int):
        if self.build_tele_worker:
            logger.info(f"LogicWorker: Triggering immediate telemetry build for project {project_id}")
            self.build_tele_worker.trigger_now(project_id)
