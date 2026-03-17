import requests
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
                headers = {"Authorization": f"Bearer {token}"}
                
                response = requests.post(url, json=data, headers=headers)
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

        headers = {"Authorization": f"Bearer {token}"}
        # Tạm thời sử dụng endpoint telemetry cho tin nhắn tức thời nếu chưa có endpoint riêng
        url = f"{API_BASE_URL}/api/telemetry/project/{server_id}"
        
        try:
            logger.info(f"Sending immediate update for server_id: {server_id}...")
            response = requests.post(url, json=data, headers=headers, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Immediate send failed for {server_id}: {response.status_code} - {response.text}")
            else:
                logger.info(f"Immediate update for project {project_id} sent successfully.")
        except Exception as e:
            logger.error(f"Immediate send error: {e}")