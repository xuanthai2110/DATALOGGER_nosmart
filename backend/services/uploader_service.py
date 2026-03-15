import requests
from config import API_BASE_URL
from services.auth_service import AuthService

class UploaderService:
    def __init__(self, buffer_service):
        self.buffer = buffer_service
        self.auth = AuthService()
        self.token = None

    def upload(self):
        if not self.token:
            self.token = self.auth.login()

        data_list = self.buffer.get_all()
        if not data_list:
            return

        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{API_BASE_URL}/api/inverter-data"

        for data in data_list:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                self.buffer.delete(data["id"])