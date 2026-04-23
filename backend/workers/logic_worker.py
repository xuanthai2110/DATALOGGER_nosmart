import time
import json
import logging
import threading
import queue
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
        self._trigger_queue = queue.Queue()

    def trigger_project(self, project_id: int):
        """Kích hoạt xử lý logic cho 1 project (gọi bởi PollingWorker sau khi commit batch)."""
        self._trigger_queue.put(project_id)

    def run(self):
        logger.info("Logic worker started.")
        while not self._stop_event.is_set():
            try:
                # Chờ sự kiện kích hoạt theo project_id (chặn tối đa 1s để kiểm tra stop_event)
                try:
                    project_id = self._trigger_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                self._process(project_id)
                self._trigger_queue.task_done()
                
            except Exception as e:
                logger.error(f"Logic worker error: {e}", exc_info=True)

    def _process(self, project_id: int):
        """Xử lý logic (Energy, Max Tracking, Faults) cho toàn bộ Inverter trong 1 Project vừa quét xong."""
        ac_rows = self.cache_db.get_ac_cache_by_project(project_id)
        if not ac_rows: 
            return

        inverter_ids = [ac["inverter_id"] for ac in ac_rows]
        is_sleep = self.telemetry.is_all_inverters_sleep(inverter_ids, self.cache_db)

        for ac in ac_rows:
            inv_id = ac["inverter_id"]
            polling_time = ac["updated_at"]
            
            # 1. Tính toán sản lượng năng lượng (Energy Calculation)
            e_state = self.energy_service.calculate(inv_id, ac["E_total"])
            
            # 2. Cập nhật Max Tracking (Vmax, Pmax, Imax)
            mppts = self.cache_db.get_mppt_cache_by_inverter(inv_id)
            strings = self.cache_db.get_string_cache_by_inverter(inv_id)
            
            hold_zero_max = self.max_service.prepare_for_poll(inv_id, polling_time)
            if hold_zero_max:
                self.cache_db.reset_mppt_max(inv_id)
                self.cache_db.reset_string_max(inv_id)
            else:
                maxes = self.max_service.update(inv_id, mppts, strings, polling_time=polling_time)
                for mppt_idx, m_max in maxes.get("mppt", {}).items():
                    self.cache_db.update_mppt_max(inv_id, mppt_idx, m_max["Max_V"], m_max["Max_I"], m_max["Max_P"])
                for str_id, s_max_i in maxes.get("string", {}).items():
                    self.cache_db.update_string_max(inv_id, str_id, s_max_i)
            
            # 3. Xử lý Lỗi và Trạng thái (Faults & States)
            err_cache = self.cache_db.get_error_cache(inv_id)
            s_code = err_cache["status_code"] if err_cache else 0
            f_code = err_cache["fault_code"] if err_cache else 0
            
            errors, changed = self.fault_logic.process(inv_id, project_id, s_code, f_code, polling_time)
            
            if changed and not is_sleep:
                for err_dict in errors:
                    err_rec = InverterErrorCreate(
                        project_id=project_id,
                        inverter_id=inv_id,
                        fault_code=err_dict["fault_code"],
                        fault_description=err_dict["fault_description"],
                        repair_instruction=err_dict["repair_instruction"],
                        severity=err_dict["severity"],
                        created_at=err_dict["created_at"]
                    )
                    self.realtime_db.post_inverter_error(err_rec)

            # 4. Cập nhật Cache với các giá trị vừa tính toán (Monthly/Delta Energy)
            self.cache_db.update_ac_processed(inv_id, e_state["E_monthly"], e_state["current_delta"])
                
        # 5. Kích hoạt Build Telemetry ngay lập tức cho project này sau khi xử lý xong lô
        self._trigger_immediate(project_id)

    def _trigger_immediate(self, project_id: int):
        if self.build_tele_worker:
            logger.info(f"LogicWorker: Triggering immediate telemetry build for project {project_id}")
            self.build_tele_worker.trigger_now(project_id)
