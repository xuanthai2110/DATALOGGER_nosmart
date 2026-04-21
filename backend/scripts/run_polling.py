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
from backend.services.modbus_server_service import ModbusServerService
from backend.workers.evn_worker import EVNWorker
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
        
        # 4. EVN Layer (Sử dụng cấu hình từ DB hoặc settings mặc định)
        evn_settings = {
            "enabled": meta_db.get_setting("evn_enabled", str(settings.EVN_ENABLED)).lower() == "true",
            "host": meta_db.get_setting("evn_modbus_host", settings.EVN_MODBUS_HOST),
            "port": int(meta_db.get_setting("evn_modbus_port", settings.EVN_MODBUS_PORT))
        }

        modbus_server = None
        evn_worker = None
        if evn_settings["enabled"]:
            modbus_server = ModbusServerService()
            evn_worker = EVNWorker(
                modbus_server=modbus_server,
                cache_db=cache_db,
                realtime_db=realtime_db,
                metadata_db=meta_db,
                control_service=control_svc,
                project_svc=project_svc
            )
        
        schedule_worker = ScheduleWorker(schedule_svc, control_svc, modbus_server=modbus_server, interval=1.0)
        
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

        # Start EVN
        if evn_settings["enabled"]:
            logger.info(f"EVN Integration enabled. Starting Modbus Server at {evn_settings['host']}:{evn_settings['port']}...")
            # Lấy list slave_id từ projects
            evn_map = meta_db.get_evn_project_map()
            slave_ids = list(evn_map.keys())
            
            allowed_ips_str = meta_db.get_setting("evn_allowed_ips", settings.EVN_ALLOWED_IPS)
            allowed_ips_list = [ip.strip() for ip in allowed_ips_str.split(",") if ip.strip()]
            
            modbus_server.start(evn_settings['host'], evn_settings['port'], slave_ids, allowed_ips=allowed_ips_list)
            evn_worker.start()
        
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
