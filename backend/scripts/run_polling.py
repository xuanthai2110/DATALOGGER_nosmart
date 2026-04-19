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
    
    # sys.path is already updated
    pass

# 2. Imports using absolute package names
from backend.db_manager import MetadataDB, CacheDB, RealtimeDB
from backend.workers.polling_worker import PollingWorker
from backend.workers.logic_worker import LogicWorker
from backend.workers.persistence_worker import PersistenceWorker
from backend.workers.build_tele_worker import BuildTeleWorker
from backend.workers.schedule_worker import ScheduleWorker
from backend.services.fault_service import FaultService
from backend.services.project_service import ProjectService
from backend.services.schedule_service import ScheduleService
from backend.services.control_service import ControlService
from backend.communication.mqtt_subscriber import MqttSubscriber
from backend.core import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Launcher")

def main():
    try:
        logger.info(f"System Path prioritized: {sys.path[0]}")
        logger.info("Starting Modular Telemetry Datalogger...")
        
        # 1. DB Layer
        meta_db = MetadataDB(settings.METADATA_DB)
        cache_db = CacheDB(settings.CACHE_DB)
        realtime_db = RealtimeDB(settings.REALTIME_DB)
        
        # 2. Service Layer
        project_svc = ProjectService(metadata_db=meta_db, realtime_db=realtime_db)
        fault_service = FaultService(realtime_db, meta_db)
        schedule_svc = ScheduleService(realtime_db, meta_db)
        
        # 3. Worker Layer
        # Chú ý: Cần BuildTeleWorker trước để truyền vào LogicWorker
        build_tele_worker = BuildTeleWorker(cache_db, project_svc, realtime_db, settings.SNAPSHOT_INTERVAL)
        poll_worker = PollingWorker(project_svc, cache_db, settings.POLL_INTERVAL)
        logic_worker = LogicWorker(cache_db, project_svc, realtime_db, fault_service, build_tele_worker)
        persist_worker = PersistenceWorker(cache_db, realtime_db, logic_worker.energy_service, settings.SNAPSHOT_INTERVAL, string_monitor=poll_worker.service.string_monitor)
        
        # Khởi tạo Control Service dựa vào polling service nội bộ của poll_worker
        control_svc = ControlService(polling_service=poll_worker.service)
        schedule_worker = ScheduleWorker(schedule_svc, control_svc, interval=1.0)
        
        mqtt_sub = MqttSubscriber(
            broker=settings.MQTT_BROKER, 
            port=settings.MQTT_PORT,
            schedule_service=schedule_svc,
            control_service=control_svc, # Thêm control_service
            username=settings.MQTT_USERNAME,
            password=settings.MQTT_PASSWORD,
            project_server_ids_provider=lambda: [
                project.server_id for project in project_svc.get_projects() if getattr(project, "server_id", None) is not None
            ],
        )
        
        # Start Threads
        poll_worker.start()
        logic_worker.start()
        persist_worker.start()
        build_tele_worker.start()
        schedule_worker.start()
        mqtt_sub.connect()
        
        logger.info("System operational (Polling/Logic/BuildTele). Press Ctrl+C to exit.")
        while True:
            time.sleep(10)

    except KeyboardInterrupt:
        logger.info("Shutdown requested.")
    except Exception as e:
        logger.error(f"Polling error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
