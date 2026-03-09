import requests
import logging
from dataclasses import asdict
from config import API_BASE_URL
from schemas.project import ProjectCreate, ProjectUpdate
from schemas.inverter import InverterCreate, InverterUpdate

logger = logging.getLogger(__name__)

class SetupService:
    def __init__(self, auth_service, metadata_db):
        self.auth = auth_service
        self.metadata_db = metadata_db

    def scan_inverters(self, transport, project_id: int, driver_class) -> list[int]:
        """
        Quét slave ID từ 1 đến 30. Nếu inverter phản hồi, lưu vào local DB.
        Trả về danh sách ID local của các inverter tìm thấy.
        """
        found_ids = []
        logger.info(f"[Setup] Starting scan for inverters (Slave 1-30) using {driver_class.__name__}")
        
        for slave_id in range(1, 31):
            try:
                driver = driver_class(transport, slave_id=slave_id)
                info = driver.read_info()
                
                if info.get("is_active"):
                    logger.info(f"[Setup] Found active inverter at Slave ID {slave_id}: {info['serial_number']}")
                    info["project_id"] = project_id
                    inv_data = InverterCreate(**info)
                    local_id = self.metadata_db.upsert_inverter(inv_data)
                    found_ids.append(local_id)
                else:
                    logger.debug(f"[Setup] No active inverter at Slave ID {slave_id}")
            except Exception as e:
                logger.debug(f"[Setup] Error scanning Slave ID {slave_id}: {e}")
                continue
                
        logger.info(f"[Setup] Scan complete. Found {len(found_ids)} inverters.")
        return found_ids

    def get_local_project(self):
        """Lấy thông tin project duy nhất ở local"""
        return self.metadata_db.get_project_first()

    def sync_project_to_server(self, project_id: int) -> int | None:
        """
        Đẩy project local lên server nếu chưa có, hoặc cập nhật nếu thông tin khác nhau.
        """
        local_project = self.metadata_db.get_project(project_id)
        if not local_project:
            logger.error(f"[Sync] No project found with ID {project_id}")
            return None

        token = self.auth.get_access_token()
        if not token:
            return None

        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Thử lấy thông tin từ server (giả định dùng id local hoặc list)
        # Trong thực tế, datalogger thường chỉ có 1 project.
        # Nếu đã có server_id trong local DB (chúng ta đang dùng ID local tương ứng server_id)
        # thì ta thử GET.
        url = f"{API_BASE_URL}/api/projects/{project_id}"
        try:
            get_resp = requests.get(url, headers=headers, timeout=5)
            if get_resp.status_code == 200:
                server_data = get_resp.json()
                # So sánh và PATCH nếu khác
                return self._compare_and_patch_project(project_id, local_project, server_data, headers)
            elif get_resp.status_code == 404:
                # Tạo mới
                return self._create_project_on_server(local_project, headers)
            else:
                logger.error(f"[Sync] Project sync error: {get_resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"[Sync] Request exception: {e}")
            return None

    def _create_project_on_server(self, local_project, headers):
        url = f"{API_BASE_URL}/api/projects/"
        payload = {k: v for k, v in asdict(local_project).items() if v is not None}
        if "id" in payload: del payload["id"] # Server tự gen ID hoặc map
        
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            server_project = resp.json()
            logger.info(f"[Sync] Project created on server: {server_project.get('id')}")
            return server_project.get("id")
        return None

    def _compare_and_patch_project(self, project_id, local_project, server_data, headers):
        # Đơn giản hoá: check name hoặc capacity
        is_different = False
        if local_project.name != server_data.get("name") or \
           local_project.capacity_kwp != server_data.get("capacity_kwp"):
            is_different = True
        
        if is_different:
            url = f"{API_BASE_URL}/api/projects/{project_id}"
            payload = {k: v for k, v in asdict(local_project).items() if v is not None}
            resp = requests.patch(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                logger.info(f"[Sync] Project updated on server: {project_id}")
                return project_id
        return project_id

    def sync_inverters_to_server(self, project_id: int):
        """Đẩy tất cả inverter của project lên server và đồng bộ"""
        local_inverters = self.metadata_db.get_inverters_by_project(project_id)
        token = self.auth.get_access_token()
        if not token: return
        headers = {"Authorization": f"Bearer {token}"}

        for inv in local_inverters:
            # Dùng serial_number làm key định danh trên server (nếu API hỗ trợ)
            # Giả định API GET /api/inverters/{id}
            url = f"{API_BASE_URL}/api/inverters/{inv.id}"
            try:
                get_resp = requests.get(url, headers=headers, timeout=5)
                if get_resp.status_code == 200:
                    server_data = get_resp.json()
                    self._compare_and_patch_inverter(inv.id, inv, server_data, headers)
                elif get_resp.status_code == 404:
                    self._create_inverter_on_server(inv, headers)
            except Exception as e:
                logger.error(f"[Sync] Inverter sync exception for {inv.serial_number}: {e}")

    def _compare_and_patch_inverter(self, inv_id, local_inv, server_data, headers):
        is_different = False
        if local_inv.serial_number != server_data.get("serial_number") or \
           local_inv.capacity_kw != server_data.get("capacity_kw"):
            is_different = True
        
        if is_different:
            url = f"{API_BASE_URL}/api/inverters/{inv_id}"
            payload = {k: v for k, v in asdict(local_inv).items() if v is not None}
            if "id" in payload: del payload["id"]
            resp = requests.patch(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                logger.info(f"[Sync] Inverter {local_inv.serial_number} updated on server")

    def _create_inverter_on_server(self, inv, headers):
        url = f"{API_BASE_URL}/api/inverters/"
        payload = asdict(inv)
        if "id" in payload: del payload["id"]
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            logger.info(f"[Sync] Inverter {inv.serial_number} created on server")
