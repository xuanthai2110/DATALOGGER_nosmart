import requests
from config import API_BASE_URL
from services.auth_service import AuthService

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
                # Lấy project_id từ payload (TelemetryService đã đóng gói có project_id)
                project_id = data.get("project_id")
                if not project_id:
                    logger.error("No project_id found in telemetry data, skipping")
                    continue

                url = f"{API_BASE_URL}/api/telemetry/project/{project_id}"
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
        
        project_id = data.get("project_id")
        if not project_id:
            logger.error("No project_id found in immediate data")
            return

        headers = {"Authorization": f"Bearer {token}"}
        # Tạm thời sử dụng endpoint telemetry cho tin nhắn tức thời nếu chưa có endpoint riêng
        url = f"{API_BASE_URL}/api/telemetry/project/{project_id}"
        
        try:
            logger.info(f"Sending immediate update for project {project_id}...")
            response = requests.post(url, json=data, headers=headers, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Immediate send failed: {response.status_code} - {response.text}")
            else:
                logger.info(f"Immediate update for project {project_id} sent successfully.")
        except Exception as e:
            logger.error(f"Immediate send error: {e}")