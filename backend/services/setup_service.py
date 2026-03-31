import requests
import logging
import time
from typing import Optional
from dataclasses import asdict
from backend.core.config import API_BASE_URL
from backend.models.project import ProjectCreate, ProjectUpdate
from backend.models.inverter import InverterCreate, InverterUpdate

logger = logging.getLogger(__name__)

class SetupService:
    def __init__(self, auth_service, project_service):
        self.auth = auth_service
        self.project_svc = project_service

    def scan_inverters(self, transport, project_id: int, driver_class) -> list[int]:
        """
        QUY TRÌNH QUÉT INVERTER:
        1. Lặp qua dải Slave ID (mặc định 1-30).
        2. Với mỗi ID, khởi tạo driver và thử đọc thông tin (read_info).
        3. Nếu inverter phản hồi (is_active), gán project_id và số thứ tự (inverter_index).
        4. Lưu thông tin vào Database local (upsert_inverter).
        """
        found_ids = []
        logger.info(f"[Setup] Starting scan for inverters (Slave 1-30) using {driver_class.__name__}")
        
        for slave_id in range(1, 31):
            success = False
            for attempt in range(2):
                try:
                    driver = driver_class(transport, slave_id=slave_id)
                    info = driver.read_info()
                    
                    if info and info.get("is_active"):
                        logger.info(f"[Setup] Found active inverter at Slave ID {slave_id}: {info['serial_number']}")
                        inv_data = InverterCreate(**info)
                        local_id = self.project_svc.upsert_inverter(inv_data)
                        found_ids.append(local_id)
                        success = True
                        break
                    else:
                        logger.debug(f"[Setup] No active inverter at Slave ID {slave_id} (Attempt {attempt+1})")
                except Exception as e:
                    logger.debug(f"[Setup] Error scanning Slave ID {slave_id} (Attempt {attempt+1}): {e}")
                
                if not success and attempt == 0:
                    time.sleep(1) # Delay 1s before retry
                    
        logger.info(f"[Setup] Scan complete. Found {len(found_ids)} inverters.")
        return found_ids

    def pre_sync_check(self, project_id: int) -> bool:
        """Kiểm tra dự án trên server bằng elec_meter_no (format mới)."""
        local_project = self.project_svc.get_project(project_id)
        if not local_project or not local_project.elec_meter_no:
            return False

        token = self.auth.get_access_token()
        if not token: return False

        try:
            # Server trả về dạng {"data": [{"project": {...}, "telemetry": ...}]}
            url = f"{API_BASE_URL}/api/projects/?telemetry=false"
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200: return False

            data_items = resp.json().get("data", [])
            matched_proj_data = None
            for item in data_items:
                proj_data = item.get("project", {})
                if proj_data.get("elec_meter_no") == local_project.elec_meter_no:
                    matched_proj_data = proj_data
                    break
            
            if matched_proj_data:
                server_id = matched_proj_data.get("id")
                self.project_svc.update_project_sync(project_id, server_id=server_id, status='approved')
                logger.info(f"[Sync] Auto-matched project {project_id} -> Server ID {server_id}")
                
                # Bonus: Nếu server trả về inverters trong project (tùy API thiết kế)
                # Ở đây chúng ta tạm thời chỉ khớp Project. Inverter sẽ khớp riêng hoặc Request sau.
                return True
        except Exception as e:
            logger.error(f"[Sync] Pre-sync error: {e}")
        
        return False

    def initiate_sync_request(self, project_id: int) -> Optional[int]:
        """Gửi yêu cầu đồng bộ (POST /api/project/requests/)"""
        project = self.project_svc.get_project(project_id)
        inverters = self.project_svc.get_inverters_by_project(project_id)
        if not project: return None

        token = self.auth.get_access_token()
        if not token: return None

        # Chỉ lấy các trường server cần
        exclude_fields = {'id', 'server_id', 'server_request_id', 'sync_status', 'created_at', 'updated_at'}
        proj_dict = {k: v for k, v in asdict(project).items() if k not in exclude_fields and v is not None}
        
        inv_list = []
        for inv in inverters:
            inv_dict = {k: v for k, v in asdict(inv).items() if k not in exclude_fields and v is not None}
            inv_list.append(inv_dict)

        payload = {
            "project": proj_dict,
            "inverters": inv_list
        }

        try:
            url = f"{API_BASE_URL}/api/project/requests/"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            resp = requests.post(url, json=payload, headers=headers, timeout=20)
            if resp.status_code in [200, 201, 202]:
                res_data = resp.json()
                request_id = res_data.get("id")
                if request_id:
                    self.project_svc.update_project_sync(project_id, server_request_id=request_id, status='pending')
                    return request_id
        except Exception as e:
            logger.error(f"[Sync] Initiate sync error: {e}")
        
        return None

    def background_poll_status(self, request_id: int, project_id: int):
        """Theo dõi trạng thái phê duyệt từ Admin."""
        max_retries = 120 # 2 tiếng (1 phút / lần)
        for _ in range(max_retries):
            token = self.auth.get_access_token()
            if not token: 
                time.sleep(60)
                continue

            try:
                url = f"{API_BASE_URL}/api/project/requests/{request_id}"
                headers = {"Authorization": f"Bearer {token}"}
                resp = requests.get(url, headers=headers, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "").lower()
                    
                    if status == "approved":
                        # Cập nhật ID sau khi Admin duyệt
                        server_id = data.get("server_id") # Hoặc tùy key server trả về khi approved
                        self.project_svc.update_project_sync(project_id, server_id=server_id, status='approved')
                        
                        # Cập nhật inverters nếu có map
                        inv_map = data.get("inverter_map", {})
                        local_invs = self.project_svc.get_inverters_by_project(project_id)
                        for li in local_invs:
                            s_inv_id = inv_map.get(li.serial_number)
                            if s_inv_id:
                                self.project_svc.update_inverter_sync(li.id, server_id=s_inv_id, status='approved')
                        
                        logger.info(f"[Sync] Project {project_id} APPROVED by Admin.")
                        break
                    elif status == "rejected":
                        self.project_svc.update_project_sync(project_id, status='rejected')
                        break
            except Exception as e:
                logger.error(f"[Sync] Polling error: {e}")
            
            time.sleep(60)

    def cancel_sync(self, project_id: int) -> bool:
        """Hủy yêu cầu đồng bộ."""
        sync_info = self.project_svc.metadata_db.get_project_sync_info(project_id)
        if not sync_info or not sync_info.get("server_request_id"):
            return False

        request_id = sync_info["server_request_id"]
        token = self.auth.get_access_token()
        if not token: return False

        try:
            url = f"{API_BASE_URL}/api/project/requests/{request_id}/"
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.delete(url, headers=headers, timeout=10)
            if resp.status_code in [200, 204]:
                self.project_svc.update_project_sync(project_id, status='pending', server_request_id=0)
                return True
        except Exception: pass
    def sync_project_to_server(self, project_id: int) -> Optional[int]:
        """
        [COMPATIBILITY WRAPPER] 
        Hàm này mô phỏng logic cũ nhưng sử dụng quy trình 'Advanced Sync'.
        Dùng cho các script hoặc UI cũ chưa cập nhật luồng từng bước.
        """
        logger.info(f"[Sync-Compat] Triggering sync for project {project_id}")
        
        # 1. Thử auto-match trước
        if self.pre_sync_check(project_id):
            proj = self.project_svc.get_project(project_id)
            return proj.server_id if proj else None
            
        # 2. Nếu không match, khởi tạo request mới
        request_id = self.initiate_sync_request(project_id)
        if request_id:
            logger.info(f"[Sync-Compat] Request {request_id} initiated. Starting background poll.")
            # Trong môi trường script, việc start thread polling có thể cần cân nhắc.
            # Nhưng để 'WEB chạy bình thường' (FastAPI), chúng ta có thể dùng BackgroundTasks 
            # Tuy nhiên ở layer Service này, chúng ta chỉ trả về ID và để API lo việc poll nếu cần.
            # Với script, user sẽ phải đợi hoặc chạy lại script sau.
            return None # Trả về None vì chưa có Server ID ngay lập tức
        
        return None

    def sync_inverters_to_server(self, project_id: int) -> int:
        """
        [COMPATIBILITY WRAPPER]
        Trả về số lượng inverter đang ở trạng thái chờ duyệt hoặc đã duyệt.
        """
        invs = self.project_svc.get_inverters_by_project(project_id)
        return len(invs)
