"""
scripts/setup_project.py
-------------------------
Script TOÀN DIỆN để khởi tạo hệ thống Datalogger:
1. GIAI ĐOẠN 1 (Local):
   - Đọc config và tạo Project trong database local.
   - Quét (Scan) Inverter qua Modbus TCP và lưu local.
   - Cập nhật số lượng inverter thực tế.
2. GIAI ĐOẠN 2 (Server Sync):
   - Đăng nhập (Auth) vào Server.
   - Gửi yêu cầu đăng ký Project (Project Request) lên Server.
   - Gửi danh sách Inverters (Inverter Request) liên kết với Project lên Server.

Cách dùng:
    python scripts/setup_project.py
"""

import sys
import logging
from pathlib import Path

# Thêm thư mục gốc vào sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.db_manager import MetadataDB
from backend.services.auth_service import AuthService
from backend.services.setup_service import SetupService
from backend.models.project import ProjectCreate, ProjectUpdate
from backend.drivers.huawei_sun2000110KTL import HuaweiSUN2000
from backend.communication.modbus_tcp import ModbusTCP
from backend.core import config

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # 1. Khởi tạo DB & Services
    meta_db = MetadataDB(config.METADATA_DB)
    auth_svc = AuthService()
    setup_svc = SetupService(auth_svc, meta_db)
    
    print("\n" + "="*50)
    print("      SOLAR DATALOGGER - COMPREHENSIVE SETUP")
    print("="*50)

    # --- GIAI ĐOẠN 1: LOCAL SETUP ---
    # Mục tiêu: Đảm bảo Project và Inverters được lưu trữ đúng cấu trúc trong database của Datalogger.
    print("\n>>> [PHASE 1] LOCAL INITIALIZATION")
    project_existing = setup_svc.get_local_project()
    
    if not project_existing:
        print(f"ℹ️ Khởi tạo dự án mới: {config.PROJECT_INFO.get('name', 'Datalogger Project')}")
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
        print(f"✅ Đã lưu Project local (ID: {project_id})")
    else:
        project_id = project_existing.id
        print(f"ℹ️ Đã có Project local: {project_existing.name} (ID: {project_id})")

    # Quét Inverter qua Modbus TCP và lưu vào local DB
    print("\n>>> [PHASE 1.5] INVERTER SCANNING")
    HOST = config.MODBUS_TCP_HOST
    PORT = config.MODBUS_TCP_PORT
    transport = ModbusTCP(host=HOST, port=PORT, timeout=2.0)
    
    found_ids = []
    if transport.connect():
        print(f"🔗 Kết nối tới Inverter tại {HOST}:{PORT}...")
        found_ids = setup_svc.scan_inverters(transport, project_id, HuaweiSUN2000)
        transport.close()
        
        # Cập nhật lại số lượng inverter thực tế
        update_data = ProjectUpdate(id=project_id, inverter_count=len(found_ids))
        meta_db.patch_project(project_id, update_data)
        print(f"✅ Đã quét và lưu {len(found_ids)} inverters.")
    else:
        print(f"❌ Không thể kết nối tới {HOST}:{PORT}. Bỏ qua bước quét inverter.")

    # --- GIAI ĐOẠN 2: SERVER SYNC ---
    # Mục tiêu: Đưa các thông tin local lên Cloud Server để quản lý tập trung và nhận phê duyệt.
    print("\n>>> [PHASE 2] SERVER SYNCHRONIZATION")
    
    # 2.1 Đồng bộ Project (Tạo yêu cầu đăng ký dự án trên Server)
    print("Đang gửi yêu cầu đồng bộ Project lên server...")
    server_project_id = setup_svc.sync_project_to_server(project_id)
    
    if server_project_id:
        print(f"✅ Dự án đã được DUYỆT trên Server (Server ID: {server_project_id}).")
    else:
        fresh_project = meta_db.get_project(project_id)
        if getattr(fresh_project, 'server_request_id', None):
            print(f"🕒 Project Request đã được gửi (ID: {fresh_project.server_request_id}). Đang chờ Admin phê duyệt.")
        else:
            print("⚠️ Cảnh báo: Gửi Project Request thất bại. Vui lòng kiểm tra kết nối mạng/API.")

    # 2.2 Đồng bộ Inverters (Gửi danh sách thiết bị linked với project lên Server)
    inverters = meta_db.get_inverters_by_project(project_id)
    if inverters:
        print("\nĐang gửi danh sách Inverters lên server...")
        setup_svc.sync_inverters_to_server(project_id)
        
        fresh_inverters = meta_db.get_inverters_by_project(project_id)
        approved_count = sum(1 for inv in fresh_inverters if getattr(inv, 'sync_status', '') == 'approved')
        pending_count = sum(1 for inv in fresh_inverters if getattr(inv, 'sync_status', '') == 'pending')
        
        print(f"📊 Thống kê Inverters trên Server:")
        print(f"   - Tổng số local: {len(inverters)}")
        print(f"   - Đã duyệt:      {approved_count}")
        print(f"   - Chờ duyệt:     {pending_count}")
    else:
        print("ℹ️ Không có inverter nào để đồng bộ.")

    print("\n" + "="*50)
    print("        QUY TRÌNH SETUP HOÀN TẤT")
    print("="*50)
    print("Sử dụng CMS để phê duyệt các yêu cầu đang chờ (pending).")

if __name__ == "__main__":
    main()
