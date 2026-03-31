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
            payload_list = self.telemetry.build_payload_from_cache(
                project_id, proj_meta.server_id, invs, self.cache_db
            )
            
            if payload_list:
                # Lưu vào DB Outbox
                self.realtime_db.post_to_outbox(project_id, proj_meta.server_id, payload_list[0])
                logger.info(f"BuildTeleWorker: Payload saved to outbox for project {project_id}")
                
                # Giới hạn 1000 hàng
                self._enforce_limit()
        except Exception as e:
            logger.error(f"BuildTeleWorker: Failed to build for project {project_id}: {e}")

    def _enforce_limit(self):
        """Xoá bớt các bản ghi cũ nếu vượt quá 1000."""
        try:
            # Ta cần một phương thức đếm và xoá trong RealtimeDB
            # Hiện tại RealtimeDB chưa có hàm này, ta sẽ tạm thời viết logic ở đây
            # hoặc bổ sung vào RealtimeDB sau.
            with self.realtime_db._connect() as conn:
                count = conn.execute("SELECT COUNT(*) FROM uploader_outbox").fetchone()[0]
                if count > self.max_outbox_rows:
                    to_delete = count - self.max_outbox_rows
                    # Lấy ID của N bản ghi cũ nhất
                    old_ids = conn.execute(
                        f"SELECT id FROM uploader_outbox ORDER BY id ASC LIMIT {to_delete}"
                    ).fetchall()
                    ids = [r[0] for r in old_ids]
                    if ids:
                        placeholders = ",".join(["?"] * len(ids))
                        conn.execute(f"DELETE FROM uploader_outbox WHERE id IN ({placeholders})", ids)
                        logger.warning(f"BuildTeleWorker: Outbox limit reached. Deleted {len(ids)} oldest records.")
        except Exception as e:
            logger.error(f"BuildTeleWorker: Error enforcing outbox limit: {e}")
