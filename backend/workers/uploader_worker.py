import time
import logging
import threading
from backend.db_manager import CacheDB, MetadataDB, RealtimeDB
from backend.services.uploader_service import UploaderService
from backend.services.telemetry_service import TelemetryService

logger = logging.getLogger(__name__)

class UploaderWorker(threading.Thread):
    def __init__(self, cache_db: CacheDB, metadata_db: MetadataDB, realtime_db: RealtimeDB, upload_interval: float = 300.0):
        super().__init__()
        self.cache_db = cache_db
        self.metadata_db = metadata_db
        self.realtime_db = realtime_db
        self.uploader = UploaderService(realtime_db)
        self.telemetry = TelemetryService(realtime_db)
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
                # 1. Gửi lại outbox tồn đọng từ chu kỳ trước (nếu có)
                logger.info("Uploader Worker: Checking previous outbox for retry upload...")
                self.uploader.upload()

                # 2. Xây gói dữ liệu mới của chu kỳ này
                projects = self.metadata_db.get_projects()
                new_payloads = 0
                for proj in projects:
                    if not proj.server_id: continue
                    invs = self.metadata_db.get_inverters_by_project(proj.id)
                    payload_list = self.telemetry.build_payload_from_cache(proj.id, proj.server_id, invs, self.cache_db)
                    
                    if payload_list:
                        # 3. Quăng vào outbox trước để lỡ cúp điện thì không mất
                        self.realtime_db.post_to_outbox(proj.id, payload_list[0])
                        new_payloads += 1
                
                if new_payloads > 0:
                    logger.info(f"Uploader Worker: Generated {new_payloads} new payloads. Initiating upload...")
                    # 4. Gửi các gói mới vừa được đưa vào outbox
                    self.uploader.upload()

            except Exception as e:
                logger.error(f"Error in Uploader Worker cycle: {e}")
            
            time.sleep(self.upload_interval)
