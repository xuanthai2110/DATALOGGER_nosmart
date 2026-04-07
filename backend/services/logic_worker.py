import time
import json
import logging
import threading
from backend.db_manager import CacheDB, MetadataDB, RealtimeDB
from backend.services.energy_service import EnergyService
from backend.services.max_tracking_service import MaxTrackingService
from backend.services.fault_logic_service import FaultLogicService
from backend.services.fault_state_service import FaultStateService
from backend.services.telemetry_service import TelemetryService
from backend.services.uploader_service import UploaderService
from backend.core import settings

logger = logging.getLogger(__name__)

class LogicWorker(threading.Thread):
    def __init__(self, 
                 cache_db: CacheDB, 
                 metadata_db: MetadataDB, 
                 realtime_db: RealtimeDB,
                 fault_state_service: FaultStateService,
                 poll_interval: float = 1.0):
        super().__init__()
        self.cache_db = cache_db
        self.metadata_db = metadata_db
        self.realtime_db = realtime_db
        
        # Modular Services
        self.energy_service = EnergyService(realtime_db)
        self.max_service = MaxTrackingService(realtime_db)
        self.fault_logic = FaultLogicService(realtime_db, metadata_db, fault_state_service)
        
        # Telemetry & Upload for Instant Events
        self.telemetry = TelemetryService(realtime_db)
        self.uploader = UploaderService(realtime_db)
        
        self.poll_interval = poll_interval
        self.daemon = True
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        logger.info("Logic Worker (Modular + Event Trigger) started (Interval: 1s)")
        while not self._stop_event.is_set():
            try:
                self._process_cycle()
            except Exception as e:
                logger.error(f"Error in Logic Worker cycle: {e}", exc_info=True)
            
            time.sleep(self.poll_interval)

    def _process_cycle(self):
        # 1. Lấy toàn bộ Inverter AC Cache (Nguồn thô)
        ac_rows = self.cache_db.get_all_ac_cache()
        if not ac_rows:
            return

        # Nhóm theo project để xử lý event trigger theo project
        projects_to_trigger = set()

        for ac in ac_rows:
            inv_id = ac["inverter_id"]
            proj_id = ac["project_id"]
            polling_time = ac["updated_at"]
            
            # A. Energy Logic
            e_state = self.energy_service.calculate(inv_id, ac["E_total"])
            
            # B. Max Logic
            mppt_rows = self.cache_db.get_mppt_cache_by_inverter(inv_id)
            string_rows = self.cache_db.get_string_cache_by_inverter(inv_id)
            max_results = self.max_service.update(inv_id, mppt_rows, string_rows)
            
            # C. Fault Logic & Change Detection
            err_row = self.cache_db.get_error_cache(inv_id)
            s_code = err_row["status_code"] if err_row else 0
            f_code = err_row["fault_code"] if err_row else 0
            
            errors_payload, has_changed = self.fault_logic.process(inv_id, proj_id, s_code, f_code, polling_time)
            
            # D. WRITE BACK (Processed Data)
            # Lưu E_monthly, Max và đặc biệt là fault_json
            self._write_results(inv_id, proj_id, e_state, max_results, errors_payload, s_code, f_code)
            
            if has_changed:
                projects_to_trigger.add(proj_id)

        # 2. EVENT TRIGGER: Gửi telemetry ngay lập tức nếu có biến động
        for pid in projects_to_trigger:
            self._trigger_immediate_upload(pid)

    def _write_results(self, inv_id, proj_id, e_state, max_results, errors_payload, s_code, f_code):
        # Ghi AC
        self.cache_db.update_ac_processed(inv_id, e_state["E_monthly"], e_state["current_delta"])
        
        # Ghi MPPT & String Max (Hàm helper trong sqlite_manager nếu có, ở đây tôi gọi tuần tự)
        # Giả định các hàm này tồn tại hoặc dùng connect() trực tiếp
        with self.cache_db._connect() as conn:
            # MPPT
            for idx, vals in max_results.get("mppt", {}).items():
                conn.execute("UPDATE mppt_cache SET Max_V=?, Max_I=?, Max_P=? WHERE inverter_id=? AND mppt_index=?", 
                             (vals["Max_V"], vals["Max_I"], vals["Max_P"], inv_id, idx))
            # String
            for sid, val in max_results.get("string", {}).items():
                conn.execute("UPDATE string_cache SET max_I=? WHERE inverter_id=? AND string_id=?", (val, inv_id, sid))
            
            # ERROR JSON
            fault_json = json.dumps(errors_payload)
            self.cache_db.upsert_error(inv_id, proj_id, s_code, f_code, fault_json=fault_json)

    def _trigger_immediate_upload(self, project_id: int):
        """Kích hoạt gửi Telemetry ngay lập tức lên server cho dự án có biến động"""
        try:
            proj_meta = self.metadata_db.get_project_by_id(project_id)
            if not proj_meta or not proj_meta.server_id:
                return

            inverters = self.metadata_db.get_inverters_by_project(project_id)
            
            # Build full payload
            payload = self.telemetry.build_payload_from_cache(project_id, proj_meta.server_id, inverters, self.cache_db)
            
            if payload:
                logger.info(f"EVENT: Triggering immediate upload for project {project_id} (server_id: {proj_meta.server_id})")
                self.uploader.send_immediate(payload[0])
        except Exception as e:
            logger.error(f"Failed to trigger immediate upload for project {project_id}: {e}")
