import time
import logging
import config
from database.sqlite_manager import MetadataDB, RealtimeDB, CacheDB
from services.polling_service import PollingService
from services.uploader_service import UploaderService
from services.project_service import ProjectService
from services.telemetry_service import TelemetryService
from logger_config import get_logger

logger = get_logger()

def main():
    metadata_db = MetadataDB(config.METADATA_DB)
    realtime_db = RealtimeDB(config.REALTIME_DB)
    cache_db = CacheDB(config.CACHE_DB)
    
    project_service = ProjectService(metadata_db, realtime_db)
    telemetry_service = TelemetryService(project_service, realtime_db)
    
    uploader = UploaderService(realtime_db)
    poller = PollingService(metadata_db, cache_db)

    logger.info("Starting datalogger service with Telemetry support...")
    
    try:
        # PollingService.run_forever handles the loop, night mode, and 10s interval
        poller.run_forever()
    except KeyboardInterrupt:
        logger.info("Datalogger stopped by user.")
    except Exception as e:
        logger.error(f"Critical error: {e}")

if __name__ == "__main__":
    main()