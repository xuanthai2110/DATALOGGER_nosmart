import sqlite3
from typing import Optional, Dict, List
from dataclasses import asdict

from schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from schemas.inverter import InverterCreate, InverterResponse, InverterUpdate
from schemas.user import UserCreate, UserResponse
from schemas.realtime import (
    ProjectRealtimeCreate, ProjectRealtimeResponse,
    InverterACRealtimeCreate, InverterACRealtimeResponse,
    InverterErrorCreate, InverterErrorResponse,
    mpptRealtimeCreate, mpptRealtimeResponse,
    stringRealtimeCreate, stringRealtimeResponse
)
from schemas.comm import CommConfig

from dataclasses import asdict, fields

def to_dataclass(cls, row):
    if row is None: return None
    d = dict(row)
    # Filter only fields present in dataclass
    cls_fields = {f.name for f in fields(cls)}
    filtered = {k: v for k, v in d.items() if k in cls_fields}
    return cls(**filtered)

class MetadataDB:
    def __init__(self, db_path: str = "metadata.db"):
        self.db_path = db_path
        self._create_tables()

    # =========================================================
    # INTERNAL
    # =========================================================

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _create_tables(self):
        with self._connect() as conn:
            cursor = conn.cursor()

            # ==========================
            # PROJECT TABLE
            # ==========================
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

            # ==========================
            # INVERTER TABLE
            # ==========================
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
                capacity_kw REAL,
                rate_dc_kwp REAL,
                rate_ac_kw REAL,
                is_active BOOLEAN DEFAULT 1,
                replaced_by_id INTEGER,
                usage_start_at TEXT,
                usage_end_at TEXT,
                slave_id INTEGER,
                project_id INTEGER,
                server_id INTEGER,
                server_request_id INTEGER,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (replaced_by_id) REFERENCES inverters(id)
            );
            """)

            # ==========================
            # USER TABLE
            # ==========================
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

            # ==========================
            # COMM CONFIG TABLE
            # ==========================
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

            # Indexes
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inverter_project
            ON inverters(project_id);
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inverter_serial
            ON inverters(serial_number);
            """)

    # =========================================================
    # PROJECT API
    # =========================================================

    def post_project(self, data: ProjectCreate) -> int:
        data_dict = asdict(data)
        with self._connect() as conn:
            # Generate next project_index
            row = conn.execute("SELECT MAX(project_index) as max_idx FROM projects").fetchone()
            next_idx = (row["max_idx"] or 0) + 1 if row else 1
            if data_dict.get("project_index") is not None:
                next_idx = data_dict["project_index"]
                
            cursor = conn.execute("""
                INSERT INTO projects (
                    project_index, elec_meter_no, elec_price_per_kwh, name,
                    location, lat, lon,
                    capacity_kwp, ac_capacity_kw, inverter_count, server_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                next_idx,
                data_dict.get("elec_meter_no"),
                data_dict.get("elec_price_per_kwh"),
                data_dict.get("name"),
                data_dict.get("location"),
                data_dict.get("lat"),
                data_dict.get("lon"),
                data_dict.get("capacity_kwp"),
                data_dict.get("ac_capacity_kw"),
                data_dict.get("inverter_count"),
                data_dict.get("server_id")
            ))
            return cursor.lastrowid

    def get_project_first(self) -> Optional[ProjectResponse]:
        """Lấy project đầu tiên trong DB (giả định datalogger chỉ quản lý 1 project local)"""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM projects LIMIT 1").fetchone()
            return to_dataclass(ProjectResponse, row)

    def post_project_with_id(self, data: ProjectCreate, server_id: int) -> int:
        data_dict = asdict(data)
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(project_index) as max_idx FROM projects").fetchone()
            next_idx = (row["max_idx"] or 0) + 1 if row else 1
            if data_dict.get("project_index") is not None:
                next_idx = data_dict["project_index"]
                
            conn.execute("""
                INSERT INTO projects (
                    id, project_index, elec_meter_no, elec_price_per_kwh, name,
                    location, lat, lon,
                    capacity_kwp, ac_capacity_kw, inverter_count,
                    server_id, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved')
            """, (
                server_id,
                next_idx,
                data_dict.get("elec_meter_no"),
                data_dict.get("elec_price_per_kwh"),
                data_dict.get("name"),
                data_dict.get("location"),
                data_dict.get("lat"),
                data_dict.get("lon"),
                data_dict.get("capacity_kwp"),
                data_dict.get("ac_capacity_kw"),
                data_dict.get("inverter_count"),
                server_id
            ))
            return server_id


    def get_project(self, project_id: int) -> Optional[ProjectResponse]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id=?",
                (project_id,)
            ).fetchone()
            return to_dataclass(ProjectResponse, row)

    # =========================================================
    # COMM CONFIG API
    # =========================================================

    def get_all_comm_configs(self) -> List[CommConfig]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM comm_config").fetchall()
            return [to_dataclass(CommConfig, r) for r in rows]

    def get_comm_config(self, config_id: int) -> Optional[CommConfig]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM comm_config WHERE id=?", (config_id,)).fetchone()
            return to_dataclass(CommConfig, row)

    def post_comm_config(self, config: CommConfig) -> int:
        data_dict = asdict(config)
        with self._connect() as conn:
            cursor = conn.execute("""
                INSERT INTO comm_config (
                    driver, comm_type, host, port, com_port, 
                    baudrate, databits, parity, stopbits, timeout, 
                    slave_id_start, slave_id_end
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                data_dict["driver"], data_dict["comm_type"], data_dict["host"],
                data_dict["port"], data_dict["com_port"], data_dict["baudrate"],
                data_dict["databits"], data_dict["parity"], data_dict["stopbits"],
                data_dict["timeout"], data_dict["slave_id_start"], data_dict["slave_id_end"]
            ))
            return cursor.lastrowid

    def patch_comm_config(self, config_id: int, data: dict):
        # We don't filter schemas here as we expect flat dict matching CommConfig
        if not data:
            return
        
        # Filter only valid fields
        from schemas.comm import CommConfig as SchemaClass
        valid_fields = {f.name for f in fields(SchemaClass)}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields and k != "id"}
        
        if not filtered_data:
            return

        set_clause = ", ".join([f"{k}=?" for k in filtered_data.keys()])
        params = list(filtered_data.values()) + [config_id]
        
        with self._connect() as conn:
            conn.execute(f"UPDATE comm_config SET {set_clause} WHERE id=?", params)

    def delete_comm_config(self, config_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM comm_config WHERE id=?", (config_id,))

    def reset_comm_configs(self):
        """Clears all comm configs and resets AUTOINCREMENT sequence."""
        with self._connect() as conn:
            conn.execute("DELETE FROM comm_config")
            conn.execute("DELETE FROM sqlite_sequence WHERE name='comm_config'")

    def upsert_comm_config(self, config: CommConfig):
        """Legacy method for backward compat - defaults to ID=1 if possible or adds new"""
        existing = self.get_comm_config(1)
        if existing:
            self.patch_comm_config(1, asdict(config))
        else:
            self.post_comm_config(config)

    # =========================================================
    # USER MANAGEMENT
    # =========================================================

    def create_user(self, user: UserCreate, hashed_password: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute("""
                INSERT INTO users (username, hashed_password, email, fullname, phone, role)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user.username, hashed_password, user.email, user.fullname, user.phone, user.role))
            return cursor.lastrowid

    def get_user_by_username(self, username: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            return dict(row) if row else None

    def list_users(self) -> List[UserResponse]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, username, email, fullname, phone, role, created_at FROM users").fetchall()
            return [UserResponse(**dict(r)) for r in rows]

    def get_projects(self) -> List[ProjectResponse]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY id DESC"
            ).fetchall()
            return [to_dataclass(ProjectResponse, r) for r in rows]

    def get_all_projects(self) -> List[ProjectResponse]:
        """Alias cho get_projects"""
        return self.get_projects()

    def upsert_project(self, data: ProjectCreate, project_id: Optional[int] = None) -> ProjectResponse:
        """Thêm mới hoặc cập nhật project dựa trên ID hoặc Name."""
        
        if project_id:
            existing = self.get_project(project_id)
            if existing:
                self.patch_project(project_id, ProjectUpdate(id=project_id, **asdict(data)))
                return self.get_project(project_id)

        # Thử tìm theo name để tránh trùng lặp
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM projects WHERE name=?", (data.name,)).fetchone()
            if row:
                pid = row['id']
                self.patch_project(pid, ProjectUpdate(id=pid, **asdict(data)))
                return self.get_project(pid)
            else:
                pid = self.post_project(data)
                return self.get_project(pid)

    def patch_project(self, project_id: int, data: ProjectUpdate):
        data_dict = {k: v for k, v in asdict(data).items() if v is not None and k != "id"}
        if not data_dict:
            return

        fields = ", ".join([f"{k}=?" for k in data_dict.keys()])
        values = list(data_dict.values())
        values.append(project_id)

        with self._connect() as conn:
            conn.execute(
                f"UPDATE projects SET {fields} WHERE id=?",
                values
            )

    def update_project_sync(self, project_id: int, server_id: Optional[int] = None, 
                            server_request_id: Optional[int] = None, status: str = 'pending'):
        """Cập nhật các trường sync cho project"""
        with self._connect() as conn:
            if server_id is not None:
                conn.execute("UPDATE projects SET server_id=?, sync_status=? WHERE id=?", (server_id, status, project_id))
            elif server_request_id is not None:
                conn.execute("UPDATE projects SET server_request_id=?, sync_status=? WHERE id=?", (server_request_id, status, project_id))
            else:
                conn.execute("UPDATE projects SET sync_status=? WHERE id=?", (status, project_id))

    def delete_project(self, project_id: int):
        try:
            with self._connect() as conn:
                # Delete related inverters first due to FK constraints
                cursor1 = conn.execute("DELETE FROM inverters WHERE project_id=?", (project_id,))
                print(f"Deleted {cursor1.rowcount} inverters for project {project_id}")
                # Delete the project
                cursor2 = conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
                print(f"Deleted project {project_id} (rowcount: {cursor2.rowcount})")
                conn.commit()
                print(f"Committed deletion of project {project_id}")
        except Exception as e:
            print(f"Error in delete_project: {e}")
            raise e

    # =========================================================
    # INVERTER API
    # =========================================================

    def upsert_inverter(self, data: InverterCreate) -> int:
        """Thêm mới hoặc cập nhật inverter dựa trên serial_number"""
        existing = self.get_inverter_by_serial(data.serial_number)
        if existing:
            self.patch_inverter(existing.id, InverterUpdate(**asdict(data)))
            return existing.id
        else:
            return self.post_inverter(data)

    def post_inverter(self, data: InverterCreate) -> int:
        data_dict = asdict(data)
        with self._connect() as conn:
            # Generate next inverter_index for the given project_id
            row = conn.execute("SELECT MAX(inverter_index) as max_idx FROM inverters WHERE project_id=?", (data.project_id,)).fetchone()
            next_idx = (row["max_idx"] or 0) + 1 if row else 1
            if data_dict.get("inverter_index") is not None:
                next_idx = data_dict["inverter_index"]

            cursor = conn.execute("""
                INSERT INTO inverters (
                    project_id, inverter_index, serial_number, brand, model,
                    firmware_version, phase_count, mppt_count,
                    string_count, capacity_kw, rate_dc_kwp, rate_ac_kw,
                    is_active, replaced_by_id,
                    usage_start_at, usage_end_at, slave_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data_dict.get("project_id"),
                next_idx,
                data_dict.get("serial_number"),
                data_dict.get("brand"),
                data_dict.get("model"),
                data_dict.get("firmware_version"),
                data_dict.get("phase_count"),
                data_dict.get("mppt_count"),
                data_dict.get("string_count"),
                data_dict.get("capacity_kw"),
                data_dict.get("rate_dc_kwp"),
                data_dict.get("rate_ac_kw"),
                data_dict.get("is_active", True),
                data_dict.get("replaced_by_id"),
                data_dict.get("usage_start_at"),
                data_dict.get("usage_end_at"),
                data_dict.get("slave_id")
            ))
            return cursor.lastrowid

    def post_inverter_with_id(self, data: InverterCreate, server_id: int) -> int:
        data_dict = asdict(data)
        with self._connect() as conn:
            # Generate next inverter_index for the given project_id
            row = conn.execute("SELECT MAX(inverter_index) as max_idx FROM inverters WHERE project_id=?", (data.project_id,)).fetchone()
            next_idx = (row["max_idx"] or 0) + 1 if row else 1
            if data_dict.get("inverter_index") is not None:
                next_idx = data_dict["inverter_index"]

            conn.execute("""
                INSERT INTO inverters (
                    id, project_id, inverter_index, serial_number, brand, model,
                    firmware_version, phase_count, mppt_count,
                    string_count, capacity_kw, rate_dc_kwp, rate_ac_kw,
                    is_active, replaced_by_id,
                    usage_start_at, usage_end_at, slave_id,
                    server_id, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved')
            """, (
                server_id,
                data_dict.get("project_id"),
                next_idx,
                data_dict.get("serial_number"),
                data_dict.get("brand"),
                data_dict.get("model"),
                data_dict.get("firmware_version"),
                data_dict.get("phase_count"),
                data_dict.get("mppt_count"),
                data_dict.get("string_count"),
                data_dict.get("capacity_kw"),
                data_dict.get("rate_dc_kwp"),
                data_dict.get("rate_ac_kw"),
                data_dict.get("is_active", True),
                data_dict.get("replaced_by_id"),
                data_dict.get("usage_start_at"),
                data_dict.get("usage_end_at"),
                data_dict.get("slave_id"),
                server_id
            ))
            return server_id


    def get_inverter(self, inverter_id: int) -> Optional[InverterResponse]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM inverters WHERE id=?",
                (inverter_id,)
            ).fetchone()
            return to_dataclass(InverterResponse, row)

    def get_inverter_by_serial(self, serial: str) -> Optional[InverterResponse]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM inverters WHERE serial_number=?",
                (serial,)
            ).fetchone()
            return to_dataclass(InverterResponse, row)

    def get_inverters_by_project(self, project_id: int) -> List[InverterResponse]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM inverters
                WHERE project_id=?
                ORDER BY inverter_index ASC
            """, (project_id,)).fetchall()
            return [to_dataclass(InverterResponse, r) for r in rows]

    def get_all_inverters(self) -> List[InverterResponse]:
        """Lấy tất cả inverters trong DB"""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM inverters").fetchall()
            return [to_dataclass(InverterResponse, r) for r in rows]

    def patch_inverter(self, inverter_id: int, data: InverterUpdate):
        data_dict = {k: v for k, v in asdict(data).items() if v is not None}
        if not data_dict:
            return

        fields = ", ".join([f"{k}=?" for k in data_dict.keys()])
        values = list(data_dict.values()) + [inverter_id]

        with self._connect() as conn:
            conn.execute(
                f"UPDATE inverters SET {fields} WHERE id=?",
                values
            )


    def update_inverter_sync(self, inverter_id: int, server_id: Optional[int] = None, 
                             server_request_id: Optional[int] = None, status: str = 'pending'):
        """Cập nhật các trường sync cho inverter"""
        with self._connect() as conn:
            if server_id is not None:
                conn.execute("UPDATE inverters SET server_id=?, sync_status=? WHERE id=?", (server_id, status, inverter_id))
            elif server_request_id is not None:
                conn.execute("UPDATE inverters SET server_request_id=?, sync_status=? WHERE id=?", (server_request_id, status, inverter_id))
            else:
                conn.execute("UPDATE inverters SET sync_status=? WHERE id=?", (status, inverter_id))

    def delete_inverter(self, inverter_id: int):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM inverters WHERE id=?",
                (inverter_id,)
            )

    def mark_inverter_inactive(self, inverter_id: int, replaced_by_id: int):
        """Đánh dấu inverter đã bị thay thế"""
        with self._connect() as conn:
            conn.execute(
                "UPDATE inverters SET is_active=0, replaced_by_id=?, usage_end_at=CURRENT_TIMESTAMP WHERE id=?",
                (replaced_by_id, inverter_id)
            )

class RealtimeDB:
    def __init__(self, db_path: str = "realtime.db"):
        self.db_path = db_path
        self._create_tables()

    # =========================================================
    # INTERNAL
    # =========================================================

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _create_tables(self):
        with self._connect() as conn:
            cursor = conn.cursor()

            # =====================================================
            # PROJECT REALTIME
            # =====================================================
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_realtime (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                Temp_C REAL,
                P_ac REAL,
                P_dc REAL,
                E_daily REAL,
                E_monthly REAL,
                E_total REAL,
                severity TEXT,
                created_at TEXT
            );
            """)

            # =====================================================
            # INVERTER AC REALTIME
            # =====================================================
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS inverter_ac_realtime (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                inverter_id INTEGER,
                IR REAL,
                Temp_C REAL,
                P_ac REAL,
                Q_ac REAL,
                V_a REAL,
                V_b REAL,
                V_c REAL,
                I_a REAL,
                I_b REAL,
                I_c REAL,
                PF REAL,
                H REAL,
                E_daily REAL,
                E_monthly REAL,
                E_total REAL,
                created_at TEXT
            );
            """)

            # =====================================================
            # MPPT REALTIME
            # =====================================================
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS mppt_realtime (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                inverter_id INTEGER,
                mppt_index INTEGER,
                string_on_mppt INTEGER,
                V_mppt REAL,
                I_mppt REAL,
                P_mppt REAL,
                Max_I REAL,
                Max_V REAL,
                Max_P REAL,
                created_at TEXT
            );
            """)

            # =====================================================
            # STRING REALTIME
            # =====================================================
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS string_realtime (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                inverter_id INTEGER,
                mppt_id INTEGER,
                string_id INTEGER,
                I_string REAL,  
                max_I REAL,
                created_at TEXT
            );
            """)

            # =====================================================
            # INVERTER ERRORS
            # =====================================================
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS inverter_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                inverter_id INTEGER,
                fault_code INTEGER,
                fault_description TEXT,
                repair_instruction TEXT,
                severity TEXT,
                created_at TEXT
            );
            """)

            # =====================================================
            # INDEXES (CRITICAL FOR PERFORMANCE)
            # =====================================================
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_rt_time
            ON project_realtime(project_id, created_at);
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inv_ac_time
            ON inverter_ac_realtime(project_id, inverter_id, created_at);
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_mppt_time
            ON mppt_realtime(project_id, inverter_id, mppt_index, created_at);
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_string_time
            ON string_realtime(project_id, inverter_id, mppt_id, string_id, created_at);
            """)

    # =========================================================
    # PROJECT REALTIME API
    # =========================================================

    def post_project_realtime(self, data: ProjectRealtimeCreate):
        data_dict = asdict(data)
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO project_realtime (
                    project_id, Temp_C, P_ac, P_dc,
                    E_daily, E_monthly, E_total,
                    severity, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data_dict["project_id"],
                data_dict["Temp_C"],
                data_dict["P_ac"],
                data_dict["P_dc"],
                data_dict["E_daily"],
                data_dict["E_monthly"],
                data_dict["E_total"],
                data_dict["severity"],
                data_dict["created_at"]
            ))

    def get_latest_project_realtime(self, project_id: int) -> Optional[ProjectRealtimeResponse]:
        """Lấy dữ liệu realtime mới nhất của project"""
        with self._connect() as conn:
            row = conn.execute("""
                SELECT * FROM project_realtime
                WHERE project_id=?
                ORDER BY created_at DESC
                LIMIT 1
            """, (project_id,)).fetchone()
            return ProjectRealtimeResponse(**dict(row)) if row else None

    def get_project_realtime_range(
        self,
        project_id: int,
        start: str,
        end: str
    ) -> List[ProjectRealtimeResponse]:

        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM project_realtime
                WHERE project_id=?
                AND created_at BETWEEN ? AND ?
                ORDER BY created_at ASC
            """, (project_id, start, end)).fetchall()

            return [ProjectRealtimeResponse(**dict(r)) for r in rows]

    def delete_project_realtime_before(self, before_time: str):
        with self._connect() as conn:
            conn.execute("""
                DELETE FROM project_realtime
                WHERE created_at < ?
            """, (before_time,))

    # =========================================================
    # INVERTER AC REALTIME API
    # =========================================================

    def post_inverter_ac_batch(self, records: List[InverterACRealtimeCreate]):
        if not records:
            return

        values = [
            (
                r.project_id,
                r.inverter_id,
                r.IR,
                r.Temp_C,
                r.P_ac,
                r.Q_ac,
                r.V_a,
                r.V_b,
                r.V_c,
                r.I_a,
                r.I_b,
                r.I_c,
                r.PF,
                r.H,
                r.E_daily,
                r.E_monthly,
                r.E_total,
                r.created_at
            )
            for r in records
        ]

        with self._connect() as conn:
            conn.executemany("""
                INSERT INTO inverter_ac_realtime (
                    project_id, inverter_id, IR, Temp_C, P_ac, Q_ac,
                    V_a, V_b, V_c,
                    I_a, I_b, I_c,
                    PF, H,
                    E_daily, E_monthly, E_total,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, values)

    def get_inverter_ac_range(
        self,
        inverter_id: int,
        start: str,
        end: str
    ) -> List[InverterACRealtimeResponse]:

        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM inverter_ac_realtime
                WHERE inverter_id=?
                AND created_at BETWEEN ? AND ?
                ORDER BY created_at ASC
            """, (inverter_id, start, end)).fetchall()

            return [InverterACRealtimeResponse(**dict(r)) for r in rows]

    def get_latest_inverter_ac_realtime(self, inverter_id: int) -> Optional[InverterACRealtimeResponse]:
        """Lấy dữ liệu AC mới nhất của một inverter."""
        with self._connect() as conn:
            row = conn.execute("""
                SELECT * FROM inverter_ac_realtime
                WHERE inverter_id=?
                ORDER BY created_at DESC
                LIMIT 1
            """, (inverter_id,)).fetchone()
            return to_dataclass(InverterACRealtimeResponse, row)

    def get_latest_mppt_batch(self, inverter_id: int) -> List[mpptRealtimeResponse]:
        """Lấy batch MPPT mới nhất của một inverter."""
        with self._connect() as conn:
            # Tìm timestamp mới nhất
            row_ts = conn.execute("""
                SELECT created_at FROM mppt_realtime
                WHERE inverter_id=?
                ORDER BY created_at DESC LIMIT 1
            """, (inverter_id,)).fetchone()
            if not row_ts: return []
            
            ts = row_ts["created_at"]
            rows = conn.execute("""
                SELECT * FROM mppt_realtime
                WHERE inverter_id=? AND created_at=?
            """, (inverter_id, ts)).fetchall()
            return [to_dataclass(mpptRealtimeResponse, r) for r in rows]

    def get_latest_string_batch(self, inverter_id: int) -> List[stringRealtimeResponse]:
        """Lấy batch String mới nhất của một inverter."""
        with self._connect() as conn:
            row_ts = conn.execute("""
                SELECT created_at FROM string_realtime
                WHERE inverter_id=?
                ORDER BY created_at DESC LIMIT 1
            """, (inverter_id,)).fetchone()
            if not row_ts: return []
            
            ts = row_ts["created_at"]
            rows = conn.execute("""
                SELECT * FROM string_realtime
                WHERE inverter_id=? AND created_at=?
            """, (inverter_id, ts)).fetchall()
            return [to_dataclass(stringRealtimeResponse, r) for r in rows]

    # =========================================================
    # MPPT API
    # =========================================================

    def post_mppt(self, data: mpptRealtimeCreate) -> int:
        data_dict = asdict(data)
        with self._connect() as conn:
            cursor = conn.execute("""
                INSERT INTO mppt_realtime (
                    project_id, inverter_id, mppt_index, string_on_mppt,
                    V_mppt, I_mppt, P_mppt,
                    Max_I, Max_V, Max_P,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data_dict["project_id"],
                data_dict["inverter_id"],
                data_dict["mppt_index"],
                data_dict["string_on_mppt"],
                data_dict["V_mppt"],
                data_dict["I_mppt"],
                data_dict["P_mppt"],
                data_dict["Max_I"],
                data_dict["Max_V"],
                data_dict["Max_P"],
                data_dict["created_at"]
            ))
            return cursor.lastrowid

    def post_mppt_batch(self, records: List[mpptRealtimeCreate]):
        if not records:
            return
        values = [
            (
                r.project_id,
                r.inverter_id,
                r.mppt_index,
                getattr(r, "string_on_mppt", 0),
                r.V_mppt,
                r.I_mppt,
                r.P_mppt,
                r.Max_I,
                r.Max_V,
                r.Max_P,
                r.created_at
            )
            for r in records
        ]
        with self._connect() as conn:
            conn.executemany("""
                INSERT INTO mppt_realtime (
                    project_id, inverter_id, mppt_index, string_on_mppt,
                    V_mppt, I_mppt, P_mppt,
                    Max_I, Max_V, Max_P,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, values)

    # =========================================================
    # STRING API
    # =========================================================

    def post_string_batch(self, records: List[stringRealtimeCreate]):
        if not records:
            return

        values = [
            (
                r.project_id,
                r.inverter_id,
                r.mppt_id,
                r.string_id,
                r.I_string,
                r.max_I,
                r.created_at
            )
            for r in records
        ]

        with self._connect() as conn:
            conn.executemany("""
                INSERT INTO string_realtime (
                    project_id, inverter_id, mppt_id, string_id,
                    I_string, max_I,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, values)


    # =========================================================
    # ERROR API
    # =========================================================

    def post_inverter_error(self, data: InverterErrorCreate):
        data_dict = asdict(data)
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO inverter_errors (
                    project_id, inverter_id, fault_code,
                    fault_description, repair_instruction,
                    severity, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                data_dict["project_id"],
                data_dict["inverter_id"],
                data_dict["fault_code"],
                data_dict["fault_description"],
                data_dict["repair_instruction"],
                data_dict["severity"],
                data_dict["created_at"]
            ))

    def get_inverter_errors(
        self,
        inverter_id: int,
        start: Optional[str] = None,
        end: Optional[str] = None
    ) -> List[InverterErrorResponse]:

        query = "SELECT * FROM inverter_errors WHERE inverter_id=?"
        params = [inverter_id]

        if start and end:
            query += " AND created_at BETWEEN ? AND ?"
            params.extend([start, end])

        query += " ORDER BY created_at DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [to_dataclass(InverterErrorResponse, r) for r in rows]

    def delete_errors_before(self, before_time: str):
        with self._connect() as conn:
            conn.execute("""
                DELETE FROM inverter_errors
                WHERE created_at < ?
            """, (before_time,))

    def delete_before(self, before_time: str):
        """Xoá toàn bộ dữ liệu realtime cũ hơn before_time"""
        with self._connect() as conn:
            tables = [
                "project_realtime",
                "inverter_ac_realtime",
                "mppt_realtime",
                "string_realtime",
                "inverter_errors"
            ]
            for table in tables:
                conn.execute(f"DELETE FROM {table} WHERE created_at < ?", (before_time,))

    def delete_inverter_data(self, inverter_id: int):
        """Xoá toàn bộ dữ liệu realtime của một inverter cụ thể"""
        with self._connect() as conn:
            tables = [
                "inverter_ac_realtime",
                "mppt_realtime",
                "string_realtime",
                "inverter_errors"
            ]
            for table in tables:
                conn.execute(f"DELETE FROM {table} WHERE inverter_id = ?", (inverter_id,))