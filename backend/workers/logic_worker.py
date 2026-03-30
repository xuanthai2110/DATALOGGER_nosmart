import time
import json
import logging
import threading
from backend.db_manager import CacheDB, MetadataDB, RealtimeDB
from backend.services.energy_service import EnergyService
from backend.services.max_tracking_service import MaxTrackingService
from backend.services.fault_service import FaultService
from backend.services.telemetry_service import TelemetryService
from backend.services.uploader_service import UploaderService
from backend.core import config

logger = logging.getLogger(__name__)

class LogicWorker(threading.Thread):
    def __init__(self, cache_db, metadata_db, realtime_db, fault_service):
        super().__init__()
        self.cache_db = cache_db
        self.metadata_db = metadata_db
        self.realtime_db = realtime_db
        self.fault_logic = fault_service
        self.energy_service = EnergyService(realtime_db)
        self.max_service = MaxTrackingService(realtime_db)
        self.telemetry = TelemetryService(realtime_db)
        self.uploader = UploaderService(realtime_db)
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
        for ac in ac_rows:
            inv_id, proj_id = ac["inverter_id"], ac["project_id"]
            e_state = self.energy_service.calculate(inv_id, ac["E_total"])
            mppts = self.cache_db.get_mppt_cache_by_inverter(inv_id)
            strings = self.cache_db.get_string_cache_by_inverter(inv_id)
            max_res = self.max_service.update(inv_id, mppts, strings)
            err = self.cache_db.get_error_cache(inv_id)
            s_code = err["status_code"] if err else 0
            f_code = err["fault_code"] if err else 0
            payload, changed = self.fault_logic.process(inv_id, proj_id, s_code, f_code, ac["updated_at"])
            self.cache_db.update_ac_processed(inv_id, e_state["E_monthly"], e_state["current_delta"])
            if changed: projects_to_trigger.add(proj_id)
        for pid in projects_to_trigger:
            self._trigger_immediate(pid)

    def _trigger_immediate(self, project_id: int):
        proj_meta = self.metadata_db.get_project(project_id)
        if proj_meta and proj_meta.server_id:
            invs = self.metadata_db.get_inverters_by_project(project_id)
            data = self.telemetry.build_payload_from_cache(project_id, proj_meta.server_id, invs, self.cache_db)
            if data: self.uploader.send_immediate(data[0])
