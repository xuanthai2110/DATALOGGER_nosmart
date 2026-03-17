import requests
import json
import logging
from config import API_BASE_URL
from services.auth_service import AuthService

logger = logging.getLogger(__name__)

class UploaderService:
    def __init__(self, buffer_service):
        self.buffer = buffer_service
        self.auth = AuthService()
        self.token = None

    def upload(self):
        token = self.auth.get_access_token()
        if not token:
            return

        data_list = self.buffer.get_all()
        if not data_list:
            return

        for data in data_list:
            try:
                server_id = data.get("server_id")
                if not server_id:
                    logger.warning(f"Project (local_id: {data.get('project_id')}) has no server_id. It might not be approved yet. Skipping upload.")
                    continue

                url = f"{API_BASE_URL}/api/telemetry/project/{server_id}"
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                
                # Sửa lỗi 422: Loại bỏ các trường extra không có trong schema server
                payload = data.copy()
                payload.pop("id", None)
                payload.pop("project_id", None)
                payload.pop("server_id", None)
                payload.pop("timestamp", None)
                
                # In JSON để debug
                logger.debug(f"DEBUG SENDING CLEAN PAYLOAD (server_id: {server_id}):\n{json.dumps(payload, indent=2)}")
                
                response = requests.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    self.buffer.delete(data["id"])
                else:
                    logger.warning(f"Upload failed for project {project_id}: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Upload error: {e}")

    def send_immediate(self, data: dict):
        """Gửi dữ liệu lỗi hoặc thay đổi trạng thái ngay lập tức lên server"""
        token = self.auth.get_access_token()
        if not token:
            return
        
        server_id = data.get("server_id")
        if not server_id:
            logger.warning(f"Project (local_id: {data.get('project_id')}) has no server_id. Cannot send immediate update.")
            return

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        # Tạm thời sử dụng endpoint telemetry cho tin nhắn tức thời nếu chưa có endpoint riêng
        url = f"{API_BASE_URL}/api/telemetry/project/{server_id}"
        
        # Sửa lỗi 422: Loại bỏ extra fields
        payload = data.copy()
        payload.pop("project_id", None)
        payload.pop("server_id", None)
        payload.pop("timestamp", None)

        try:
            logger.info(f"Sending immediate update for server_id: {server_id}...")
            # In JSON để debug
            logger.debug(f"DEBUG SENDING CLEAN IMMEDIATE PAYLOAD:\n{json.dumps(payload, indent=2)}")
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Immediate send failed for {server_id}: {response.status_code} - {response.text}")
            else:
                logger.info(f"Immediate update for project {project_id} sent successfully.")
        except Exception as e:
            logger.error(f"Immediate send error: {e}")