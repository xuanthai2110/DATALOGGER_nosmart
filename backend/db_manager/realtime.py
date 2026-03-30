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
                data_json TEXT,
                created_at TEXT
            );
            """)
            # Project Realtime
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_realtime (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER, Temp_C REAL, P_ac REAL, P_dc REAL,
                E_daily REAL, denta_E_monthly REAL, E_monthly REAL, E_total REAL,
                severity TEXT, created_at TEXT
            );
            """)
            # Inverter AC Realtime
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS inverter_ac_realtime (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER, inverter_id INTEGER,
                IR REAL, Temp_C REAL, P_ac REAL, Q_ac REAL,
                V_a REAL, V_b REAL, V_c REAL, I_a REAL, I_b REAL, I_c REAL,
                PF REAL, H REAL, E_daily REAL, denta_E_monthly REAL, E_monthly REAL, E_total REAL,
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
            # MPPT & String Realtime tables... (giản lược cho ngắn gọn)
            cursor.execute("CREATE TABLE IF NOT EXISTS mppt_realtime (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER, inverter_id INTEGER, mppt_index INTEGER, string_on_mppt INTEGER, V_mppt REAL, I_mppt REAL, P_mppt REAL, Max_I REAL, Max_V REAL, Max_P REAL, created_at TEXT);")
            cursor.execute("CREATE TABLE IF NOT EXISTS string_realtime (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER, inverter_id INTEGER, mppt_id INTEGER, string_id INTEGER, I_string REAL, max_I REAL, created_at TEXT);")

    # --- Outbox API ---
    def post_to_outbox(self, project_id: int, data: dict):
        from datetime import datetime
        now_str = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute("INSERT INTO uploader_outbox (project_id, data_json, created_at) VALUES (?, ?, ?)",
                         (project_id, json.dumps(data), now_str))

    def get_all_outbox(self) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, project_id, data_json, created_at FROM uploader_outbox").fetchall()
            result = []
            for r in rows:
                d = json.loads(r["data_json"])
                d["id"] = r["id"]
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
        values = [(r.project_id, r.inverter_id, r.IR, r.Temp_C, r.P_ac, r.Q_ac, r.V_a, r.V_b, r.V_c, r.I_a, r.I_b, r.I_c, r.PF, r.H, r.E_daily, r.E_monthly, r.E_total, r.created_at) for r in records]
        with self._connect() as conn:
            conn.executemany("INSERT INTO inverter_ac_realtime (project_id, inverter_id, IR, Temp_C, P_ac, Q_ac, V_a, V_b, V_c, I_a, I_b, I_c, PF, H, E_daily, E_monthly, E_total, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)

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
