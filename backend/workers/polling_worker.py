import time
import logging
import threading
from database import MetadataDB, CacheDB
from services.polling_service import PollingService
import config

logger = logging.getLogger(__name__)

class PollingWorker(threading.Thread):
    def __init__(self, metadata_db: MetadataDB, cache_db: CacheDB, interval: float = 10.0):
        super().__init__()
        self.service = PollingService(metadata_db, cache_db)
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
                    # 2. Quét dữ liệu Modbus
                    self.service.poll_all_inverters(project.id, inverters=inverters)
                    
            except Exception as e:
                logger.error(f"Error in Polling Worker cycle: {e}")
            
            elapsed = time.time() - t0
            sleep_time = max(0.1, self.interval - elapsed)
            time.sleep(sleep_time)
