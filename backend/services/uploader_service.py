import requests
import json
import logging
from config import API_BASE_URL
from services.auth_service import AuthService

logger = logging.getLogger(__name__)

class UploaderService:
    def __init__(self, realtime_db):
        self.db = realtime_db
        self.auth = AuthService()
        self.token = None

    def upload(self):
        token = self.auth.get_access_token()
        if not token:
            return

        data_list = self.db.get_all_outbox()
        if not data_list:
            return

        for data in data_list:
            try:
                # Tạo bản sao sạch để debug và gửi
                payload = data.copy()
                payload.pop("id", None)
                payload.pop("project_id", None)
                payload.pop("server_id", None)
                payload.pop("timestamp", None)

                server_id = data.get("server_id")
                if not server_id:
                    logger.warning(f"Project (local_id: {data.get('project_id')}) has no server_id. Skipping upload.")
                    continue

                url = f"{API_BASE_URL}/api/telemetry/project/{server_id}"
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                
                response = requests.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    self.db.delete_from_outbox(data["id"])
                    logger.info(f"Uploaded telemetry for project_id {data.get('project_id')} to server_id {server_id}")
                else:
                    logger.warning(f"Upload failed for project {server_id}: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Upload error: {e}")

    def send_immediate(self, data: dict):
        """Gửi dữ liệu lỗi hoặc thay đổi trạng thái ngay lập tức lên server"""
        token = self.auth.get_access_token()
        if not token:
            return
        
        server_id = data.get("server_id")
        
        # Sửa lỗi 422: Loại bỏ extra fields
        payload = data.copy()
        payload.pop("project_id", None)
        payload.pop("server_id", None)
        payload.pop("timestamp", None)

        if not server_id:
            logger.warning(f"Project (local_id: {data.get('project_id')}) has no server_id. Cannot send immediate update.")
            return

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        # Tạm thời sử dụng endpoint telemetry cho tin nhắn tức thời nếu chưa có endpoint riêng
        url = f"{API_BASE_URL}/api/telemetry/project/{server_id}"
        
        try:
            logger.info(f"Sending immediate update for server_id: {server_id}...")
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Immediate send failed for {server_id}: {response.status_code} - {response.text}")
            else:
                logger.info(f"Immediate update for server_id {server_id} sent successfully.")
        except Exception as e:
            logger.error(f"Immediate send error: {e}")