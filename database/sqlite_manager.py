import sqlite3
from typing import Optional, Dict, List
from dataclasses import asdict

from schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from schemas.inverter import InverterCreate, InverterResponse, InverterUpdate
from schemas.realtime import (
    ProjectRealtimeCreate, ProjectRealtimeResponse,
    InverterACRealtimeCreate, InverterACRealtimeResponse,
    InverterErrorCreate, InverterErrorResponse,
    mpptRealtimeCreate, mpptRealtimeResponse,
    stringRealtimeCreate, stringRealtimeResponse
)

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
                elec_meter_no TEXT,
                elec_price_per_kwh REAL,
                name TEXT,
                location TEXT,
                lat REAL,
                lon REAL,
                capacity_kwp REAL,
                ac_capacity_kw REAL,
                inverter_count INTEGER,
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
                project_id INTEGER,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (replaced_by_id) REFERENCES inverters(id)
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
            cursor = conn.execute("""
                INSERT INTO projects (
                    elec_meter_no, elec_price_per_kwh, name,
                    location, lat, lon,
                    capacity_kwp, ac_capacity_kw, inverter_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data_dict.get("elec_meter_no"),
                data_dict.get("elec_price_per_kwh"),
                data_dict.get("name"),
                data_dict.get("location"),
                data_dict.get("lat"),
                data_dict.get("lon"),
                data_dict.get("capacity_kwp"),
                data_dict.get("ac_capacity_kw"),
                data_dict.get("inverter_count"),
            ))
            return cursor.lastrowid

    def get_project_first(self) -> Optional[ProjectResponse]:
        """Lấy project đầu tiên trong DB (giả định datalogger chỉ quản lý 1 project local)"""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM projects LIMIT 1").fetchone()
            return ProjectResponse(**dict(row)) if row else None

    def post_project_with_id(self, data: ProjectCreate, server_id: int) -> int:
        data_dict = asdict(data)
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO projects (
                    id, elec_meter_no, elec_price_per_kwh, name,
                    location, lat, lon,
                    capacity_kwp, ac_capacity_kw, inverter_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                server_id,
                data_dict.get("elec_meter_no"),
                data_dict.get("elec_price_per_kwh"),
                data_dict.get("name"),
                data_dict.get("location"),
                data_dict.get("lat"),
                data_dict.get("lon"),
                data_dict.get("capacity_kwp"),
                data_dict.get("ac_capacity_kw"),
                data_dict.get("inverter_count"),
            ))
            return server_id


    def get_project(self, project_id: int) -> Optional[ProjectResponse]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id=?",
                (project_id,)
            ).fetchone()
            return ProjectResponse(**dict(row)) if row else None

    def get_projects(self) -> List[ProjectResponse]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY id DESC"
            ).fetchall()
            return [ProjectResponse(**dict(r)) for r in rows]

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

    def delete_project(self, project_id: int):
        with self._connect() as conn:
            # Delete related inverters first due to FK constraints
            conn.execute("DELETE FROM inverters WHERE project_id=?", (project_id,))
            # Delete the project
            conn.execute("DELETE FROM projects WHERE id=?", (project_id,))

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
            cursor = conn.execute("""
                INSERT INTO inverters (
                    project_id, inverter_index, serial_number, brand, model,
                    firmware_version, phase_count, mppt_count,
                    string_count, capacity_kw, rate_dc_kwp, rate_ac_kw,
                    is_active, replaced_by_id,
                    usage_start_at, usage_end_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data_dict.get("project_id"),
                data_dict.get("inverter_index"),
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
                data_dict.get("usage_end_at")
            ))
            return cursor.lastrowid

    def post_inverter_with_id(self, data: InverterCreate, server_id: int) -> int:
        data_dict = asdict(data)
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO inverters (
                    id, project_id, inverter_index, serial_number, brand, model,
                    firmware_version, phase_count, mppt_count,
                    string_count, capacity_kw, rate_dc_kwp, rate_ac_kw,
                    is_active, replaced_by_id,
                    usage_start_at, usage_end_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                server_id,
                data_dict.get("project_id"),
                data_dict.get("inverter_index"),
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
                data_dict.get("usage_end_at")
            ))
            return server_id


    def get_inverter(self, inverter_id: int) -> Optional[InverterResponse]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM inverters WHERE id=?",
                (inverter_id,)
            ).fetchone()
            return InverterResponse(**dict(row)) if row else None

    def get_inverter_by_serial(self, serial: str) -> Optional[InverterResponse]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM inverters WHERE serial_number=?",
                (serial,)
            ).fetchone()
            return InverterResponse(**dict(row)) if row else None

    def get_inverters_by_project(self, project_id: int) -> List[InverterResponse]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM inverters
                WHERE project_id=?
                ORDER BY inverter_index ASC
            """, (project_id,)).fetchall()
            return [InverterResponse(**dict(r)) for r in rows]

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


    def delete_inverter(self, inverter_id: int):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM inverters WHERE id=?",
                (inverter_id,)
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
            return [InverterErrorResponse(**dict(r)) for r in rows]

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