import sqlite3
import json
from typing import List, Dict, Optional
from database.base_db import BaseDB

class CacheDB(BaseDB):
    """Quản lý dữ liệu thay đổi nhanh (RAM-based)."""
    
    def _connect(self):
        conn = super()._connect()
        # Tối ưu hóa tối đa cho RAM
        conn.execute("PRAGMA journal_mode=MEMORY;")
        conn.execute("PRAGMA synchronous=OFF;")
        return conn

    def _create_tables(self):
        with self._connect() as conn:
            # AC Cache
            conn.execute("""
            CREATE TABLE IF NOT EXISTS inverter_ac_cache (
                inverter_id INTEGER PRIMARY KEY, project_id INTEGER,
                IR REAL, Temp_C REAL, P_ac REAL, Q_ac REAL,
                V_a REAL, V_b REAL, V_c REAL, I_a REAL, I_b REAL, I_c REAL,
                PF REAL, H REAL, E_daily REAL, E_total REAL,
                delta_E_monthly REAL DEFAULT 0, E_monthly REAL DEFAULT 0, updated_at TEXT
            );
            """)
            # MPPT Cache
            conn.execute("""
            CREATE TABLE IF NOT EXISTS mppt_cache (
                inverter_id INTEGER, mppt_index INTEGER, project_id INTEGER,
                V_mppt REAL, I_mppt REAL, P_mppt REAL,
                Max_V REAL DEFAULT 0, Max_I REAL DEFAULT 0, Max_P REAL DEFAULT 0,
                updated_at TEXT, PRIMARY KEY (inverter_id, mppt_index)
            );
            """)
            # String Cache
            conn.execute("""
            CREATE TABLE IF NOT EXISTS string_cache (
                inverter_id INTEGER, string_id INTEGER, project_id INTEGER, mppt_id INTEGER,
                I_string REAL, max_I REAL DEFAULT 0, updated_at TEXT,
                PRIMARY KEY (inverter_id, string_id)
            );
            """)
            # Error Cache
            conn.execute("""
            CREATE TABLE IF NOT EXISTS error_cache (
                inverter_id INTEGER PRIMARY KEY, project_id INTEGER,
                status_code INTEGER, fault_code INTEGER,
                status_text TEXT, fault_text TEXT, fault_json TEXT, updated_at TEXT
            );
            """)

    def upsert_inverter_ac(self, inverter_id: int, project_id: int, data: dict):
        from datetime import datetime
        now_str = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO inverter_ac_cache (
                    inverter_id, project_id, IR, Temp_C, P_ac, Q_ac,
                    V_a, V_b, V_c, I_a, I_b, I_c, PF, H,
                    E_daily, E_total, delta_E_monthly, E_monthly, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(inverter_id) DO UPDATE SET
                    project_id=excluded.project_id, IR=excluded.IR, Temp_C=excluded.Temp_C, P_ac=excluded.P_ac, Q_ac=excluded.Q_ac,
                    V_a=excluded.V_a, V_b=excluded.V_b, V_c=excluded.V_c, I_a=excluded.I_a, I_b=excluded.I_b, I_c=excluded.I_c,
                    PF=excluded.PF, H=excluded.H, E_daily=excluded.E_daily, E_total=excluded.E_total,
                    delta_E_monthly=COALESCE(excluded.delta_E_monthly, inverter_ac_cache.delta_E_monthly),
                    E_monthly=COALESCE(excluded.E_monthly, inverter_ac_cache.E_monthly), updated_at=excluded.updated_at
            """, (inverter_id, project_id, data.get("ir"), data.get("temp_c"), data.get("p_inv_w"), data.get("q_inv_var"),
                  data.get("v_a"), data.get("v_b"), data.get("v_c"), data.get("i_a"), data.get("i_b"), data.get("i_c"),
                  data.get("pf"), data.get("grid_hz"), data.get("e_daily"), data.get("e_total"), 0.0, 0.0, now_str))

    def update_ac_processed(self, inverter_id: int, e_monthly: float, delta_e: float):
        with self._connect() as conn:
            conn.execute("UPDATE inverter_ac_cache SET E_monthly = ?, delta_E_monthly = ? WHERE inverter_id = ?",
                         (e_monthly, delta_e, inverter_id))

    def get_all_ac_cache(self) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM inverter_ac_cache").fetchall()
            return [dict(r) for r in rows]

    def get_ac_cache_by_project(self, project_id: int) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM inverter_ac_cache WHERE project_id = ?", (project_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_error_cache(self, inverter_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM error_cache WHERE inverter_id = ?", (inverter_id,)).fetchone()
            return dict(row) if row else None
            
    def upsert_error(self, inverter_id: int, project_id: int, status_code: int, fault_code: int, status_text: str = None, fault_text: str = None, fault_json: str = None):
        from datetime import datetime
        now_str = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO error_cache (inverter_id, project_id, status_code, fault_code, status_text, fault_text, fault_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(inverter_id) DO UPDATE SET
                    project_id=excluded.project_id, status_code=excluded.status_code, fault_code=excluded.fault_code,
                    status_text=COALESCE(excluded.status_text, error_cache.status_text),
                    fault_text=COALESCE(excluded.fault_text, error_cache.fault_text),
                    fault_json=COALESCE(excluded.fault_json, error_cache.fault_json), updated_at=excluded.updated_at
            """, (inverter_id, project_id, status_code, fault_code, status_text, fault_text, fault_json, now_str))
