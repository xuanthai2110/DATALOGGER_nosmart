import sys
import os
import logging
import time
from pathlib import Path

# Add project root correctly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.db_manager import MetadataDB, CacheDB, RealtimeDB
from backend.services.modbus_server_service import ModbusServerService
from backend.services.project_service import ProjectService
from backend.workers.evn_worker import EVNWorker
from backend.core import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("EVNLauncher")

def main():
    try:
        logger.info("Starting Dedicated EVN Service...")
        
        # 1. DB Layer
        meta_db = MetadataDB(settings.METADATA_DB)
        cache_db = CacheDB(settings.CACHE_DB)
        realtime_db = RealtimeDB(settings.REALTIME_DB)
        
        # 2. Service Layer
        project_svc = ProjectService(metadata_db=meta_db, realtime_db=realtime_db)
        
        # 3. EVN Layer
        evn_enabled = meta_db.get_setting("evn_enabled", str(settings.EVN_ENABLED)).lower() == "true"
        if not evn_enabled:
            logger.info("EVN Integration is disabled in settings. Exiting.")
            return

        host = meta_db.get_setting("evn_modbus_host", settings.EVN_MODBUS_HOST)
        port = int(meta_db.get_setting("evn_modbus_port", settings.EVN_MODBUS_PORT))
        
        modbus_server = ModbusServerService()
        
        # Lưu ý: Khi tách riêng, EVNWorker sẽ không có direct ControlService (trực tiếp điều khiển polling)
        # mà sẽ thông qua MQTT hoặc DB để ra lệnh. 
        # Hiện tại EVNWorker trong code của chúng ta nhận control_service làm tham số.
        # Chúng ta sẽ khởi tạo một ControlService "rỗng" hoặc sửa EVNWorker để gửi lệnh qua MQTT.
        
        evn_worker = EVNWorker(
            modbus_server=modbus_server,
            cache_db=cache_db,
            realtime_db=realtime_db,
            metadata_db=meta_db,
            control_service=None, # Sẽ được xử lý qua MQTT/DB sau
            project_svc=project_svc
        )

        # 4. Khởi chạy Modbus Server
        evn_map = meta_db.get_evn_project_map()
        slave_ids = list(evn_map.keys())
        
        allowed_ips_str = meta_db.get_setting("evn_allowed_ips", settings.EVN_ALLOWED_IPS)
        allowed_ips_list = [ip.strip() for ip in allowed_ips_str.split(",") if ip.strip()]

        logger.info(f"Starting Modbus Server at {host}:{port} with allowed IPs: {allowed_ips_list}")
        modbus_server.start(host, port, slave_ids, allowed_ips=allowed_ips_list)
        
        # 5. Khởi chạy EVN Worker (Gửi telemetry)
        evn_worker.start()
        
        logger.info("EVN Service operational. Press Ctrl+C to exit.")
        while True:
            time.sleep(10)

    except KeyboardInterrupt:
        logger.info("Shutdown requested.")
    except Exception as e:
        logger.error(f"EVN Service error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
