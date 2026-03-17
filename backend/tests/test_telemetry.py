import os
import sys
import json
import logging
import time
from datetime import datetime, timezone

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database.sqlite_manager import MetadataDB, RealtimeDB, CacheDB
from services.project_service import ProjectService
from services.telemetry_service import TelemetryService
from services.fault_state_service import FaultStateService
from services.polling_service import PollingService
from services.buffer_service import BufferService
import config

# Configure logging to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TestTelemetry")

def run_test():
    logger.info("Starting One-Shot Telemetry Test...")
    
    try:
        # 1. Initialize DBs with paths from config
        metadata_db = MetadataDB(config.METADATA_DB)
        realtime_db = RealtimeDB(config.REALTIME_DB)
        cache_db = CacheDB(config.CACHE_DB)
        buffer_service = BufferService(realtime_db)
        
        # 2. Initialize Services
        project_service = ProjectService(metadata_db, realtime_db)
        telemetry_service = TelemetryService(project_service, buffer_service)
        fault_service = FaultStateService()
        
        # Chúng ta không truyền uploader để đảm bảo không gửi lên server
        service = PollingService(
            metadata_db, 
            realtime_db, 
            uploader=None, 
            telemetry_service=telemetry_service, 
            cache_db=cache_db,
            fault_service=fault_service
        )
        
        # 3. Get projects
        projects = metadata_db.get_all_projects()
        if not projects:
            logger.error("No projects found in database!")
            return

        all_telemetry = []

        for project in projects:
            logger.info(f"Processing Project: {project.name} (ID: {project.id})")
            
            # Đọc dữ liệu từ Inverters (Step 1-2: Poll & Enrichment & Tracking)
            # service.poll_all_inverters(project.id)
            
            # Lưu snapshot 5p vào RealtimeDB (để telemetry lấy ra)
            service.save_to_database(project.id)
            
            # Build Telemetry Payload (Step 4)
            # Thay vì gọi build_and_buffer, ta gọi _build_payload để lấy trực tiếp dữ liệu
            snapshot = project_service.get_project_snapshot(project.id)
            if snapshot:
                payload = telemetry_service._build_payload(project.id, snapshot)
                
                # Làm sạch payload (loại bỏ extra fields như Uploader làm)
                clean_payload = payload.copy()
                clean_payload.pop("id", None)
                clean_payload.pop("project_id", None)
                clean_payload.pop("server_id", None)
                clean_payload.pop("timestamp", None)
                
                all_telemetry.append({
                    "project_name": project.name,
                    "local_id": project.id,
                    "server_id": project.server_id,
                    "payload": clean_payload
                })
            else:
                logger.warning(f"No snapshot data for project {project.id}")

        # 4. Save to data.json
        output_file = "data.json"
        if all_telemetry:
            # Chỉ lấy payload của project đầu tiên để khớp mẫu data.txt (không có [])
            final_data = all_telemetry[0]["payload"]
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(final_data, f, indent=4, ensure_ascii=False)
            logger.info(f"Success! Telemetry data saved to {os.path.abspath(output_file)}")
        else:
            logger.error("No telemetry data to save.")
            
        print("\n" + "="*50)
        print(f"DONE: Please check {output_file}")
        print("="*50 + "\n")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)

if __name__ == "__main__":
    run_test()
