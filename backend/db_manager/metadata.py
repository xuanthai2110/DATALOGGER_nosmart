import sqlite3
import logging
from typing import Optional, Dict, List
from dataclasses import asdict, fields
from .base_db import BaseDB, to_dataclass

from backend.models.project import ProjectCreate, ProjectResponse, ProjectUpdate
from backend.models.inverter import InverterCreate, InverterResponse, InverterUpdate
from backend.models.user import UserCreate, UserResponse
from backend.models.comm import CommConfig

logger = logging.getLogger(__name__)

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
            # Đảm bảo cột sync_status tồn tại (Migration cho hệ thống cũ)
            self._ensure_column(conn, "projects", "sync_status", "sync_status TEXT DEFAULT 'pending'")
            self._ensure_column(conn, "inverters", "sync_status", "sync_status TEXT DEFAULT 'pending'")
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

    def upsert_project(self, data: ProjectCreate, project_id: Optional[int] = None) -> ProjectResponse:
        data_dict = asdict(data)
        with self._connect() as conn:
            cursor = conn.cursor()
            if project_id:
                # Update existing project (ignore None values)
                fields = []
                values = []
                for k, v in data_dict.items():
                    if v is not None:
                        fields.append(f"{k} = ?")
                        values.append(v)
                if not fields:
                    return self.get_project(project_id)
                values.append(project_id)
                cursor.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id=?", tuple(values))
                final_id = project_id
            else:
                # Insert new project
                row = conn.execute("SELECT MAX(project_index) as max_idx FROM projects").fetchone()
                next_idx = (row["max_idx"] or 0) + 1 if row else 1
                if data_dict.get("project_index") is not None:
                    next_idx = data_dict["project_index"]
                
                cursor.execute("""
                    INSERT INTO projects (
                        project_index, elec_meter_no, elec_price_per_kwh, name, location, lat, lon,
                        capacity_kwp, ac_capacity_kw, inverter_count, server_id, server_request_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (next_idx, data_dict.get("elec_meter_no"), data_dict.get("elec_price_per_kwh"),
                      data_dict.get("name"), data_dict.get("location"), data_dict.get("lat"), data_dict.get("lon"),
                      data_dict.get("capacity_kwp"), data_dict.get("ac_capacity_kw"), data_dict.get("inverter_count"),
                      data_dict.get("server_id"), data_dict.get("server_request_id")))
                final_id = cursor.lastrowid
                
            row = conn.execute("SELECT * FROM projects WHERE id=?", (final_id,)).fetchone()
            return to_dataclass(ProjectResponse, row)

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

    def patch_project(self, project_id: int, data: ProjectUpdate):
        data_dict = asdict(data)
        fields = [f"{k} = ?" for k, v in data_dict.items() if v is not None]
        values = [v for v in data_dict.values() if v is not None]
        if not fields: return
        values.append(project_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id=?", tuple(values))

    def update_project_sync(self, project_id: int, server_id: Optional[int] = None, server_request_id: Optional[int] = None, status: str = 'pending'):
        logger.info(f"[MetadataDB] Updating project {project_id} sync status to {status} (server_id={server_id})")
        with self._connect() as conn:
            conn.execute("""
                UPDATE projects 
                SET server_id = COALESCE(?, server_id), 
                    server_request_id = COALESCE(?, server_request_id),
                    sync_status = ? 
                WHERE id = ?
            """, (server_id, server_request_id, status, project_id))

    def get_project_sync_info(self, project_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT server_id, server_request_id, sync_status FROM projects WHERE id=?", (project_id,)).fetchone()
            return dict(row) if row else None

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

    def get_all_inverters(self) -> List[InverterResponse]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM inverters ORDER BY id ASC").fetchall()
            return [to_dataclass(InverterResponse, r) for r in rows]

    def upsert_inverter(self, data: InverterCreate) -> InverterResponse:
        data_dict = asdict(data)
        serial = data_dict.get("serial_number")
        with self._connect() as conn:
            cursor = conn.cursor()
            # Check if exists
            row = conn.execute("SELECT id FROM inverters WHERE serial_number=?", (serial,)).fetchone()
            if row:
                inv_id = row["id"]
                fields = []
                values = []
                for k, v in data_dict.items():
                    if k != "serial_number" and v is not None:
                        fields.append(f"{k} = ?")
                        values.append(v)
                if fields:
                    values.append(inv_id)
                    cursor.execute(f"UPDATE inverters SET {', '.join(fields)} WHERE id=?", tuple(values))
                final_id = inv_id
            else:
                # Insert
                keys = [k for k, v in data_dict.items() if v is not None]
                placeholders = ["?" for _ in keys]
                values = [data_dict[k] for k in keys]
                cursor.execute(f"INSERT INTO inverters ({', '.join(keys)}) VALUES ({', '.join(placeholders)})", tuple(values))
                final_id = cursor.lastrowid
            
            row = conn.execute("SELECT * FROM inverters WHERE id=?", (final_id,)).fetchone()
            return to_dataclass(InverterResponse, row)

    def patch_inverter(self, inverter_id: int, data: InverterUpdate):
        data_dict = asdict(data)
        fields = [f"{k} = ?" for k, v in data_dict.items() if v is not None]
        values = [v for v in data_dict.values() if v is not None]
        if not fields: return
        values.append(inverter_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE inverters SET {', '.join(fields)} WHERE id=?", tuple(values))

    def update_inverter_sync(self, inverter_id: int, server_id: Optional[int] = None, status: str = 'pending'):
        with self._connect() as conn:
            conn.execute("""
                UPDATE inverters 
                SET server_id = COALESCE(?, server_id), 
                    sync_status = ? 
                WHERE id = ?
            """, (server_id, status, inverter_id))

    # --- Comm/Auth API (Rút gọn) ---
    def get_comm_config(self) -> List[CommConfig]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM comm_config").fetchall()
            return [to_dataclass(CommConfig, r) for r in rows]

    def get_comm(self) -> List[CommConfig]:
        """Tương đương get_comm_config."""
        return self.get_comm_config()

    def get_comm_id(self, config_id: int) -> Optional[CommConfig]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM comm_config WHERE id=?", (config_id,)).fetchone()
            return to_dataclass(CommConfig, row)

    def post_comm(self, data: CommConfig) -> int:
        data_dict = asdict(data)
        with self._connect() as conn:
            # Check if any config exists (assume ID=1 for the main config)
            row = conn.execute("SELECT id FROM comm_config LIMIT 1").fetchone()
            if row:
                config_id = row["id"]
                fields = []
                values = []
                for k, v in data_dict.items():
                    if k != "id" and v is not None:
                        fields.append(f"{k} = ?")
                        values.append(v)
                values.append(config_id)
                conn.execute(f"UPDATE comm_config SET {', '.join(fields)} WHERE id=?", tuple(values))
                return config_id
            else:
                cursor = conn.execute("""
                    INSERT INTO comm_config (
                        driver, comm_type, host, port, com_port, baudrate, databits, parity, stopbits, timeout, slave_id_start, slave_id_end
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (data_dict.get("driver"), data_dict.get("comm_type"), data_dict.get("host"), data_dict.get("port"),
                      data_dict.get("com_port"), data_dict.get("baudrate"), data_dict.get("databits"), data_dict.get("parity"),
                      data_dict.get("stopbits"), data_dict.get("timeout"), data_dict.get("slave_id_start"), data_dict.get("slave_id_end")))
                return cursor.lastrowid

    def patch_comm(self, config_id: int, updates: dict):
        with self._connect() as conn:
            fields = []
            values = []
            for k, v in updates.items():
                fields.append(f"{k} = ?")
                values.append(v)
            if not fields: return
            values.append(config_id)
            conn.execute(f"UPDATE comm_config SET {', '.join(fields)} WHERE id=?", tuple(values))

    def delete_comm(self, config_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM comm_config WHERE id=?", (config_id,))

    def reset_comm(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM comm_config")
            conn.execute("DELETE FROM sqlite_sequence WHERE name='comm_config'")

    # --- User API ---
    def get_user_by_name(self, username: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def create_user(self, data: UserCreate) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, hashed_password, email, fullname, phone, role) VALUES (?, ?, ?, ?, ?, ?)",
                (data.username, data.password, data.email, data.fullname, data.phone, data.role)
            )
            return cursor.lastrowid
