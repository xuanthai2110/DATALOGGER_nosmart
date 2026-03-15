import time
from services.polling_service import PollingService
from services.uploader_service import UploaderService
from services.buffer_service import BufferService
from core.logger import get_logger

logger = get_logger()

def main():
    metadata_db = MetadataDB(app_config.METADATA_DB)
    realtime_db = RealtimeDB(app_config.REALTIME_DB)
    
    buffer_service = BufferService()
    uploader = UploaderService(buffer_service)
    poller = PollingService(metadata_db, realtime_db)

    logger.info("Starting datalogger...")

    while True:
        try:
            poller.poll()
            uploader.upload()
            time.sleep(5)
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()