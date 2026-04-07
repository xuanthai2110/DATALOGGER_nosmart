"""
scripts/setup_project_local.py
------------------------------
Script để khởi tạo project và quét inverter LOCAL ONLY:
1. Tạo project trong database local từ config.py.
2. Quét inverter Huawei qua Modbus TCP (Slave 1-30).
3. Lưu danh sách inverter tìm thấy vào database local.
4. KHÔNG đồng bộ lên server.

Cách dùng:
    python scripts/setup_project_local.py
"""

import sys
import logging
from pathlib import Path

# Thêm thư mục gốc vào sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.db_manager import MetadataDB, RealtimeDB
from backend.services.setup_service import SetupService
from backend.services.project_service import ProjectService
from backend.models.project import ProjectCreate, ProjectUpdate
from backend.drivers.huawei_sun2000110KTL import HuaweiSUN2000
from backend.communication.modbus_tcp import ModbusTCP
from backend.core import settings

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # 1. Khởi tạo DB & Services
    # Sử dụng database path từ config (thường là database/metadata.db hoặc datalogger.db)
    meta_db = MetadataDB(settings.METADATA_DB)
    realtime_db = RealtimeDB(settings.REALTIME_DB)
    project_svc = ProjectService(metadata_db=meta_db, realtime_db=realtime_db)

    # Chúng ta không cần AuthService vì không đồng bộ server
    setup_svc = SetupService(auth_service=None, project_service=project_svc)
    
    print("\n=== [STEP 1] LOCAL PROJECT SETUP ===")
    project_existing = setup_svc.get_local_project()
    
    if not project_existing:
        print(f"Project chưa có trong DB local. Đang khởi tạo: {settings.PROJECT_INFO.get('name', 'Unknown')}...")
        
        # Tạo dữ liệu project, ưu tiên giá trị mặc định nếu config thiếu
        project_data = {
            "elec_meter_no": "N/A",
            "elec_price_per_kwh": 0.0,
            "name": "Datalogger Project",
            "location": "Unknown",
            "lat": 0.0,
            "lon": 0.0,
            "capacity_kwp": 0.0,
            "ac_capacity_kw": 0.0,
            "inverter_count": 0
        }
        project_data.update(settings.PROJECT_INFO)
        
        new_project = ProjectCreate(**project_data)
        project_id = project_svc.upsert_project(new_project)
        print(f"✅ Đã lưu project local (ID: {project_id})")
    else:
        project_id = project_existing.id
        print(f"ℹ️ Đã có project local: {project_existing.name} (ID: {project_id})")

    print("\n=== [STEP 2] LOCAL INVERTER SCANNING ===")
    HOST = settings.MODBUS_TCP_HOST
    PORT = settings.MODBUS_TCP_PORT
    transport = ModbusTCP(host=HOST, port=PORT, timeout=2.0)
    
    if transport.connect():
        print(f"Kết nối Modbus thành công tới {HOST}:{PORT}. Đang quét Slave ID 1-30...")
        # Hàm scan_inverters sẽ tự động lưu vào DB local thông qua setup_svc
        found_ids = setup_svc.scan_inverters(transport, project_id, HuaweiSUN2000)
        transport.close()
        
        # Cập nhật lại số lượng inverter thực tế tìm thấy (ProjectUpdate không có trường id)
        update_data = ProjectUpdate(inverter_count=len(found_ids))
        project_svc.update_project(project_id, update_data)
        
        print(f"✅ Quét xong. Tìm thấy và lưu {len(found_ids)} inverters vào DB local.")
        if found_ids:
            print(f"Danh sách Slave IDs tìm thấy: {found_ids}")
    else:
        print(f"❌ Không thể kết nối tới {HOST}:{PORT}. Vui lòng kiểm tra dây mạng hoặc IP Inverter.")

    print("\n=== SETUP LOCAL HOÀN TẤT (BỎ QUA SERVER SYNC) ===")
    print(f"Database đã được cập nhật tại: {settings.METADATA_DB}")

if __name__ == "__main__":
    main()
