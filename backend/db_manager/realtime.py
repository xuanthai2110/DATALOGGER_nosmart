import sqlite3
import json
from typing import Optional, List
from dataclasses import asdict
from .base_db import BaseDB, to_dataclass

from backend.models.realtime import (
    ProjectRealtimeCreate, ProjectRealtimeResponse,
    InverterACRealtimeCreate, InverterACRealtimeResponse,
    InverterErrorCreate, InverterErrorResponse,
    mpptRealtimeCreate, mpptRealtimeResponse,
    stringRealtimeCreate, stringRealtimeResponse
)

class RealtimeDB(BaseDB):
    """Quản lý dữ liệu Snapshot ghi xuống Disk (RealtimeDB)."""
    
    def _connect(self):
        conn = super()._connect()
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _create_tables(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            # Uploader Outbox
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS uploader_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                server_id INTEGER,
                data_json TEXT,
                created_at TEXT
            );
            """)
            # Migration uploader_outbox
            cols = {row[1] for row in conn.execute("PRAGMA table_info(uploader_outbox)").fetchall()}
            if "server_id" not in cols:
                conn.execute("ALTER TABLE uploader_outbox ADD COLUMN server_id INTEGER")
            # Project Realtime
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_realtime (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER, Temp_C REAL, P_ac REAL, P_dc REAL,
                E_daily REAL, delta_E_monthly REAL, E_monthly REAL, E_total REAL,
                severity TEXT, created_at TEXT
            );
            """)
            # Inverter AC Realtime
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS inverter_ac_realtime (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER, inverter_id INTEGER,
                IR REAL, Temp_C REAL, P_ac REAL, Q_ac REAL,
                V_a REAL, V_b REAL, V_c REAL, I_a REAL, I_b REAL, I_c REAL,
                PF REAL, H REAL, E_daily REAL, delta_E_monthly REAL, E_monthly REAL, E_total REAL,
                created_at TEXT
            );
            """)
            # Errors
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS inverter_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER, inverter_id INTEGER, fault_code INTEGER,
                fault_description TEXT, repair_instruction TEXT, severity TEXT, created_at TEXT
            );
            """)
            # MPPT & String Realtime tables
            cursor.execute("CREATE TABLE IF NOT EXISTS mppt_realtime (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER, inverter_id INTEGER, mppt_index INTEGER, string_on_mppt INTEGER, V_mppt REAL, I_mppt REAL, P_mppt REAL, Max_I REAL, Max_V REAL, Max_P REAL, created_at TEXT);")
            cursor.execute("CREATE TABLE IF NOT EXISTS string_realtime (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER, inverter_id INTEGER, mppt_id INTEGER, string_id INTEGER, I_string REAL, max_I REAL, created_at TEXT);")

            # --- Migration: sửa typo denta_E_monthly -> delta_E_monthly ---
            cols = {row[1] for row in conn.execute("PRAGMA table_info(inverter_ac_realtime)").fetchall()}
            if "delta_E_monthly" not in cols:
                # Thêm cột mới (SQLite < 3.25 không hỗ trợ RENAME COLUMN)
                conn.execute("ALTER TABLE inverter_ac_realtime ADD COLUMN delta_E_monthly REAL DEFAULT 0")
                # Copy giá trị từ cột typo nếu tồn tại
                if "denta_E_monthly" in cols:
                    conn.execute("UPDATE inverter_ac_realtime SET delta_E_monthly = denta_E_monthly")


    # --- Outbox API ---
    def post_to_outbox(self, project_id: int, server_id: int, data: dict):
        from datetime import datetime
        now_str = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute("INSERT INTO uploader_outbox (project_id, server_id, data_json, created_at) VALUES (?, ?, ?, ?)",
                         (project_id, server_id, json.dumps(data), now_str))

    def get_all_outbox(self) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, project_id, server_id, data_json, created_at FROM uploader_outbox").fetchall()
            result = []
            for r in rows:
                d = json.loads(r["data_json"])
                d["id"] = r["id"]
                d["server_id"] = r["server_id"]
                result.append(d)
            return result

    def delete_from_outbox(self, record_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM uploader_outbox WHERE id=?", (record_id,))

    # --- History API ---
    def post_inverter_error(self, data: InverterErrorCreate):
        d = asdict(data)
        with self._connect() as conn:
            conn.execute("INSERT INTO inverter_errors (project_id, inverter_id, fault_code, fault_description, repair_instruction, severity, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (d["project_id"], d["inverter_id"], d["fault_code"], d["fault_description"], d["repair_instruction"], d["severity"], d["created_at"]))

    def post_inverter_ac_batch(self, records: List[InverterACRealtimeCreate]):
        if not records: return
        values = [(r.project_id, r.inverter_id, r.IR, r.Temp_C, r.P_ac, r.Q_ac, r.V_a, r.V_b, r.V_c, r.I_a, r.I_b, r.I_c, r.PF, r.H, r.E_daily, r.delta_E_monthly, r.E_monthly, r.E_total, r.created_at) for r in records]
        with self._connect() as conn:
            conn.executemany("INSERT INTO inverter_ac_realtime (project_id, inverter_id, IR, Temp_C, P_ac, Q_ac, V_a, V_b, V_c, I_a, I_b, I_c, PF, H, E_daily, delta_E_monthly, E_monthly, E_total, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)

    def get_latest_inverter_ac_realtime(self, inverter_id: int) -> Optional[InverterACRealtimeResponse]:
        """Lấy bản ghi AC realtime mới nhất của inverter từ Disk (dùng khi seed EnergyService)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM inverter_ac_realtime WHERE inverter_id = ? ORDER BY created_at DESC LIMIT 1",
                (inverter_id,)
            ).fetchone()
            return to_dataclass(InverterACRealtimeResponse, row)

    def get_latest_ac_batch(self, project_id: int) -> List[InverterACRealtimeResponse]:
        """Lấy bản ghi AC realtime mới nhất của mỗi inverter trong một project."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM inverter_ac_realtime
                WHERE id IN (
                    SELECT MAX(id) FROM inverter_ac_realtime
                    WHERE project_id = ?
                    GROUP BY inverter_id
                )
            """, (project_id,)).fetchall()
            return [to_dataclass(InverterACRealtimeResponse, r) for r in rows]

    # --- MPPT Realtime API ---
    def get_latest_mppt_batch(self, inverter_id: int) -> List[mpptRealtimeResponse]:
        """Lấy danh sách điểm MPPT mới nhất của 1 inverter từ Disk (dùng khi seed)."""
        with self._connect() as conn:
            # Lấy bản ghi có created_at mới nhất cho inverter này
            rows = conn.execute("""
                SELECT * FROM mppt_realtime
                WHERE inverter_id = ?
                AND created_at = (
                    SELECT MAX(created_at) FROM mppt_realtime WHERE inverter_id = ?
                )
            """, (inverter_id, inverter_id)).fetchall()
            return [to_dataclass(mpptRealtimeResponse, r) for r in rows]

    def get_inverter_errors(self, inverter_id: int) -> List[InverterErrorResponse]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM inverter_errors WHERE inverter_id = ? ORDER BY created_at DESC",
                (inverter_id,)
            ).fetchall()
            return [to_dataclass(InverterErrorResponse, r) for r in rows]

    def post_mppt_batch(self, records: List[mpptRealtimeCreate]):
        if not records: return
        values = [(r.project_id, r.inverter_id, r.mppt_index, r.string_on_mppt, r.V_mppt, r.I_mppt, r.P_mppt, r.Max_I, r.Max_V, r.Max_P, r.created_at) for r in records]
        with self._connect() as conn:
            conn.executemany("INSERT INTO mppt_realtime (project_id, inverter_id, mppt_index, string_on_mppt, V_mppt, I_mppt, P_mppt, Max_I, Max_V, Max_P, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", values)

    # --- String Realtime API ---
    def get_latest_string_batch(self, inverter_id: int) -> List[stringRealtimeResponse]:
        """Lấy danh sách điểm String mới nhất của 1 inverter từ Disk (dùng khi seed)."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM string_realtime
                WHERE inverter_id = ?
                AND created_at = (
                    SELECT MAX(created_at) FROM string_realtime WHERE inverter_id = ?
                )
            """, (inverter_id, inverter_id)).fetchall()
            return [to_dataclass(stringRealtimeResponse, r) for r in rows]

    def post_string_batch(self, records: List[stringRealtimeCreate]):
        if not records: return
        values = [(r.project_id, r.inverter_id, r.mppt_id, r.string_id, r.I_string, r.max_I, r.created_at) for r in records]
        with self._connect() as conn:
            conn.executemany("INSERT INTO string_realtime (project_id, inverter_id, mppt_id, string_id, I_string, max_I, created_at) VALUES (?,?,?,?,?,?,?)", values)

    # --- Project Realtime API ---
    def post_project_realtime(self, data: ProjectRealtimeCreate):
        d = asdict(data)
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO project_realtime (
                    project_id, Temp_C, P_ac, P_dc, E_daily, delta_E_monthly, E_monthly, E_total, severity, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (d["project_id"], d["Temp_C"], d["P_ac"], d["P_dc"], d["E_daily"], d["delta_E_monthly"], d["E_monthly"], d["E_total"], d["severity"], d["created_at"]))

    def get_latest_project_realtime(self, project_id: int) -> Optional[ProjectRealtimeResponse]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM project_realtime WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id,)
            ).fetchone()
            return to_dataclass(ProjectRealtimeResponse, row)

    def get_project_realtime_range(self, project_id: int, start: str, end: str) -> List[ProjectRealtimeResponse]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM project_realtime WHERE project_id = ? AND created_at BETWEEN ? AND ? ORDER BY created_at ASC",
                (project_id, start, end)
            ).fetchall()
            return [to_dataclass(ProjectRealtimeResponse, r) for r in rows]

    def get_inverter_ac_range(self, inverter_id: int, start: str, end: str) -> List[InverterACRealtimeResponse]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM inverter_ac_realtime WHERE inverter_id = ? AND created_at BETWEEN ? AND ? ORDER BY created_at ASC",
                (inverter_id, start, end)
            ).fetchall()
            return [to_dataclass(InverterACRealtimeResponse, r) for r in rows]
