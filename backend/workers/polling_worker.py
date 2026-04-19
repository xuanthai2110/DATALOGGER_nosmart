import time
import logging
import threading
from backend.db_manager import CacheDB
from backend.services.polling_service import PollingService
from backend.services.project_service import ProjectService
from backend.core import settings

logger = logging.getLogger(__name__)

class PollingWorker(threading.Thread):
    def __init__(self, project_svc: ProjectService, cache_db: CacheDB, interval: float = 10.0):
        super().__init__()
        self.service = PollingService(project_svc, cache_db)
        self.interval = interval
        self.daemon = True
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        logger.info(f"Polling Worker started (Interval: {self.interval}s)")
        while not self._stop_event.is_set():
            t0 = time.time()
            try:
                # 1. Lấy cấu hình từ cache (hoặc database nếu hết hạn)
                polling_config = self.service.get_polling_config()
                
                for item in polling_config:
                    project = item["project"]
                    inverters = item["inverters"]
                    meters = item.get("meters", [])
                    # 2. Quét dữ liệu Modbus
                    self.service.poll_all_inverters(project.id, inverters=inverters)
                    self.service.poll_meters(project.id, meters=meters)
                    
            except Exception as e:
                logger.error(f"Error in Polling Worker cycle: {e}")
            
            elapsed = time.time() - t0
            sleep_time = max(0.1, self.interval - elapsed)
            time.sleep(sleep_time)
