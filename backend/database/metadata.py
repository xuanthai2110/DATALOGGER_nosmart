import sqlite3
from typing import Optional, Dict, List
from dataclasses import asdict, fields
from .base_db import BaseDB, to_dataclass

from models.project import ProjectCreate, ProjectResponse, ProjectUpdate
from models.inverter import InverterCreate, InverterResponse, InverterUpdate
from models.user import UserCreate, UserResponse
from models.comm import CommConfig

class MetadataDB(BaseDB):
    """Quản lý cấu hình Project, Inverter, User và Communication."""
    
    def _connect(self):
        conn = super()._connect()
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _create_tables(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            # Project table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_index INTEGER,
                elec_meter_no TEXT,
                elec_price_per_kwh REAL,
                name TEXT,
                location TEXT,
                lat REAL,
                lon REAL,
                capacity_kwp REAL,
                ac_capacity_kw REAL,
                inverter_count INTEGER,
                server_id INTEGER,
                server_request_id INTEGER,
                sync_status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)
            # Inverter table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS inverters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inverter_index INTEGER,
                serial_number TEXT UNIQUE,
                brand TEXT,
                model TEXT,
                firmware_version TEXT,
                phase_count INTEGER,
                mppt_count INTEGER,
                string_count INTEGER,
                strings_per_mppt INTEGER,
                capacity_kw REAL,
                rate_dc_kwp REAL,
                rate_ac_kw REAL,
                is_active BOOLEAN DEFAULT 1,
                replaced_by_id INTEGER,
                usage_start_at TEXT,
                usage_end_at TEXT,
                slave_id INTEGER,
                comm_id INTEGER,
                project_id INTEGER,
                server_id INTEGER,
                server_request_id INTEGER,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (replaced_by_id) REFERENCES inverters(id),
                FOREIGN KEY (comm_id) REFERENCES comm_config(id)
            );
            """)
            # User table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                email TEXT,
                fullname TEXT,
                phone TEXT,
                role TEXT DEFAULT 'user',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)
            # Comm config
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS comm_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                driver TEXT,
                comm_type TEXT,
                host TEXT,
                port INTEGER,
                com_port TEXT,
                baudrate INTEGER,
                databits INTEGER,
                parity TEXT,
                stopbits INTEGER,
                timeout REAL,
                slave_id_start INTEGER,
                slave_id_end INTEGER
            );
            """)
            self._ensure_column(conn, "inverters", "comm_id", "comm_id INTEGER")

    # --- Project API ---
    def get_project(self, project_id: int) -> Optional[ProjectResponse]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            return to_dataclass(ProjectResponse, row)

    def get_projects(self) -> List[ProjectResponse]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
            return [to_dataclass(ProjectResponse, r) for r in rows]

    def post_project(self, data: ProjectCreate) -> int:
        data_dict = asdict(data)
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(project_index) as max_idx FROM projects").fetchone()
            next_idx = (row["max_idx"] or 0) + 1 if row else 1
            if data_dict.get("project_index") is not None:
                next_idx = data_dict["project_index"]
            cursor = conn.execute("""
                INSERT INTO projects (
                    project_index, elec_meter_no, elec_price_per_kwh, name, location, lat, lon,
                    capacity_kwp, ac_capacity_kw, inverter_count, server_id, server_request_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (next_idx, data_dict.get("elec_meter_no"), data_dict.get("elec_price_per_kwh"),
                  data_dict.get("name"), data_dict.get("location"), data_dict.get("lat"), data_dict.get("lon"),
                  data_dict.get("capacity_kwp"), data_dict.get("ac_capacity_kw"), data_dict.get("inverter_count"),
                  data_dict.get("server_id"), data_dict.get("server_request_id")))
            return cursor.lastrowid

    def delete_project(self, project_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM inverters WHERE project_id=?", (project_id,))
            conn.execute("DELETE FROM projects WHERE id=?", (project_id,))

    # --- Inverter API ---
    def get_inverter_by_id(self, inverter_id: int) -> Optional[InverterResponse]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM inverters WHERE id=?", (inverter_id,)).fetchone()
            return to_dataclass(InverterResponse, row)

    def get_inverter_by_serial(self, serial: str) -> Optional[InverterResponse]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM inverters WHERE serial_number=?", (serial,)).fetchone()
            return to_dataclass(InverterResponse, row)

    def get_inverters_by_project(self, project_id: int) -> List[InverterResponse]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM inverters WHERE project_id=? ORDER BY inverter_index ASC", (project_id,)).fetchall()
            return [to_dataclass(InverterResponse, r) for r in rows]

    # --- Comm/Auth API (Rút gọn) ---
    def get_comm_config(self) -> List[CommConfig]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM comm_config").fetchall()
            return [to_dataclass(CommConfig, r) for r in rows]

    def get_user_by_name(self, username: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            return dict(row) if row else None
