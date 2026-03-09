"""
scripts/setup_project.py
------------------------
Script để khởi tạo project và inverter:
1. Quét inverter local (Slave 1-30).
2. Lưu thông tin project & inverter vào local DB.
3. Đồng bộ dữ liệu lên server (Check local -> POST/PATCH).

Cách dùng:
    .\venv\Scripts\python.exe scripts/setup_project.py
"""

import sys
import logging
from pathlib import Path

# Thêm thư mục gốc vào sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database.sqlite_manager import MetadataDB
from services.auth_service import AuthService
from services.setup_service import SetupService
from schemas.project import ProjectCreate
from drivers.huawei_sun2000110KTL import HuaweiSUN2000
from communication.modbus_tcp import ModbusTCP

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # 1. Khởi tạo DB & Services
    db_path = str(ROOT / "metadata.db")
    meta_db = MetadataDB(db_path)
    auth_svc = AuthService()
    setup_svc = SetupService(auth_svc, meta_db)
    
    print("\n=== [STEP 1] INFO PROJECT SETUP ===")
    project_existing = setup_svc.get_local_project()
    
    if not project_existing:
        print("Project chưa được thiết lập local. Đang khởi tạo thông tin mặc định...")
        # (Trong thực tế nên nhập từ CLI hoặc Config)
        new_project = ProjectCreate(
            name="Datalogger ABC",
            location="Ho Chi Minh City",
            lat=10.762622,
            lon=106.660172,
            capacity_kwp=110.0,
            ac_capacity_kw=100.0,
            inverter_count=0, # Sẽ cập nhật sau khi quét
            elec_meter_no="METER-123",
            elec_price_per_kwh=2000.0
        )
        project_id = meta_db.post_project(new_project)
        print(f"✅ Đã lưu project local (ID: {project_id})")
    else:
        project_id = project_existing.id
        print(f"ℹ️ Đã có project local: {project_existing.name} (ID: {project_id})")

    print("\n=== [STEP 2] INVERTER SCANNING ===")
    HOST = "192.168.1.8" # IP Inverter/Gateway
    transport = ModbusTCP(host=HOST, port=502)
    
    if transport.connect():
        print(f"Kết nối Modbus thành công tới {HOST}. Đang quét Slave 1-30...")
        found_ids = setup_svc.scan_inverters(transport, project_id, HuaweiSUN2000)
        transport.close()
        
        # Cập nhật số lượng inverter vào Project
        meta_db.patch_project(project_id, type('UP', (), {'inverter_count': len(found_ids)})())
        print(f"✅ Quét xong. Tìm thấy {len(found_ids)} inverters.")
    else:
        print("❌ Không thể kết nối Modbus. Bỏ qua bước quét inverter.")

    print("\n=== [STEP 3] SERVER SYNCHRONIZATION ===")
    print("Đang đồng bộ Project lên server...")
    server_project_id = setup_svc.sync_project_to_server(project_id)
    if server_project_id:
        print(f"✅ Đồng bộ Project thành công (Server ID: {server_project_id}).")
        
        print("Đang đồng bộ danh sách Inverters lên server...")
        setup_svc.sync_inverters_to_server(project_id)
        print("✅ Đồng bộ Inverters hoàn tất.")
    else:
        print("❌ Đồng bộ Project thất bại. Có lẽ server chưa sẵn sàng hoặc lỗi token.")

    print("\n=== SETUP HOÀN TẤT ===")

if __name__ == "__main__":
    main()
