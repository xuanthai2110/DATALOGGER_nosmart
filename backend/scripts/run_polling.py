# scripts/run_polling.py

import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.sqlite_manager import MetadataDB, RealtimeDB, CacheDB
from services.polling_service import PollingService
from services.uploader_service import UploaderService
from services.buffer_service import BufferService
from services.project_service import ProjectService
from services.telemetry_service import TelemetryService
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("polling.log")
    ]
)

logger = logging.getLogger("RunPolling")

def main():
    try:
        logger.info("Initializing Polling System with RAM Cache & Telemetry...")
        
        metadata_db = MetadataDB(config.METADATA_DB)
        realtime_db = RealtimeDB(config.REALTIME_DB)
        cache_db = CacheDB(config.CACHE_DB)
        
        project_service = ProjectService(metadata_db, realtime_db)
        buffer_service = BufferService(realtime_db)
        telemetry_service = TelemetryService(project_service, buffer_service)
        
        uploader = UploaderService(buffer_service)
        
        service = PollingService(metadata_db, realtime_db, uploader, telemetry_service, cache_db)
        service.run_forever()
    except KeyboardInterrupt:
        logger.info("Polling Service stopped by user.")
    except Exception as e:
        logger.error(f"Critical error in Polling Service: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
