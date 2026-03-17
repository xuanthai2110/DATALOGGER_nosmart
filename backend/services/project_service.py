from dataclasses import asdict
from typing import Optional, List, Dict, Any
from schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from schemas.inverter import InverterCreate, InverterResponse, InverterUpdate
from schemas.realtime import ProjectRealtimeResponse, ProjectRealtimeCreate

class ProjectService:
    def __init__(self, metadata_db, realtime_db):
        self.metadata_db = metadata_db
        self.realtime_db = realtime_db

    # ==============================
    # PROJECT
    # ==============================

    def create_project(self, data: ProjectCreate) -> int:
        return self.metadata_db.post_project(data)
    
    def get_project(self, project_id: int) -> Optional[ProjectResponse]:
        return self.metadata_db.get_project(project_id)

    def get_all_projects(self) -> List[ProjectResponse]:
        return self.metadata_db.get_projects()

    def update_project(self, project_id: int, data: ProjectUpdate):
        return self.metadata_db.patch_project(project_id, data)

    def delete_project(self, project_id):
        """
        Xoá project và toàn bộ dữ liệu liên quan
        """

        # 1️⃣ Lấy inverter thuộc project
        inverters = self.metadata_db.get_inverters_by_project(project_id)

        # 2️⃣ Xoá realtime data
        for inv in inverters:
            self.realtime_db.delete_inverter_data(inv.id)

        # 3️⃣ Xoá metadata (cascade mppt + string)
        self.metadata_db.delete_project(project_id)

        return True

    # ==============================
    # INVERTER
    # ==============================

    def create_inverter(self, data: InverterCreate) -> int:
        return self.metadata_db.post_inverter(data)

    def get_inverter(self, inverter_id: int) -> Optional[InverterResponse]:
        return self.metadata_db.get_inverter(inverter_id)

    def delete_inverter(self, inverter_id: int):
        self.realtime_db.delete_inverter_data(inverter_id)
        self.metadata_db.delete_inverter(inverter_id)
        return True

    # ==============================
    # REALTIME
    # ==============================

    def add_project_realtime_data(self, data: ProjectRealtimeCreate):
        """
        Ghi dữ liệu realtime cho Project
        """
        return self.realtime_db.post_project_realtime(data)

    def get_latest_project_data(self, project_id: int):
        # Lấy bản ghi mới nhất trong dải thời gian rộng
        data = self.realtime_db.get_project_realtime_range(project_id, "2000-01-01", "2100-01-01")
        return data[-1] if data else None

    def get_project_snapshot(self, project_id: int) -> Dict[str, Any]:
        """
        Lấy trạng thái realtime toàn bộ dự án với hiệu suất tối ưu (Batch Loading).
        Đây là phiên bản nâng cấp của get_project_dashboard.
        """
        # 1. Project Metadata & Realtime
        project_meta = self.get_project(project_id)
        if not project_meta:
            return {}
        
        project_rt = self.get_latest_project_data(project_id)

        # 2. Inverters Metadata
        inverters_meta = self.metadata_db.get_inverters_by_project(project_id)
        
        # 3. Batch Queries (Tương tự logic trong test_readDB.py)
        ac_map = {}
        with self.realtime_db._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY inverter_id ORDER BY created_at DESC) as rn
                    FROM inverter_ac_realtime
                    WHERE project_id = ?
                ) WHERE rn = 1
            """, (project_id,)).fetchall()
            for r in rows: ac_map[r["inverter_id"]] = dict(r)

        mppt_map = {}
        with self.realtime_db._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY inverter_id, mppt_index ORDER BY created_at DESC) as rn
                    FROM mppt_realtime
                    WHERE project_id = ?
                ) WHERE rn = 1
            """, (project_id,)).fetchall()
            for r in rows:
                inv_id = r["inverter_id"]
                if inv_id not in mppt_map: mppt_map[inv_id] = []
                mppt_map[inv_id].append(dict(r))

        string_map = {}
        with self.realtime_db._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY inverter_id, mppt_id, string_id ORDER BY created_at DESC) as rn
                    FROM string_realtime
                    WHERE project_id = ?
                ) WHERE rn = 1
            """, (project_id,)).fetchall()
            for r in rows:
                key = (r["inverter_id"], r["mppt_id"])
                if key not in string_map: string_map[key] = []
                string_map[key].append({
                    "string_index": r["string_id"],
                    "I_mppt": r["I_string"],
                    "Max_I": r["max_I"],
                    "created_at": r["created_at"]
                })

        error_map = {}
        with self.realtime_db._connect() as conn:
            msg_rows = conn.execute("""
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY inverter_id, fault_code ORDER BY created_at DESC) as rn
                    FROM inverter_errors
                    WHERE project_id = ?
                ) WHERE rn = 1
            """, (project_id,)).fetchall()
            for r in msg_rows:
                inv_id = r["inverter_id"]
                if inv_id not in error_map: error_map[inv_id] = []
                error_map[inv_id].append(dict(r))

        # 4. Assembly
        inverters_json = []
        for inv in inverters_meta:
            inv_id = inv.id
            mppts = mppt_map.get(inv_id, [])
            for m in mppts:
                m["strings"] = string_map.get((inv_id, m["mppt_index"]), [])

            inverters_json.append({
                "serial_number": inv.serial_number,
                "strings_per_mppt": getattr(inv, "strings_per_mppt", None),
                "ac": ac_map.get(inv_id),
                "mppts": mppts,
                "errors": error_map.get(inv_id, [])
            })

        return {
            "project": asdict(project_rt) if project_rt else None,
            "metadata": asdict(project_meta),
            "inverters": inverters_json
        }

    # ==============================
    # CLEANUP
    # ==============================

    def cleanup_old_data(self, before_timestamp: str):
        """
        Xoá toàn bộ dữ liệu cũ hơn timestamp
        """

        return self.realtime_db.delete_before(before_timestamp)