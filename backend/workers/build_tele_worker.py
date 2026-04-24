import time
import logging
import threading
import queue
from datetime import datetime
from backend.db_manager import CacheDB, RealtimeDB
from backend.services.project_service import ProjectService
from backend.services.telemetry_service import TelemetryService

logger = logging.getLogger(__name__)

class BuildTeleWorker(threading.Thread):
    def __init__(self, cache_db: CacheDB, project_svc: ProjectService, realtime_db: RealtimeDB, interval: float = 300.0):
        super().__init__()
        self.cache_db = cache_db
        self.project_svc = project_svc
        self.realtime_db = realtime_db
        self.telemetry = TelemetryService(realtime_db)
        self.interval = interval
        self.daemon = True
        self._stop_event = threading.Event()
        self._trigger_queue = queue.Queue()
        self.max_outbox_rows = 1000
        self._disconnect_notified_projects = {}

    def stop(self):
        self._stop_event.set()

    def trigger_now(self, project_id: int):
        """Kích hoạt đóng gói ngay lập tức cho dự án cụ thể."""
        self._trigger_queue.put(project_id)

    def run(self):
        logger.info(f"BuildTeleWorker started (Interval: {self.interval}s)")
        
        last_periodic_run = 0
        
        while not self._stop_event.is_set():
            try:
                # Chờ trigger hoặc timeout
                project_id_to_build = None
                try:
                    # Chờ trong 1 giây để kiểm tra stop_event thường xuyên
                    project_id_to_build = self._trigger_queue.get(timeout=1.0)
                    logger.info(f"BuildTeleWorker: Event-triggered build for project {project_id_to_build}")
                except queue.Empty:
                    pass

                now = time.time()
                # Kiểm tra xem đã đến kỳ chạy định kỳ chưa (5 phút)
                is_periodic = (now - last_periodic_run) >= self.interval
                
                if project_id_to_build:
                    self._build_for_project(project_id_to_build)
                elif is_periodic:
                    logger.info("BuildTeleWorker: Periodic build for all projects")
                    projects = self.project_svc.get_projects()
                    for p in projects:
                        if p.server_id:
                            self._build_for_project(p.id)
                    last_periodic_run = now

            except Exception as e:
                logger.error(f"Error in BuildTeleWorker loop: {e}", exc_info=True)
            
            time.sleep(0.1)

    def _build_for_project(self, project_id: int):
        try:
            proj_meta = self.project_svc.get_project(project_id)
            if not proj_meta or not proj_meta.server_id:
                return

            invs = self.project_svc.get_inverters_by_project(project_id)
            active_invs = [inv for inv in invs if getattr(inv, "is_active", True)]
            inverter_ids = [inv.id for inv in active_invs]
            all_disconnect = self.telemetry.is_all_inverters_disconnect(inverter_ids, self.cache_db)
            disconnect_notified = self._disconnect_notified_projects.get(project_id, False)

            if all_disconnect and disconnect_notified:
                logger.info(f"BuildTeleWorker: Project {project_id} is still all DISCONNECT. Skipping duplicate disconnect telemetry.")
                return

            if not all_disconnect and disconnect_notified:
                self._disconnect_notified_projects.pop(project_id, None)
                logger.info(f"BuildTeleWorker: Project {project_id} exited all DISCONNECT state. Resuming normal telemetry.")

            payload_list = self.telemetry.build_payload_from_cache(
                project_id, proj_meta.server_id, active_invs, self.cache_db
            )
            
            if payload_list:
                payload = payload_list[0]
                
                # Logic lọc: Từ 16h chiều đến 7h sáng hôm sau, nếu P_dc <= 0 thì không lưu outbox
                current_hour = datetime.now().hour
                p_dc = payload.get("project", {}).get("P_dc", 0)
                
                is_night_dusk = (current_hour >= 16 or current_hour < 7)
                if is_night_dusk and p_dc <= 0:
                    logger.info(f"BuildTeleWorker: Project {project_id} P_dc is {p_dc} during Night/Dusk ({current_hour}h). Skipping outbox save.")
                    return

                # Lưu vào DB Outbox
                self.realtime_db.post_to_outbox(project_id, proj_meta.server_id, payload, data_type="Project")
                
                # Giới hạn 1000 hàng
                self._enforce_limit()
        except Exception as e:
            logger.error(f"BuildTeleWorker: Failed to build for project {project_id}: {e}")

    def _enforce_limit(self):
        """Xoá bớt các bản ghi cũ nếu vượt quá 1000."""
        try:
            self.realtime_db.trim_outbox(self.max_outbox_rows)
        except Exception as e:
            logger.error(f"BuildTeleWorker: Error enforcing outbox limit: {e}")
