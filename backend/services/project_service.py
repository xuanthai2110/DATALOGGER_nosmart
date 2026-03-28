import logging
from dataclasses import asdict
from typing import Optional, List, Dict, Any
from schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from schemas.inverter import InverterCreate, InverterResponse, InverterUpdate
from schemas.realtime import ProjectRealtimeResponse, ProjectRealtimeCreate

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
        # 1. Xoá dữ liệu realtime của từng inverter trong project
        inverters = self.metadata_db.get_inverters_by_project(project_id)
        for inv in inverters:
            self.realtime_db.delete_inverter_data(inv.id)
        
        # 2. Xoá metadata (SqliteManager sẽ tự cascade xoá inverters trong bảng metadata)
        self.metadata_db.delete_project(project_id)
        return True

    # ==============================
    # INVERTER
    # ==============================

    def create_inverter(self, data: InverterCreate) -> int:
        return self.metadata_db.post_inverter(data)

    def get_inverter_id(self, inverter_id: int) -> Optional[InverterResponse]:
        return self.metadata_db.get_inverter_id(inverter_id)

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
        """Lấy dữ liệu realtime mới nhất của dự án (Sử dụng LIMIT 1 để tối ưu)"""
        return self.realtime_db.get_latest_project_realtime(project_id)

    # ==============================
    # SNAPSHOT - Tổng hợp dữ liệu từ CACHE (RAM)
    # ==============================

    def get_project_snapshot(self, project_id: int) -> Dict[str, Any]:
        """
        Lấy trạng thái realtime toàn bộ dự án từ RAM (CacheDB).
        Đây là nguồn dữ liệu chính cho Dashboard và Telemetry Builder.
        """
        if not self.cache_db:
            logger.warning("CacheDB not initialized in ProjectService")
            return {}

        # 1. Metadata
        project_meta = self.get_project(project_id)
        if not project_meta: return {}
        inverters_meta = self.metadata_db.get_inverters_by_project(project_id)

        # 2. Lấy dữ liệu từ RAM Cache (Sử dụng Repository methods để tránh phân tán SQL)
        # a. AC Data
        ac_list = self.cache_db.get_ac_cache_by_project(project_id)
        ac_map = {r["inverter_id"]: r for r in ac_list}

        # b. MPPT Data
        mppt_list = self.cache_db.get_mppt_cache_by_project(project_id)
        mppt_map = {}
        for r in mppt_list:
            inv_id = r["inverter_id"]
            if inv_id not in mppt_map: mppt_map[inv_id] = []
            mppt_map[inv_id].append(r)

        # c. String Data
        string_list = self.cache_db.get_string_cache_by_project(project_id)
        string_map = {}
        for r in string_list:
            key = (r["inverter_id"], r["mppt_id"])
            if key not in string_map: string_map[key] = []
            string_map[key].append({
                "string_id": r["string_id"],
                "I_string": r["I_string"],
                "updated_at": r["updated_at"]
            })

        # d. Error Data
        error_list = self.cache_db.get_error_cache_by_project(project_id)
        error_map = {r["inverter_id"]: r for r in error_list}

        # 3. Assembly
        inverters_json = []
        for inv in inverters_meta:
            inv_id = inv.id
            mppts = mppt_map.get(inv_id, [])
            for m in mppts:
                # Mapping strings vào mppt dựa trên mppt_index
                m["strings"] = string_map.get((inv_id, m["mppt_index"]), [])

            inverters_json.append({
                "serial_number": inv.serial_number,
                "ac": ac_map.get(inv_id),
                "mppts": mppts,
                "error": error_map.get(inv_id)
            })

        # Project Realtime (Lấy từ RealtimeDB disk vì Polling không lưu Project vào Cache RAM)
        project_rt = self.get_latest_project_data(project_id)

        return {
            "project": asdict(project_rt) if project_rt else None,
            "metadata": asdict(project_meta),
            "inverters": inverters_json
        }

    def cleanup_old_data(self, before_timestamp: str):
        """Xoá toàn bộ dữ liệu cũ hơn timestamp"""
        return self.realtime_db.delete_before(before_timestamp)
