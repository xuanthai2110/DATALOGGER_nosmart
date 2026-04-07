import time
import logging
from backend.core import settings
from backend.db_manager import MetadataDB, RealtimeDB, CacheDB
from backend.workers.polling_worker import PollingWorker
from backend.workers.logic_worker import LogicWorker
from backend.services.fault_service import FaultService

logger = logging.getLogger("LegacyMain")

def main():
    metadata_db = MetadataDB(settings.METADATA_DB)
    realtime_db = RealtimeDB(settings.REALTIME_DB)
    cache_db = CacheDB(settings.CACHE_DB)
    
    # 6-Threads Launcher should be the new way.
    # This main.py is kept for compatibility but should use the new Workers.
    logger.info("Starting legacy main.py using new Worker Architecture...")
    
    fault_service = FaultService(realtime_db, metadata_db)
    logic = LogicWorker(cache_db, metadata_db, realtime_db, fault_service)
    logic.start()
    
    poll_worker = PollingWorker(metadata_db, cache_db, settings.POLL_INTERVAL)
    poll_worker.run() # Run in main thread for legacy comportment

if __name__ == "__main__":
    main()