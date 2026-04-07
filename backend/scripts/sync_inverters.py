"""
scripts/sync_inverters.py
-------------------------
Script chuyên biệt để đồng bộ danh sách Inverters từ local lên server:
1. Đọc thông tin project local.
2. Kiểm tra xem project đã có server_id (đã duyệt) hay server_request_id (đang chờ duyệt).
3. Gửi danh sách Inverters lên Server.
4. Tự động liên kết với Project tương ứng trên server.

Cách dùng:
    python scripts/sync_inverters.py
"""

import sys
import logging
from pathlib import Path

# Thêm thư mục gốc vào sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.db_manager import MetadataDB, RealtimeDB
from backend.services.auth_service import AuthService
from backend.services.setup_service import SetupService
from backend.services.project_service import ProjectService
from backend.core import settings

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # 1. Khởi tạo DB & Services
    meta_db = MetadataDB(settings.METADATA_DB)
    realtime_db = RealtimeDB(settings.REALTIME_DB)
    project_svc = ProjectService(metadata_db=meta_db, realtime_db=realtime_db)
    
    auth_svc = AuthService()
    setup_svc = SetupService(auth_svc, project_service=project_svc)
    
    print("\n=== [STEP 1] CHECKING LOCAL DATA ===")
    project_existing = setup_svc.get_local_project()
    
    if not project_existing:
        print("❌ Lỗi: Không tìm thấy Project trong DB local. Vui lòng chạy setup_project_local.py trước.")
        return

    project_id = project_existing.id
    print(f"ℹ️ Đang xử lý inverters cho project: {project_existing.name} (ID Local: {project_id})")

    # Kiểm tra danh sách inverter local
    inverters = project_svc.get_inverters_by_project(project_id)
    if not inverters:
        print("⚠️ Cảnh báo: Chưa có inverters nào được lưu local. Vui lòng chạy setup_project_local.py để quét thiết bị.")
        return
    
    print(f"ℹ️ Tìm thấy {len(inverters)} inverters trong DB local.")

    # Kiểm tra liên kết server
    if not getattr(project_existing, 'server_id', None) and not getattr(project_existing, 'server_request_id', None):
        print("⚠️ Cảnh báo: Project chưa được đồng bộ lên server. Đang thử đồng bộ Project trước...")
        setup_svc.sync_project_to_server(project_id)
        # Cập nhật lại thông tin project sau khi sync
        project_existing = project_svc.get_project(project_id)

    print("\n=== [STEP 2] INVERTER SYNCHRONIZATION ===")
    
    print("Đang gửi danh sách Inverters lên server...")
    setup_svc.sync_inverters_to_server(project_id)
    
    # 3. Thống kê trạng thái sau khi đồng bộ
    fresh_inverters = project_svc.get_inverters_by_project(project_id)
    total = len(fresh_inverters)
    approved_count = sum(1 for inv in fresh_inverters if getattr(inv, 'sync_status', '') == 'approved')
    pending_count = sum(1 for inv in fresh_inverters if getattr(inv, 'sync_status', '') == 'pending')
    
    print(f"\n📊 Kết quả đồng bộ:")
    print(f"   - Tổng số inverter local: {total}")
    print(f"   - Đã duyệt (Approved): {approved_count}")
    print(f"   - Đang chờ duyệt (Pending): {pending_count}")
    print(f"   - Thất bại/Chưa gửi: {total - approved_count - pending_count}")

    print("\n=== HOÀN TẤT ===")
    if pending_count > 0:
        print("Mẹo: Hãy báo Admin duyệt các Inverter Request trên CMS.")

if __name__ == "__main__":
    main()
