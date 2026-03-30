import sys
import os
import logging
import time
from datetime import datetime

# 1. Thêm đường dẫn gốc của project vào sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import MetadataDB, CacheDB, RealtimeDB
from workers.polling_worker import PollingWorker
from workers.logic_worker import LogicWorker
from workers.persistence_worker import PersistenceWorker
from workers.uploader_worker import UploaderWorker
from services.fault_service import FaultService
from core import config

# 2. Cấu hình Logging tập trung (Sau này sẽ move vào core/logger.py)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("polling.log")]
)

logger = logging.getLogger("Launcher")

def main():
    try:
        logger.info("Starting Datalogger 6-Threads Modular Architecture...")
        
        # 1. Khởi tạo Database Layer
        metadata_db = MetadataDB(config.METADATA_DB)
        cache_db = CacheDB(config.CACHE_DB)
        realtime_db = RealtimeDB(config.REALTIME_DB)
        
        # 2. Khởi tạo Logic Services
        fault_service = FaultService(realtime_db, metadata_db)
        
        # 3. KHỞI CHẠY CÁC WORKERS (THREADS)
        
        # L1: Polling Worker (10s/lần)
        poll_worker = PollingWorker(metadata_db, cache_db, config.POLL_INTERVAL)
        poll_worker.start()
        
        # L2: Logic Worker (1s/lần - Xử lý E, Max, Fault + Instant Trigger)
        logic_worker = LogicWorker(cache_db, metadata_db, realtime_db, fault_service)
        logic_worker.start()
        
        # L3: Persistence Worker (5p/lần - Snapshot RAM -> Disk)
        persist_worker = PersistenceWorker(cache_db, realtime_db, logic_worker.energy_service, config.SNAPSHOT_INTERVAL)
        persist_worker.start()
        
        # L4: Uploader Worker (5p/lần - Periodic Upload)
        upload_worker = UploaderWorker(realtime_db, config.SNAPSHOT_INTERVAL)
        upload_worker.start()
        
        logger.info("All workers started successfully. Monitoring mode active.")
        
        # Luồng chính giữ cho chương trình chạy và có thể in Dashboard định kỳ
        while True:
            # Dashboard logic could go here
            time.sleep(10)

    except KeyboardInterrupt:
        logger.info("Stopping Datalogger...")
    except Exception as e:
        logger.error(f"Critical error in Launcher: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
