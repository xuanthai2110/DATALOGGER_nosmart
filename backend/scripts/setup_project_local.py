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

from database.sqlite_manager import MetadataDB
from services.setup_service import SetupService
from schemas.project import ProjectCreate, ProjectUpdate
from drivers.huawei_sun2000110KTL import HuaweiSUN2000
from communication.modbus_tcp import ModbusTCP
import config

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # 1. Khởi tạo DB & Services
    # Sử dụng database path từ config (thường là database/metadata.db hoặc datalogger.db)
    meta_db = MetadataDB(config.METADATA_DB)
    # Chúng ta không cần AuthService vì không đồng bộ server
    setup_svc = SetupService(auth_service=None, metadata_db=meta_db)
    
    print("\n=== [STEP 1] LOCAL PROJECT SETUP ===")
    project_existing = setup_svc.get_local_project()
    
    if not project_existing:
        print(f"Project chưa có trong DB local. Đang khởi tạo: {config.PROJECT_INFO.get('name', 'Unknown')}...")
        
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
        project_data.update(config.PROJECT_INFO)
        
        new_project = ProjectCreate(**project_data)
        project_id = meta_db.post_project(new_project)
        print(f"✅ Đã lưu project local (ID: {project_id})")
    else:
        project_id = project_existing.id
        print(f"ℹ️ Đã có project local: {project_existing.name} (ID: {project_id})")

    print("\n=== [STEP 2] LOCAL INVERTER SCANNING ===")
    HOST = config.MODBUS_TCP_HOST
    PORT = config.MODBUS_TCP_PORT
    transport = ModbusTCP(host=HOST, port=PORT, timeout=2.0)
    
    if transport.connect():
        print(f"Kết nối Modbus thành công tới {HOST}:{PORT}. Đang quét Slave ID 1-30...")
        # Hàm scan_inverters sẽ tự động lưu vào DB local thông qua setup_svc
        found_ids = setup_svc.scan_inverters(transport, project_id, HuaweiSUN2000)
        transport.close()
        
        # Cập nhật lại số lượng inverter thực tế tìm thấy
        update_data = ProjectUpdate(id=project_id, inverter_count=len(found_ids))
        meta_db.patch_project(project_id, update_data)
        
        print(f"✅ Quét xong. Tìm thấy và lưu {len(found_ids)} inverters vào DB local.")
        if found_ids:
            print(f"Danh sách Slave IDs tìm thấy: {found_ids}")
    else:
        print(f"❌ Không thể kết nối tới {HOST}:{PORT}. Vui lòng kiểm tra dây mạng hoặc IP Inverter.")

    print("\n=== SETUP LOCAL HOÀN TẤT (BỎ QUA SERVER SYNC) ===")
    print(f"Database đã được cập nhật tại: {config.METADATA_DB}")

if __name__ == "__main__":
    main()
