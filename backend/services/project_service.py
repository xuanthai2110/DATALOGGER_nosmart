import logging
from dataclasses import asdict
from typing import Optional, List, Dict, Any
from models.project import ProjectCreate, ProjectResponse, ProjectUpdate
from models.inverter import InverterCreate, InverterResponse, InverterUpdate
from models.realtime import ProjectRealtimeResponse, ProjectRealtimeCreate

logger = logging.getLogger(__name__)

class ProjectService:
    def __init__(self, metadata_db, realtime_db, cache_db=None):
        self.metadata_db = metadata_db
        self.realtime_db = realtime_db
        self.cache_db = cache_db

    # ==============================
    # PROJECT
    # ==============================

    def create_project(self, data: ProjectCreate) -> int:
        return self.metadata_db.post_project(data)
    
    def get_project(self, project_id: int) -> Optional[ProjectResponse]:
        return self.metadata_db.get_project(project_id)

    def get_projects(self) -> List[ProjectResponse]:
        return self.metadata_db.get_projects()

    def update_project(self, project_id: int, data: ProjectUpdate):
        return self.metadata_db.patch_project(project_id, data)

    def delete_project(self, project_id):
        """Xoá project và toàn bộ dữ liệu liên quan"""
        inverters = self.metadata_db.get_inverters_by_project(project_id)
        for inv in inverters:
            self.realtime_db.delete_inverter_data(inv.id)
        
        self.metadata_db.delete_project(project_id)
        return True

    # ==============================
    # INVERTER
    # ==============================

    def create_inverter(self, data: InverterCreate) -> int:
        return self.metadata_db.post_inverter(data)

    def get_inverter_id(self, inverter_id: int) -> Optional[InverterResponse]:
        return self.metadata_db.get_inverter_by_id(inverter_id)

    def delete_inverter(self, inverter_id: int):
        self.realtime_db.delete_inverter_data(inverter_id)
        self.metadata_db.delete_inverter(inverter_id)
        return True

    # ==============================
    # CACHE (RAM) - Dành cho Polling & Realtime UI
    # ==============================

    def upsert_inverter_ac_cache(self, inverter_id: int, project_id: int, data: dict):
        if self.cache_db:
            self.cache_db.upsert_inverter_ac(inverter_id, project_id, data)

    def upsert_mppt_cache(self, inverter_id: int, project_id: int, mppts: List[dict]):
        if self.cache_db:
            self.cache_db.upsert_mppt_batch(inverter_id, project_id, mppts)

    def upsert_string_cache(self, inverter_id: int, project_id: int, strings: List[dict]):
        if self.cache_db:
            self.cache_db.upsert_string_batch(inverter_id, project_id, strings)

    def upsert_error_cache(self, inverter_id: int, project_id: int, status_code: int, fault_code: int):
        if self.cache_db:
            self.cache_db.upsert_error(inverter_id, project_id, status_code, fault_code)

    # ==============================
    # OUTBOX - Dành cho Telemetry & Uploader
    # ==============================

    def post_to_outbox(self, project_id: int, data: dict):
        self.realtime_db.post_to_outbox(project_id, data)

    def get_all_outbox(self) -> List[dict]:
        return self.realtime_db.get_all_outbox()

    def delete_from_outbox(self, record_id: int):
        self.realtime_db.delete_from_outbox(record_id)

    # ==============================
    # REALTIME (DISK) - Lưu trữ lịch sử
    # ==============================

    def get_latest_project_data(self, project_id: int):
        return self.realtime_db.get_latest_project_realtime(project_id)

    def cleanup_old_data(self, before_timestamp: str):
        return self.realtime_db.delete_before(before_timestamp)
