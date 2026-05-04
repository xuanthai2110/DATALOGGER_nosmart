from typing import List, Optional
from backend.models.comm import CommConfig
import serial.tools.list_ports

class CommService:
    def __init__(self, metadata_db):
        self.metadata_db = metadata_db

    def get_available_ports(self):
        """Liệt kê các cổng serial (COM) có sẵn trên hệ thống."""
        ports = serial.tools.list_ports.comports()
        return [{"device": p.device, "description": p.description} for p in ports]

    def get_comm(self) -> List[CommConfig]:
        return self.metadata_db.get_comm()

    def get_comm_config(self) -> List[CommConfig]:
        """Tương đương get_comm"""
        return self.metadata_db.get_comm_config()

    def get_comm_id(self, config_id: int) -> Optional[CommConfig]:
        return self.metadata_db.get_comm_id(config_id)

    def post_comm(self, data: CommConfig) -> int:
        return self.metadata_db.post_comm(data)

    def patch_comm(self, config_id: int, updates: dict):
        return self.metadata_db.patch_comm(config_id, updates)

    def delete_comm(self, config_id: int):
        return self.metadata_db.delete_comm(config_id)

    def reset_comm(self):
        return self.metadata_db.reset_comm()
