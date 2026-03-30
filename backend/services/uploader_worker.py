import time
import logging
import threading
from database.sqlite_manager import RealtimeDB
from services.uploader_service import UploaderService
import config

logger = logging.getLogger(__name__)

class UploaderWorker(threading.Thread):
    def __init__(self, realtime_db: RealtimeDB, upload_interval: float = 300.0):
        super().__init__()
        self.uploader = UploaderService(realtime_db)
        self.upload_interval = upload_interval
        self.daemon = True
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        logger.info(f"Uploader Worker started (Interval: {self.upload_interval}s)")
        
        # Đợi Persistence Worker chạy xong lượt Snapshot đầu tiên
        time.sleep(15)
        
        while not self._stop_event.is_set():
            try:
                logger.info("Uploader Worker: Checking outbox for periodic upload...")
                self.uploader.upload()
            except Exception as e:
                logger.error(f"Error in Uploader Worker cycle: {e}")
            
            time.sleep(self.upload_interval)
