"""
scripts/sync_to_server.py
-------------------------
Script để đồng bộ dữ liệu local lên server:
1. Đọc thông tin project và inverter đã có trong DB local.
2. Gửi yêu cầu đăng ký Project lên Server (nếu chưa có hoặc đang chờ duyệt).
3. Gửi danh sách Inverters lên Server để được phê duyệt.
4. KHÔNG thực hiện quét (detect) lại thiết bị qua Modbus.

Cách dùng:
    python scripts/sync_to_server.py
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
from backend.core import config

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # 1. Khởi tạo DB & Services
    meta_db = MetadataDB(config.METADATA_DB)
    auth_svc = AuthService()
    setup_svc = SetupService(auth_svc, meta_db)
    
    print("\n=== [STEP 1] CHECKING LOCAL DATA ===")
    project_existing = setup_svc.get_local_project()
    
    if not project_existing:
        print("❌ Lỗi: Không tìm thấy Project trong DB local. Vui lòng chạy setup_project_local.py trước.")
        return

    project_id = project_existing.id
    print(f"ℹ️ Đang xử lý project: {project_existing.name} (ID Local: {project_id})")

    # Kiểm tra danh sách inverter local
    inverters = meta_db.get_inverters_by_project(project_id)
    if not inverters:
        print("⚠️ Cảnh báo: Chưa có inverters nào được lưu local. Sẽ chỉ đồng bộ Project.")
    else:
        print(f"ℹ️ Tìm thấy {len(inverters)} inverters trong DB local.")

    print("\n=== [STEP 2] SERVER SYNCHRONIZATION ===")
    
    # Đồng bộ Project
    print("Đang đồng bộ Project lên server...")
    server_project_id = setup_svc.sync_project_to_server(project_id)
    
    if server_project_id:
        print(f"✅ Dự án đã được DUYỆT trên Server (Server ID: {server_project_id}).")
    else:
        # Kiểm tra trạng thái sync sau khi gọi sync_project_to_server
        fresh_project = meta_db.get_project(project_id)
        status = getattr(fresh_project, 'sync_status', 'pending')
        req_id = getattr(fresh_project, 'server_request_id', None)
        
        if status == 'approved':
            print(f"✅ Dự án đã được xác nhận tồn tại trên Server.")
        elif req_id:
            print(f"🕒 Project Request đã được gửi (ID: {req_id}). Đang chờ Admin phê duyệt.")
        else:
            print("❌ Gửi yêu cầu đồng bộ Project thất bại. Vui lòng kiểm tra config API hoặc kết nối mạng.")
            return

    # Đồng bộ Inverters
    if inverters:
        print("\nĐang gửi/kiểm tra danh sách Inverters lên server...")
        setup_svc.sync_inverters_to_server(project_id)
        
        # Thống kê trạng thái sau khi đồng bộ
        fresh_inverters = meta_db.get_inverters_by_project(project_id)
        approved_count = sum(1 for inv in fresh_inverters if getattr(inv, 'sync_status', '') == 'approved')
        pending_count = sum(1 for inv in fresh_inverters if getattr(inv, 'sync_status', '') == 'pending')
        
        print(f"📊 Thống kê Inverters:")
        print(f"   - Đã duyệt: {approved_count}")
        print(f"   - Đang chờ duyệt: {pending_count}")

    print("\n=== ĐỒNG BỘ HOÀN TẤT ===")
    print("Mẹo: Nếu Project/Inverter đang ở trạng thái 'pending', hãy báo Admin duyệt trên CMS.")

if __name__ == "__main__":
    main()
