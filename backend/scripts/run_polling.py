import sys
import os
import logging
import time
from pathlib import Path

# Add project root correctly
# script_dir = .../backend/scripts
# backend_dir = .../backend
# project_root = .../
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    # Insert at 0 to prioritize local modules
    sys.path.insert(0, str(PROJECT_ROOT))
    
# Debug print - check what's in sys.path
print(f"DEBUG - sys.path[0]: {sys.path[0]}")

# 2. Imports using absolute package names
from backend.db_manager import MetadataDB, CacheDB, RealtimeDB
from backend.workers.polling_worker import PollingWorker
from backend.workers.logic_worker import LogicWorker
from backend.workers.persistence_worker import PersistenceWorker
from backend.workers.uploader_worker import UploaderWorker
from backend.services.fault_service import FaultService
from backend.core import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Launcher")

def main():
    try:
        logger.info(f"System Path prioritized: {sys.path[0]}")
        logger.info("Starting Modular 6-Threads Datalogger...")
        
        # 1. DB Layer
        metadata_db = MetadataDB(config.METADATA_DB)
        cache_db = CacheDB(config.CACHE_DB)
        realtime_db = RealtimeDB(config.REALTIME_DB)
        
        # 2. Service Layer
        fault_service = FaultService(realtime_db, metadata_db)
        
        # 3. Worker Layer
        poll_worker = PollingWorker(metadata_db, cache_db, config.POLL_INTERVAL)
        logic_worker = LogicWorker(cache_db, metadata_db, realtime_db, fault_service)
        persist_worker = PersistenceWorker(cache_db, realtime_db, logic_worker.energy_service, config.SNAPSHOT_INTERVAL)
        upload_worker = UploaderWorker(realtime_db, config.SNAPSHOT_INTERVAL)
        
        # Start Threads
        poll_worker.start()
        logic_worker.start()
        persist_worker.start()
        upload_worker.start()
        
        logger.info("System operational. Press Ctrl+C to exit.")
        while True:
            time.sleep(10)

    except KeyboardInterrupt:
        logger.info("Shutdown requested.")
    except Exception as e:
        logger.error(f"Critical failure: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
