import requests
import json
import logging
from backend.core.settings import API_BASE_URL
from backend.services.auth_service import AuthService

logger = logging.getLogger(__name__)

class UploaderService:
    def __init__(self, realtime_db):
        self.db = realtime_db
        self.auth = AuthService()
        self.token = None

    def upload(self):
        token = self.auth.get_access_token()
        if not token: return
        data_list = self.db.get_all_outbox()
        if not data_list: return
        for data in data_list:
            try:
                payload = data.copy()
                payload.pop("id", None)
                payload.pop("project_id", None)
                payload.pop("server_id", None)
                payload.pop("timestamp", None)
                server_id = data.get("server_id")
                if not server_id: continue
                url = f"{API_BASE_URL}/api/telemetry/project/{server_id}"
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                response = requests.post(url, json=payload, headers=headers)
                if response.status_code in (200, 201):
                    self.db.delete_from_outbox(data["id"])
                    logger.info(f"Uploaded project {server_id} (status={response.status_code})")
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
        token = self.auth.get_access_token()
        if not token: return
        server_id = data.get("server_id")
        payload = data.copy()
        payload.pop("project_id", None)
        payload.pop("server_id", None)
        payload.pop("timestamp", None)
        if not server_id: return
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{API_BASE_URL}/api/telemetry/project/{server_id}"
        try:
            logger.info(f"Sending immediate update for {server_id}...")
            requests.post(url, json=payload, headers=headers, timeout=10)
        except Exception as e:
            logger.error(f"Immediate send error: {e}")
