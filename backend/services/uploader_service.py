import requests
import json
import logging
from core.config import API_BASE_URL
from services.auth_service import AuthService

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
                if response.status_code == 200:
                    self.db.delete_from_outbox(data["id"])
                    logger.info(f"Uploaded project {server_id}")
            except Exception as e:
                logger.error(f"Upload error: {e}")

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