import requests
import logging
import time
from typing import Optional, List
from datetime import datetime, timezone
from dataclasses import asdict
from backend.core.settings import API_BASE_URL
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
            
        if local_project.server_id:
            return False

        token = self.auth.get_access_token()
        if not token: return False

        try:
            base_api = API_BASE_URL.rstrip('/')
            # 1. So khớp Project
            url = f"{base_api}/api/projects/?telemetry=false"
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(url, headers=headers, timeout=10)
            
            if resp.status_code == 401:
                logger.info("[Sync] Pre-sync: 401 detected, attempting to recover...")
                token = self.auth.handle_unauthorized()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    resp = requests.get(url, headers=headers, timeout=10)

            if resp.status_code != 200:
                logger.warning(f"[Sync] Pre-sync: Server returned {resp.status_code}")
                return False

            data_items = resp.json().get("data", [])
            matched_proj_data = None
            for item in data_items:
                proj_data = item.get("project", {})
                if proj_data.get("elec_meter_no") == local_project.elec_meter_no:
                    matched_proj_data = proj_data
                    break
            
            if matched_proj_data:
                server_proj_id = matched_proj_data.get("id")
                self.project_svc.update_project_sync(project_id, server_id=server_proj_id, status='approved')
                logger.info(f"[Sync] Auto-matched project {project_id} -> Server ID {server_proj_id}")
                
                # 2. Thử so khớp Inverters của project này
                # Giả định server có endpoint lấy inverters hoặc lọc theo project_id server
                inv_url = f"{base_api}/api/inverters/?telemetry=false" # Lấy hết hoặc thêm filter nếu server hỗ trợ
                inv_resp = requests.get(inv_url, headers=headers, timeout=10)
                if inv_resp.status_code == 200:
                    server_invs = inv_resp.json().get("data", [])
                    local_invs = self.project_svc.get_inverters_by_project(project_id)
                    
                    for li in local_invs:
                        for si_item in server_invs:
                            si = si_item.get("inverter", si_item) # Support both nested and flat
                            if si.get("serial_number") == li.serial_number:
                                self.project_svc.update_inverter_sync(li.id, server_id=si.get("id"), status='approved')
                                logger.info(f"[Sync] Auto-matched inverter {li.serial_number} -> Server ID {si.get('id')}")
                                break
                
                return True
        except Exception as e:
            logger.error(f"[Sync] Pre-sync error: {e}")
        
        return False

    def initiate_project_sync(self, project_id: int) -> Optional[int]:
        """Gửi yêu cầu đồng bộ Project (POST /api/projects/requests/)"""
        project = self.project_svc.get_project(project_id)
        if not project: return None

        token = self.auth.get_access_token()
        if not token: return None

        # Danh sách các trường Project theo yêu cầu server
        project_fields = {
            'elec_meter_no', 'elec_price_per_kwh', 'name', 'location', 
            'lat', 'lon', 'capacity_kwp', 'ac_capacity_kw', 'inverter_count'
        }
        payload = {k: v for k, v in asdict(project).items() if k in project_fields}

        try:
            base_api = API_BASE_URL.rstrip('/')
            url = f"{base_api}/api/projects/requests/"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            
            # 0. Nếu dự án ĐÃ ĐƯỢC DUYỆT, ta dùng POST update với full payload
            if project.server_id and project.sync_status == 'approved':
                # KIỂM TRA SỰ THAY ĐỔI
                check_url = f"{base_api}/api/projects/{project.server_id}"
                get_resp = requests.get(check_url, headers=headers, timeout=10)
                if get_resp.status_code == 401:
                    token = self.auth.handle_unauthorized()
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        get_resp = requests.get(check_url, headers=headers, timeout=10)
                
                diff_payload = payload
                if get_resp.status_code == 200:
                    server_data = get_resp.json()
                    diff_payload = {}
                    for k, v in payload.items():
                        sv = server_data.get(k)
                        if str(sv) != str(v) and str(sv) != str(v) + ".0":
                            diff_payload[k] = v
                    if not diff_payload:
                        logger.info(f"[Sync] Project {project_id} has no changes. Skipping POST update.")
                        return -1
                        
                update_url = f"{base_api}/api/projects/requests/update/{project.server_id}"
                logger.info(f"[Sync] Project is approved. Sending update request to {update_url} with: {diff_payload}")
                resp = requests.post(update_url, json=diff_payload, headers=headers, timeout=20)
                
                if resp.status_code == 401:
                    token = self.auth.handle_unauthorized()
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        resp = requests.post(update_url, json=payload, headers=headers, timeout=20)
                
                if resp.status_code in [200, 201, 202]:
                    res_data = resp.json()
                    request_id = res_data.get("id")
                    if request_id:
                        self.project_svc.update_project_sync(project_id, server_request_id=request_id, status='pending')
                        return request_id
                else:
                    logger.warning(f"[Sync] Project update request failed: {resp.status_code} - {resp.text}")
                return None

            # 1. Thử PATCH nếu đang ở trạng thái pending
            if project.server_request_id:
                req_url = f"{base_api}/api/projects/requests/{project.server_request_id}"
                check_resp = requests.get(req_url, headers=headers, timeout=10)
                
                if check_resp.status_code == 401:
                    token = self.auth.handle_unauthorized()
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        check_resp = requests.get(req_url, headers=headers, timeout=10)
                
                if check_resp.status_code == 200:
                    server_data = check_resp.json()
                    status = server_data.get("status", "").lower()
                    
                    if status == "pending":
                        patch_payload = {}
                        for k, v in payload.items():
                            if server_data.get(k) != v:
                                patch_payload[k] = v
                        
                        if not patch_payload:
                            logger.info(f"[Sync] Project {project_id} has no changes to patch.")
                            return project.server_request_id
                        
                        logger.info(f"[Sync] Patching project request {project.server_request_id} with: {patch_payload}")
                        patch_resp = requests.patch(req_url, json=patch_payload, headers=headers, timeout=20)
                        
                        if patch_resp.status_code in [200, 201, 202]:
                            return project.server_request_id
                        else:
                            logger.warning(f"[Sync] Project patch failed: {patch_resp.status_code} - {patch_resp.text}")
                            return None
                    else:
                        if status == "approved":
                            server_id = server_data.get("server_id")
                            self.project_svc.update_project_sync(project_id, server_id=server_id, status='approved')
                            logger.info(f"[Sync] Project request {project.server_request_id} already approved on server. Verifying changes...")
                            return self.initiate_project_sync(project_id)
                        elif status == "rejected":
                            self.project_svc.update_project_sync(project_id, status='rejected')
                            logger.info(f"[Sync] Project request {project.server_request_id} was rejected. Sync failed.")
                            return None
                        else:
                            logger.info(f"[Sync] Project request {project.server_request_id} is '{status}'. Cannot patch.")
                        
            # 2. Tạo mới bằng POST nếu chưa có

            resp = requests.post(url, json=payload, headers=headers, timeout=20)
            
            if resp.status_code == 401:
                logger.info("[Sync] Project: 401 detected, attempting to recover...")
                token = self.auth.handle_unauthorized()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    resp = requests.post(url, json=payload, headers=headers, timeout=20)

            if resp.status_code in [200, 201, 202]:
                res_data = resp.json()
                request_id = res_data.get("id")
                if request_id:
                    self.project_svc.update_project_sync(project_id, server_request_id=request_id, status='pending')
                    return request_id
            else:
                logger.warning(f"[Sync] Project sync failed with status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"[Sync] Project sync error: {e}")
        
        return None

    def initiate_inverter_sync(self, inverter_id: int) -> Optional[int]:
        """Gửi yêu cầu đồng bộ Inverter (POST /api/inverters/requests/)"""
        inverter = self.project_svc.get_inverter(inverter_id)
        if not inverter: return None
        
        project_id = inverter.project_id
        sync_info = self.project_svc.metadata_db.get_project_sync_info(project_id)
        if not sync_info: return None

        token = self.auth.get_access_token()
        if not token: return None

        # Danh sách các trường Inverter theo yêu cầu server
        inv_fields = {
            'inverter_index', 'serial_number', 'brand', 'model', 'firmware_version',
            'phase_count', 'mppt_count', 'string_count', 'rate_dc_kwp', 'rate_ac_kw',
            'is_active', 'replaced_by_id', 'usage_start_at', 'usage_end_at'
        }
        payload = {k: v for k, v in asdict(inverter).items() if k in inv_fields}
        
        # Thêm các ID liên kết
        payload["project_id"] = sync_info.get("server_id") or 0
        payload["project_request_id"] = sync_info.get("server_request_id") or 0
        
        # Format date strings if they are objects
        if payload.get("usage_start_at") is None:
            payload["usage_start_at"] = datetime.now(timezone.utc).isoformat()

        try:
            base_api = API_BASE_URL.rstrip('/')
            url = f"{base_api}/api/inverters/requests/"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            
            # 0. Nếu inverter ĐÃ ĐƯỢC DUYỆT, ta dùng POST update với full payload
            if inverter.server_id and inverter.sync_status == 'approved':
                # KIỂM TRA SỰ THAY ĐỔI
                check_url = f"{base_api}/api/inverters/{inverter.server_id}"
                get_resp = requests.get(check_url, headers=headers, timeout=10)
                if get_resp.status_code == 401:
                    token = self.auth.handle_unauthorized()
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        get_resp = requests.get(check_url, headers=headers, timeout=10)
                        
                diff_payload = payload
                if get_resp.status_code == 200:
                    server_data = get_resp.json()
                    diff_payload = {}
                    for k, v in payload.items():
                        sv = server_data.get(k)
                        if str(sv) != str(v) and str(sv) != str(v) + ".0":
                            diff_payload[k] = v
                    if not diff_payload:
                        logger.info(f"[Sync] Inverter {inverter_id} has no changes. Skipping POST update.")
                        return -1
                        
                update_url = f"{base_api}/api/inverters/requests/update/{inverter.server_id}"
                logger.info(f"[Sync] Inverter is approved. Sending update request to {update_url} with: {diff_payload}")
                resp = requests.post(update_url, json=diff_payload, headers=headers, timeout=20)
                
                if resp.status_code == 401:
                    token = self.auth.handle_unauthorized()
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        resp = requests.post(update_url, json=payload, headers=headers, timeout=20)
                
                if resp.status_code in [200, 201, 202]:
                    res_data = resp.json()
                    request_id = res_data.get("id")
                    if request_id:
                        self.project_svc.update_inverter_sync(inverter_id, server_request_id=request_id, status='pending')
                        return request_id
                else:
                    logger.warning(f"[Sync] Inverter update request failed: {resp.status_code} - {resp.text}")
                return None

            # 1. Thử PATCH nếu đang ở trạng thái pending
            if inverter.server_request_id:
                req_url = f"{base_api}/api/inverters/requests/{inverter.server_request_id}"
                check_resp = requests.get(req_url, headers=headers, timeout=10)
                
                if check_resp.status_code == 401:
                    token = self.auth.handle_unauthorized()
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        check_resp = requests.get(req_url, headers=headers, timeout=10)
                        
                if check_resp.status_code == 200:
                    server_data = check_resp.json()
                    status = server_data.get("status", "").lower()
                    
                    if status == "pending":
                        patch_payload = {}
                        for k, v in payload.items():
                            if server_data.get(k) != v:
                                patch_payload[k] = v
                                
                        if not patch_payload:
                            logger.info(f"[Sync] Inverter {inverter_id} has no changes to patch.")
                            return inverter.server_request_id
                            
                        logger.info(f"[Sync] Patching inverter request {inverter.server_request_id} with: {patch_payload}")
                        patch_resp = requests.patch(req_url, json=patch_payload, headers=headers, timeout=20)
                        
                        if patch_resp.status_code in [200, 201, 202]:
                            return inverter.server_request_id
                        else:
                            logger.warning(f"[Sync] Inverter patch failed: {patch_resp.status_code} - {patch_resp.text}")
                            return None
                    else:
                        if status == "approved":
                            server_id = server_data.get("server_id")
                            self.project_svc.update_inverter_sync(inverter_id, server_id=server_id, status='approved')
                            logger.info(f"[Sync] Inverter request {inverter.server_request_id} already approved on server. Verifying changes...")
                            return self.initiate_inverter_sync(inverter_id)
                        elif status == "rejected":
                            self.project_svc.update_inverter_sync(inverter_id, status='rejected')
                            logger.info(f"[Sync] Inverter request {inverter.server_request_id} was rejected. Sync failed.")
                            return None
                        else:
                            logger.info(f"[Sync] Inverter request {inverter.server_request_id} is '{status}'. Cannot patch.")
            # 2. Tạo mới bằng POST nếu chưa có

            resp = requests.post(url, json=payload, headers=headers, timeout=20)
            
            if resp.status_code == 401:
                logger.info("[Sync] Inverter: 401 detected, attempting to recover...")
                token = self.auth.handle_unauthorized()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    resp = requests.post(url, json=payload, headers=headers, timeout=20)

            if resp.status_code in [200, 201, 202]:
                res_data = resp.json()
                request_id = res_data.get("id")
                if request_id:
                    self.project_svc.update_inverter_sync(inverter_id, server_request_id=request_id, status='pending')
                    return request_id
            else:
                logger.warning(f"[Sync] Inverter sync failed with status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"[Sync] Inverter sync error: {e}")
        
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
                base_api = API_BASE_URL.rstrip('/')
                url = f"{base_api}/api/projects/requests/{request_id}"
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

    def request_delete_project_sync(self, project_id: int) -> bool:
        """Gửi yêu cầu xoá Project lên server (POST /api/projects/requests/delete/{server_id})"""
        project = self.project_svc.get_project(project_id)
        if not project or not project.server_id:
            return True

        token = self.auth.get_access_token()
        if not token: return False

        try:
            base_api = API_BASE_URL.rstrip('/')
            url = f"{base_api}/api/projects/requests/delete/{project.server_id}"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            
            resp = requests.post(url, headers=headers, timeout=20)
            if resp.status_code == 401:
                token = self.auth.handle_unauthorized()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    resp = requests.post(url, headers=headers, timeout=20)
            
            if resp.status_code in [200, 201, 202, 204]:
                logger.info(f"[Sync] Sent delete request for project {project_id} (Server ID {project.server_id})")
                return True
            else:
                logger.warning(f"[Sync] Project delete request failed: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            logger.error(f"[Sync] Project delete sync error: {e}")
            return False

    def request_delete_inverter_sync(self, inverter_id: int) -> bool:
        """Gửi yêu cầu xoá Inverter lên server (POST /api/inverters/requests/delete/{server_id})"""
        inverter = self.project_svc.get_inverter_id(inverter_id)
        if not inverter or not inverter.server_id:
            return True

        token = self.auth.get_access_token()
        if not token: return False

        try:
            base_api = API_BASE_URL.rstrip('/')
            url = f"{base_api}/api/inverters/requests/delete/{inverter.server_id}"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            
            resp = requests.post(url, headers=headers, timeout=20)
            if resp.status_code == 401:
                token = self.auth.handle_unauthorized()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    resp = requests.post(url, headers=headers, timeout=20)
            
            if resp.status_code in [200, 201, 202, 204]:
                logger.info(f"[Sync] Sent delete request for inverter {inverter_id} (Server ID {inverter.server_id})")
                return True
            else:
                logger.warning(f"[Sync] Inverter delete request failed: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            logger.error(f"[Sync] Inverter delete sync error: {e}")
            return False

    def cancel_sync(self, project_id: int) -> bool:
        """Hủy yêu cầu đồng bộ."""
        sync_info = self.project_svc.metadata_db.get_project_sync_info(project_id)
        if not sync_info or not sync_info.get("server_request_id"):
            return False

        request_id = sync_info["server_request_id"]
        token = self.auth.get_access_token()
        if not token: return False

        try:
            base_api = API_BASE_URL.rstrip('/')
            url = f"{base_api}/api/projects/requests/{request_id}"
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
