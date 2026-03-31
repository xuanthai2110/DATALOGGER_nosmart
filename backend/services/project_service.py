import logging
from dataclasses import asdict
from typing import Optional, List, Dict, Any
from backend.models.project import ProjectCreate, ProjectResponse, ProjectUpdate
from backend.models.inverter import InverterCreate, InverterResponse, InverterUpdate
from backend.models.realtime import ProjectRealtimeResponse, ProjectRealtimeCreate
import requests
import time
import threading
from backend.core.config import API_BASE_URL
from backend.services.auth_service import AuthService

logger = logging.getLogger(__name__)

class ProjectService:
    def __init__(self, metadata_db, realtime_db, cache_db=None):
        self.metadata_db = metadata_db
        self.realtime_db = realtime_db
        self.cache_db = cache_db
        self.auth = AuthService()

    # ==============================
    # PROJECT
    # ==============================

    def create_project(self, data: ProjectCreate) -> int:
        return self.metadata_db.post_project(data)
    
    def get_project(self, project_id: int) -> Optional[ProjectResponse]:
        return self.metadata_db.get_project(project_id)

    def get_projects(self) -> List[ProjectResponse]:
        return self.metadata_db.get_projects()

    def update_project(self, project_id: int, data: ProjectUpdate):
        return self.metadata_db.patch_project(project_id, data)

    def update_project_sync(self, project_id: int, server_id: Optional[int] = None, server_request_id: Optional[int] = None, status: str = 'pending'):
        return self.metadata_db.update_project_sync(project_id, server_id, server_request_id, status)

    def upsert_project(self, data: ProjectCreate, project_id: Optional[int] = None) -> ProjectResponse:
        return self.metadata_db.upsert_project(data, project_id)

    def delete_project(self, project_id):
        """Xoá project và toàn bộ dữ liệu liên quan"""
        inverters = self.metadata_db.get_inverters_by_project(project_id)
        for inv in inverters:
            self.realtime_db.delete_inverter_data(inv.id)
        
        self.metadata_db.delete_project(project_id)
        return True

    # ==============================
    # INVERTER
    # ==============================

    def get_inverter(self) -> List[InverterResponse]:
        return self.metadata_db.get_all_inverters()

    def create_inverter(self, data: InverterCreate) -> int:
        return self.metadata_db.post_inverter(data)

    def upsert_inverter(self, data: InverterCreate) -> int:
        return self.metadata_db.upsert_inverter(data)

    def patch_inverter(self, inverter_id: int, updates: InverterUpdate):
        return self.metadata_db.patch_inverter(inverter_id, updates)

    def get_inverter_id(self, inverter_id: int) -> Optional[InverterResponse]:
        return self.metadata_db.get_inverter_by_id(inverter_id)

    def delete_inverter(self, inverter_id: int):
        self.realtime_db.delete_inverter_data(inverter_id)
        self.metadata_db.delete_inverter(inverter_id)
        return True

    def get_inverters_by_project(self, project_id: int) -> List[InverterResponse]:
        return self.metadata_db.get_inverters_by_project(project_id)

    def update_inverter_sync(self, inverter_id: int, server_id: Optional[int] = None, status: str = 'pending'):
        return self.metadata_db.update_inverter_sync(inverter_id, server_id, status)

    # ==============================
    # CACHE (RAM) - Dành cho Polling & Realtime UI
    # ==============================

    def upsert_inverter_ac_cache(self, inverter_id: int, project_id: int, data: dict):
        if self.cache_db:
            self.cache_db.upsert_inverter_ac(inverter_id, project_id, data)

    def upsert_mppt_cache(self, inverter_id: int, project_id: int, mppts: List[dict]):
        if self.cache_db:
            self.cache_db.upsert_mppt_batch(inverter_id, project_id, mppts)

    def upsert_string_cache(self, inverter_id: int, project_id: int, strings: List[dict]):
        if self.cache_db:
            self.cache_db.upsert_string_batch(inverter_id, project_id, strings)

    def upsert_error_cache(self, inverter_id: int, project_id: int, status_code: int, fault_code: int):
        if self.cache_db:
            self.cache_db.upsert_error(inverter_id, project_id, status_code, fault_code)

    # ==============================
    # OUTBOX - Dành cho Telemetry & Uploader
    # ==============================

    def post_to_outbox(self, project_id: int, data: dict):
        self.realtime_db.post_to_outbox(project_id, data)

    def get_all_outbox(self) -> List[dict]:
        return self.realtime_db.get_all_outbox()

    def delete_from_outbox(self, record_id: int):
        self.realtime_db.delete_from_outbox(record_id)

    # ==============================
    # REALTIME (DISK) - Lưu trữ lịch sử
    # ==============================

    def get_latest_project_data(self, project_id: int):
        return self.realtime_db.get_latest_project_realtime(project_id)

    def cleanup_old_data(self, before_timestamp: str):
        return self.realtime_db.delete_before(before_timestamp)

    # ==============================
    # SYNC LOGIC (ADVANCED)
    # ==============================

    def pre_sync_check(self, project_id: int) -> bool:
        """Kiểm tra xem project đã có trên server chưa dựa trên số công tơ."""
        project = self.get_project(project_id)
        if not project or not project.elec_meter_no:
            return False

        token = self.auth.get_access_token()
        if not token: return False

        try:
            url = f"{API_BASE_URL}/api/projects/?telemetry=false"
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200: return False

            server_projects = response.json()
            # server_projects là list các project đã approved
            matched_server_project = None
            for sp in server_projects:
                if sp.get("elec_meter_no") == project.elec_meter_no:
                    matched_server_project = sp
                    break
            
            if not matched_server_project:
                return False

            # So khớp inverters
            local_inverters = self.get_inverters_by_project(project_id)
            server_inverters = matched_server_project.get("inverters", [])
            
            # Map inverter local -> server by serial_number
            inv_map = {} # serial -> server_id
            for si in server_inverters:
                inv_map[si.get("serial_number")] = si.get("id")

            # Kiểm tra xem tất cả inverters local có trên server và khớp serial không
            all_match = True
            for li in local_inverters:
                if li.serial_number not in inv_map:
                    all_match = False
                    break
            
            if all_match:
                # Cập nhật local
                server_id = matched_server_project.get("id")
                self.update_project_sync(project_id, server_id=server_id, status='approved')
                for li in local_inverters:
                    s_inv_id = inv_map.get(li.serial_number)
                    self.update_inverter_sync(li.id, server_id=s_inv_id, status='approved')
                return True
                
        except Exception as e:
            logger.error(f"Pre-sync check error: {e}")
        
        return False

    def initiate_sync_request(self, project_id: int) -> Optional[int]:
        """Gửi yêu cầu đồng bộ lên server (POST /api/project/requests/)"""
        project = self.get_project(project_id)
        inverters = self.get_inverters_by_project(project_id)
        if not project: return None

        token = self.auth.get_access_token()
        if not token: return None

        payload = {
            "project": asdict(project),
            "inverters": [asdict(inv) for inv in inverters]
        }
        # Clean payload
        payload["project"].pop("id", None)
        for inv in payload["inverters"]:
            inv.pop("id", None)
            inv.pop("project_id", None)

        try:
            url = f"{API_BASE_URL}/api/project/requests/"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            if response.status_code in [200, 201, 202]:
                res_data = response.json()
                request_id = res_data.get("id") or res_data.get("server_request_id")
                if request_id:
                    self.update_project_sync(project_id, server_request_id=request_id, status='pending')
                    for inv in inverters:
                        self.update_inverter_sync(inv.id, status='pending')
                    return request_id
        except Exception as e:
            logger.error(f"Initiate sync error: {e}")
        
        return None

    def background_poll_status(self, request_id: int, project_id: int):
        """Polling server để cập nhật trạng thái phê duyệt (Chạy trong BackgroundTask)"""
        max_retries = 60 # Ví dụ poll trong 1 tiếng (1 phút / lần)
        retry_count = 0
        
        while retry_count < max_retries:
            token = self.auth.get_access_token()
            if not token: 
                time.sleep(60)
                continue

            try:
                url = f"{API_BASE_URL}/api/project/requests/{request_id}"
                headers = {"Authorization": f"Bearer {token}"}
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "pending").lower()
                    
                    if status == "approved":
                        server_id = data.get("server_id")
                        self.update_project_sync(project_id, server_id=server_id, status='approved')
                        # Cập nhật inverters nếu có map trả về
                        inv_map = data.get("inverter_map", {}) # serial -> server_id
                        local_invs = self.get_inverters_by_project(project_id)
                        for li in local_invs:
                            s_inv_id = inv_map.get(li.serial_number)
                            self.update_inverter_sync(li.id, server_id=s_inv_id, status='approved')
                        logger.info(f"Project {project_id} sync approved on server.")
                        break
                    elif status == "rejected":
                        self.update_project_sync(project_id, status='rejected')
                        logger.warning(f"Project {project_id} sync rejected by admin.")
                        break
                
            except Exception as e:
                logger.error(f"Polling sync status error: {e}")
            
            retry_count += 1
            time.sleep(60)

    def cancel_sync(self, project_id: int) -> bool:
        """Hủy yêu cầu đồng bộ (DELETE /api/project/requests/{id})"""
        sync_info = self.metadata_db.get_project_sync_info(project_id)
        if not sync_info or not sync_info.get("server_request_id"):
            return False

        request_id = sync_info["server_request_id"]
        token = self.auth.get_access_token()
        if not token: return False

        try:
            url = f"{API_BASE_URL}/api/project/requests/{request_id}/"
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.delete(url, headers=headers, timeout=10)
            
            if response.status_code in [200, 204]:
                # Reset local status
                self.update_project_sync(project_id, status='pending', server_request_id=0)
                inverters = self.get_inverters_by_project(project_id)
                for inv in inverters:
                    self.update_inverter_sync(inv.id, status='pending')
                return True
        except Exception as e:
            logger.error(f"Cancel sync error: {e}")
            
        return False
