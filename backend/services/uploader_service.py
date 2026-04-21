import requests
import json
import logging
from backend.core.settings import API_BASE_URL
from backend.services.auth_service import AuthService

logger = logging.getLogger(__name__)

class UploaderService:
    def __init__(self, realtime_db, metadata_db):
        self.db = realtime_db
        self.metadata_db = metadata_db
        self.auth = AuthService(metadata_db)

    def upload(self):
        data_list = self.db.get_all_outbox()
        if not data_list: return
        for data in data_list:
            try:
                project_id = data.get("project_id")
                server_id = data.get("server_id")
                if not project_id or not server_id: continue
                
                # Look up server_account_id
                proj_meta = self.metadata_db.get_project(project_id)
                if not proj_meta or not proj_meta.server_account_id:
                    logger.warning(f"Project {project_id} has no server account. Skipping upload.")
                    continue
                
                token = self.auth.get_access_token(proj_meta.server_account_id)
                if not token: continue

                data_type = data.get("data_type", "Project")
                payload = data.copy()
                payload.pop("id", None)
                payload.pop("project_id", None)
                payload.pop("server_id", None)
                payload.pop("data_type", None)
                payload.pop("timestamp", None)
                
                if data_type == "EVN":
                    url = f"{API_BASE_URL}/api/telemetry/evn/project/{server_id}"
                else:
                    url = f"{API_BASE_URL}/api/telemetry/project/{server_id}"

                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                
                logger.info(f"[Uploader] Sending {data_type} telemetry for project {server_id} to {url}...")
                response = requests.post(url, json=payload, headers=headers, timeout=15)
                
                if response.status_code == 401:
                    logger.warning(f"[Uploader] 401 Unauthorized for project {server_id}. Attempting token refresh...")
                    token = self.auth.handle_unauthorized(proj_meta.server_account_id)
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        response = requests.post(url, json=payload, headers=headers, timeout=15)
                        logger.info(f"[Uploader] Retry result for project {server_id}: status={response.status_code}")
                
                if response.status_code in (200, 201):
                    self.db.delete_from_outbox(data["id"])
                    logger.info(f"[Uploader] SUCCESS: Uploaded {data_type} for project {server_id} (status={response.status_code})")
                elif response.status_code == 422:
                    logger.warning(f"Validation error (422) for project {server_id}. Attempting to fix payload and retry once...")
                    # Sửa nhanh payload trong bộ nhớ trước khi thử lại
                    self._fix_payload_severity(payload)
                    response = requests.post(url, json=payload, headers=headers)
                    if response.status_code in (200, 201):
                        self.db.delete_from_outbox(data["id"])
                        logger.info(f"Uploaded project {server_id} after fix and retry (status={response.status_code})")
                    else:
                        self.db.delete_from_outbox(data["id"])
                        logger.error(f"Upload failed twice for record {data['id']} (status={response.status_code}). Deleted from outbox. Error: {response.text}")
                elif response.status_code == 409:
                    self.db.delete_from_outbox(data["id"])
                    logger.warning(f"Upload conflict (409) for project {server_id}. Data already exists. Record {data['id']} deleted from outbox.")
                else:
                    logger.warning(f"Upload failed for project {server_id} (status={response.status_code}): {response.text}")
            except Exception as e:
                logger.error(f"Upload error: {e}")

    def _fix_payload_severity(self, obj):
        """Hàm đệ quy để sửa 'NORMAL' thành 'STABLE' trong payload telemetry."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "severity" and v == "NORMAL":
                    obj[k] = "STABLE"
                else:
                    self._fix_payload_severity(v)
        elif isinstance(obj, list):
            for item in obj:
                self._fix_payload_severity(item)

    def send_immediate(self, data: dict):
        project_id = data.get("project_id")
        server_id = data.get("server_id")
        if not project_id or not server_id: return

        proj_meta = self.metadata_db.get_project(project_id)
        if not proj_meta or not proj_meta.server_account_id: return
        
        token = self.auth.get_access_token(proj_meta.server_account_id)
        if not token: return

        data_type = data.get("data_type", "Project")
        payload = data.copy()
        payload.pop("project_id", None)
        payload.pop("server_id", None)
        payload.pop("data_type", None)
        payload.pop("timestamp", None)
        
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        if data_type == "EVN":
            url = f"{API_BASE_URL}/api/telemetry/evn/project/{server_id}"
        else:
            url = f"{API_BASE_URL}/api/telemetry/project/{server_id}"

        try:
            logger.info(f"[Uploader] Sending IMMEDIATE {data_type} for project {server_id} to {url}...")
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 401:
                logger.warning(f"[Uploader] Immediate 401 for project {server_id}. Refreshing token...")
                token = self.auth.handle_unauthorized(proj_meta.server_account_id)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    resp = requests.post(url, json=payload, headers=headers, timeout=10)
            
            logger.info(f"[Uploader] Immediate result for project {server_id}: status={resp.status_code}")
        except Exception as e:
            logger.error(f"[Uploader] Immediate send error: {e}")
