# scripts/run_polling.py

import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.sqlite_manager import MetadataDB, RealtimeDB
from services.polling_service import PollingService
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
        logger.info("Initializing Polling Service...")
        metadata_db = MetadataDB(config.METADATA_DB)
        realtime_db = RealtimeDB(config.REALTIME_DB)
        
        service = PollingService(metadata_db, realtime_db)
        service.run_forever()
    except KeyboardInterrupt:
        logger.info("Polling Service stopped by user.")
    except Exception as e:
        logger.error(f"Critical error in Polling Service: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
