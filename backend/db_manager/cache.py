import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from .base_db import BaseDB

class CacheDB(BaseDB):
    """Quản lý dữ liệu thay đổi nhanh (RAM-based), hỗ trợ lưu đệm trượt ngắn hạn 5 phút."""
    
    def __init__(self, db_path: str):
        import threading
        super().__init__(db_path)
        self.batch_lock = threading.RLock()
    
    def _connect(self):
        conn = super()._connect()
        # Tối ưu hóa tối đa cho RAM
        conn.execute("PRAGMA journal_mode=MEMORY;")
        conn.execute("PRAGMA synchronous=OFF;")
        return conn

    def _create_tables(self):
        with self._connect() as conn:
            # Kiểm tra xem cấu trúc bảng cũ (với inverter_id là PRIMARY KEY cố định) có tồn tại không
            cols = {row[1] for row in conn.execute("PRAGMA table_info(inverter_ac_cache)").fetchall()}
            if cols and "id" not in cols:
                # Nâng cấp lên cấu trúc lưu lịch sử chuỗi thời gian 5 phút: Drop bảng cache cũ
                conn.execute("DROP TABLE IF EXISTS inverter_ac_cache;")
                conn.execute("DROP TABLE IF EXISTS mppt_cache;")
                conn.execute("DROP TABLE IF EXISTS string_cache;")
                conn.execute("DROP TABLE IF EXISTS error_cache;")
                conn.execute("DROP TABLE IF EXISTS meter_cache;")

            # 1. AC Cache (Hỗ trợ lưu nhiều bản ghi trong 5 phút)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS inverter_ac_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inverter_id INTEGER, project_id INTEGER,
                IR REAL, Temp_C REAL, P_ac REAL, Q_ac REAL,
                V_a REAL, V_b REAL, V_c REAL, I_a REAL, I_b REAL, I_c REAL,
                PF REAL, H REAL, E_daily REAL, E_total REAL,
                delta_E_monthly REAL DEFAULT 0, E_monthly REAL DEFAULT 0, 
                p_dc_w REAL DEFAULT 0, updated_at TEXT
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ac_inv_time ON inverter_ac_cache (inverter_id, updated_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ac_proj_time ON inverter_ac_cache (project_id, updated_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ac_time ON inverter_ac_cache (updated_at);")

            # 2. MPPT Cache
            conn.execute("""
            CREATE TABLE IF NOT EXISTS mppt_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inverter_id INTEGER, mppt_index INTEGER, project_id INTEGER,
                V_mppt REAL, I_mppt REAL, P_mppt REAL,
                Max_V REAL DEFAULT 0, Max_I REAL DEFAULT 0, Max_P REAL DEFAULT 0,
                updated_at TEXT
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mppt_inv_time ON mppt_cache (inverter_id, mppt_index, updated_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mppt_time ON mppt_cache (updated_at);")

            # 3. String Cache
            conn.execute("""
            CREATE TABLE IF NOT EXISTS string_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inverter_id INTEGER, string_id INTEGER, project_id INTEGER, mppt_id INTEGER,
                I_string REAL, max_I REAL DEFAULT 0, updated_at TEXT
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_string_inv_time ON string_cache (inverter_id, string_id, updated_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_string_time ON string_cache (updated_at);")

            # 4. Error Cache
            conn.execute("""
            CREATE TABLE IF NOT EXISTS error_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inverter_id INTEGER, project_id INTEGER,
                status_code INTEGER, fault_code INTEGER,
                status_text TEXT, fault_text TEXT, fault_json TEXT, updated_at TEXT
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_err_inv_time ON error_cache (inverter_id, updated_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_err_time ON error_cache (updated_at);")

            # 5. Meter Cache
            conn.execute("""
            CREATE TABLE IF NOT EXISTS meter_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meter_id INTEGER,
                project_id INTEGER,
                P_total REAL, P_a REAL, P_b REAL, P_c REAL,
                Q_total REAL, Q_a REAL, Q_b REAL, Q_c REAL,
                S_total REAL, S_a REAL, S_b REAL, S_c REAL,
                V_a REAL, V_b REAL, V_c REAL, V_phase_avg REAL,
                V_ab REAL, V_bc REAL, V_ca REAL, V_line_avg REAL,
                I_a REAL, I_b REAL, I_c REAL, I_avg REAL,
                PF REAL, PF_a REAL, PF_b REAL, PF_c REAL,
                F REAL,
                exp_st_today REAL, exp_pt_today REAL, exp_qt_today REAL,
                imp_st_today REAL, imp_pt_today REAL, imp_qt_today REAL,
                e_pt_import REAL, e_pt_export REAL,
                e_qt_import REAL, e_qt_export REAL,
                e_st_import REAL, e_st_export REAL,
                updated_at TEXT
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_meter_inv_time ON meter_cache (meter_id, updated_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_meter_time ON meter_cache (updated_at);")

            # 6. Zero Export Status Cache — Lưu trạng thái runtime để Web và Polling chia sẻ
            conn.execute("""
            CREATE TABLE IF NOT EXISTS zero_export_status_cache (
                project_id INTEGER PRIMARY KEY,
                enabled INTEGER,
                suspended_by TEXT,
                p_grid_w REAL,
                p_inv_total_w REAL,
                p_inv_setpoint_w REAL,
                last_action TEXT,
                meter_fail_count INTEGER,
                last_updated TEXT
            );
            """)

    # =========================================================
    # INVERTER AC CACHE
    # =========================================================
    def get_ac_cache(self, inverter_id: int, max_age_seconds: Optional[float] = 300.0) -> Optional[dict]:
        """Lấy bản ghi AC mới nhất của Inverter (mặc định trong vòng 5 phút)."""
        cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).isoformat() if max_age_seconds is not None else ""
        with self.batch_lock:
            with self._connect() as conn:
                row = conn.execute("""
                    SELECT * FROM inverter_ac_cache 
                    WHERE inverter_id = ? AND (? = '' OR updated_at >= ?)
                    ORDER BY updated_at DESC LIMIT 1
                """, (inverter_id, cutoff, cutoff)).fetchone()
                return dict(row) if row else None

    def upsert_inverter_ac(self, inverter_id: int, project_id: int, data: dict):
        """Thêm bản ghi AC mới vào cache chuỗi thời gian (kế thừa E_monthly nếu chưa tính)."""
        now_str = datetime.now().isoformat()
        delta_e = data.get("delta_E_monthly")
        e_monthly = data.get("e_monthly")
        
        if delta_e is None or e_monthly is None:
            prev = self.get_ac_cache(inverter_id, max_age_seconds=None)
            if prev:
                if delta_e is None:
                    delta_e = prev.get("delta_E_monthly", 0.0)
                if e_monthly is None:
                    e_monthly = prev.get("E_monthly", 0.0)

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO inverter_ac_cache (
                    inverter_id, project_id, IR, Temp_C, P_ac, Q_ac,
                    V_a, V_b, V_c, I_a, I_b, I_c, PF, H,
                    E_daily, E_total, delta_E_monthly, E_monthly, p_dc_w, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                inverter_id, project_id, data.get("ir"), data.get("temp_c"), data.get("p_inv_w"), data.get("q_inv_var"),
                data.get("v_a"), data.get("v_b"), data.get("v_c"), data.get("i_a"), data.get("i_b"), data.get("i_c"),
                data.get("pf"), data.get("grid_hz"), data.get("e_daily"), data.get("e_total"),
                delta_e or 0.0, e_monthly or 0.0, data.get("p_dc_w"), now_str
            ))

    def update_ac_processed(self, inverter_id: int, e_monthly: float, delta_e: float):
        """Cập nhật E_monthly và delta_E cho bản ghi AC mới nhất của Inverter."""
        with self._connect() as conn:
            conn.execute("""
                UPDATE inverter_ac_cache
                SET E_monthly = ?, delta_E_monthly = ?
                WHERE id = (
                    SELECT id FROM inverter_ac_cache
                    WHERE inverter_id = ?
                    ORDER BY updated_at DESC LIMIT 1
                )
            """, (e_monthly, delta_e, inverter_id))

    def get_all_ac_cache(self, max_age_seconds: Optional[float] = 300.0) -> List[dict]:
        """Lấy bản ghi AC mới nhất của TẤT CẢ Inverter trong vòng max_age_seconds (mỗi inv 1 bản ghi)."""
        cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).isoformat() if max_age_seconds is not None else ""
        with self.batch_lock:
            with self._connect() as conn:
                query = """
                WITH ranked AS (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY inverter_id ORDER BY updated_at DESC) as rn
                    FROM inverter_ac_cache
                    WHERE (? = '' OR updated_at >= ?)
                )
                SELECT * FROM ranked WHERE rn = 1 ORDER BY inverter_id ASC
                """
                rows = conn.execute(query, (cutoff, cutoff)).fetchall()
                return [dict(r) for r in rows]

    def get_ac_cache_by_project(self, project_id: int, max_age_seconds: Optional[float] = 300.0) -> List[dict]:
        """Lấy bản ghi AC mới nhất của các Inverter thuộc 1 project trong vòng max_age_seconds."""
        cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).isoformat() if max_age_seconds is not None else ""
        with self.batch_lock:
            with self._connect() as conn:
                query = """
                WITH ranked AS (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY inverter_id ORDER BY updated_at DESC) as rn
                    FROM inverter_ac_cache
                    WHERE project_id = ? AND (? = '' OR updated_at >= ?)
                )
                SELECT * FROM ranked WHERE rn = 1 ORDER BY inverter_id ASC
                """
                rows = conn.execute(query, (project_id, cutoff, cutoff)).fetchall()
                return [dict(r) for r in rows]

    # =========================================================
    # ERROR CACHE
    # =========================================================
    def get_error_cache(self, inverter_id: int, max_age_seconds: Optional[float] = 300.0) -> Optional[dict]:
        """Lấy trạng thái lỗi mới nhất của Inverter trong vòng max_age_seconds."""
        cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).isoformat() if max_age_seconds is not None else ""
        with self.batch_lock:
            with self._connect() as conn:
                row = conn.execute("""
                    SELECT * FROM error_cache 
                    WHERE inverter_id = ? AND (? = '' OR updated_at >= ?)
                    ORDER BY updated_at DESC LIMIT 1
                """, (inverter_id, cutoff, cutoff)).fetchone()
                return dict(row) if row else None

    def upsert_error(self, inverter_id: int, project_id: int, status_code: int, fault_code: int,
                     status_text: str = None, fault_text: str = None, fault_json: str = None):
        """Thêm bản ghi trạng thái lỗi mới vào cache."""
        now_str = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO error_cache (inverter_id, project_id, status_code, fault_code, status_text, fault_text, fault_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (inverter_id, project_id, status_code, fault_code, status_text, fault_text, fault_json, now_str))

    # =========================================================
    # MPPT CACHE
    # =========================================================
    def get_all_mppt_cache(self, max_age_seconds: Optional[float] = 300.0) -> List[dict]:
        """Lấy bản ghi MPPT mới nhất của tất cả Inverter trong vòng max_age_seconds."""
        cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).isoformat() if max_age_seconds is not None else ""
        with self.batch_lock:
            with self._connect() as conn:
                query = """
                WITH ranked AS (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY inverter_id, mppt_index ORDER BY updated_at DESC) as rn
                    FROM mppt_cache
                    WHERE (? = '' OR updated_at >= ?)
                )
                SELECT * FROM ranked WHERE rn = 1 ORDER BY inverter_id ASC, mppt_index ASC
                """
                rows = conn.execute(query, (cutoff, cutoff)).fetchall()
                return [dict(r) for r in rows]

    def get_mppt_cache_by_inverter(self, inverter_id: int, max_age_seconds: Optional[float] = 300.0) -> List[dict]:
        """Lấy bản ghi MPPT mới nhất của 1 Inverter trong vòng max_age_seconds."""
        cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).isoformat() if max_age_seconds is not None else ""
        with self.batch_lock:
            with self._connect() as conn:
                query = """
                WITH ranked AS (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY mppt_index ORDER BY updated_at DESC) as rn
                    FROM mppt_cache
                    WHERE inverter_id = ? AND (? = '' OR updated_at >= ?)
                )
                SELECT * FROM ranked WHERE rn = 1 ORDER BY mppt_index ASC
                """
                rows = conn.execute(query, (inverter_id, cutoff, cutoff)).fetchall()
                return [dict(r) for r in rows]

    def upsert_mppt(self, inverter_id: int, mppt_index: int, project_id: int, data: dict):
        """Thêm bản ghi MPPT mới vào cache (bảo toàn Max_V, Max_I, Max_P)."""
        now_str = datetime.now().isoformat()
        v_mppt = data.get("v_mppt", 0)
        i_mppt = data.get("i_mppt", 0)
        p_mppt = data.get("p_mppt", 0)

        prev_max_v = data.get("Max_V", 0)
        prev_max_i = data.get("Max_I", 0)
        prev_max_p = data.get("Max_P", 0)

        if not (prev_max_v and prev_max_i and prev_max_p):
            with self._connect() as conn:
                prev = conn.execute("""
                    SELECT Max_V, Max_I, Max_P FROM mppt_cache
                    WHERE inverter_id = ? AND mppt_index = ?
                    ORDER BY updated_at DESC LIMIT 1
                """, (inverter_id, mppt_index)).fetchone()
                if prev:
                    prev_max_v = max(v_mppt, prev["Max_V"] or 0)
                    prev_max_i = max(i_mppt, prev["Max_I"] or 0)
                    prev_max_p = max(p_mppt, prev["Max_P"] or 0)
                else:
                    prev_max_v = v_mppt
                    prev_max_i = i_mppt
                    prev_max_p = p_mppt
        else:
            prev_max_v = max(v_mppt, prev_max_v)
            prev_max_i = max(i_mppt, prev_max_i)
            prev_max_p = max(p_mppt, prev_max_p)

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO mppt_cache (inverter_id, mppt_index, project_id, V_mppt, I_mppt, P_mppt, Max_V, Max_I, Max_P, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (inverter_id, mppt_index, project_id, v_mppt, i_mppt, p_mppt, prev_max_v, prev_max_i, prev_max_p, now_str))

    # =========================================================
    # STRING CACHE
    # =========================================================
    def get_all_string_cache(self, max_age_seconds: Optional[float] = 300.0) -> List[dict]:
        """Lấy bản ghi String mới nhất của tất cả Inverter trong vòng max_age_seconds."""
        cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).isoformat() if max_age_seconds is not None else ""
        with self.batch_lock:
            with self._connect() as conn:
                query = """
                WITH ranked AS (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY inverter_id, string_id ORDER BY updated_at DESC) as rn
                    FROM string_cache
                    WHERE (? = '' OR updated_at >= ?)
                )
                SELECT * FROM ranked WHERE rn = 1 ORDER BY inverter_id ASC, string_id ASC
                """
                rows = conn.execute(query, (cutoff, cutoff)).fetchall()
                return [dict(r) for r in rows]

    def get_string_cache_by_inverter(self, inverter_id: int, max_age_seconds: Optional[float] = 300.0) -> List[dict]:
        """Lấy bản ghi String mới nhất của 1 Inverter trong vòng max_age_seconds."""
        cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).isoformat() if max_age_seconds is not None else ""
        with self.batch_lock:
            with self._connect() as conn:
                query = """
                WITH ranked AS (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY string_id ORDER BY updated_at DESC) as rn
                    FROM string_cache
                    WHERE inverter_id = ? AND (? = '' OR updated_at >= ?)
                )
                SELECT * FROM ranked WHERE rn = 1 ORDER BY string_id ASC
                """
                rows = conn.execute(query, (inverter_id, cutoff, cutoff)).fetchall()
                return [dict(r) for r in rows]

    def upsert_string(self, inverter_id: int, string_id: int, project_id: int, mppt_id: int, i_string: float):
        """Thêm bản ghi String mới vào cache (bảo toàn max_I)."""
        now_str = datetime.now().isoformat()
        with self._connect() as conn:
            prev = conn.execute("""
                SELECT max_I FROM string_cache
                WHERE inverter_id = ? AND string_id = ?
                ORDER BY updated_at DESC LIMIT 1
            """, (inverter_id, string_id)).fetchone()
            prev_max = max(i_string, prev["max_I"] or 0) if prev else i_string

            conn.execute("""
                INSERT INTO string_cache (inverter_id, string_id, project_id, mppt_id, I_string, max_I, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (inverter_id, string_id, project_id, mppt_id, i_string, prev_max, now_str))

    def reset_mppt_max(self, inverter_id: int):
        """Reset Max values hàng ngày cho MPPT."""
        with self._connect() as conn:
            conn.execute("UPDATE mppt_cache SET Max_V=0, Max_I=0, Max_P=0 WHERE inverter_id=?", (inverter_id,))

    def reset_string_max(self, inverter_id: int):
        """Reset max_I hàng ngày cho String."""
        with self._connect() as conn:
            conn.execute("UPDATE string_cache SET max_I=0 WHERE inverter_id=?", (inverter_id,))

    def clear_inverter_mppt_string_cache(self, inverter_id: int):
        """Xoá dữ liệu MPPT và String của 1 Inverter."""
        with self._connect() as conn:
            conn.execute("DELETE FROM mppt_cache WHERE inverter_id = ?", (inverter_id,))
            conn.execute("DELETE FROM string_cache WHERE inverter_id = ?", (inverter_id,))

    def update_mppt_max(self, inverter_id: int, mppt_index: int, max_v: float, max_i: float, max_p: float):
        """Cập nhật giá trị Max cho bản ghi MPPT mới nhất."""
        with self._connect() as conn:
            conn.execute("""
                UPDATE mppt_cache 
                SET Max_V = ?, Max_I = ?, Max_P = ?
                WHERE id = (
                    SELECT id FROM mppt_cache 
                    WHERE inverter_id = ? AND mppt_index = ? 
                    ORDER BY updated_at DESC LIMIT 1
                )
            """, (max_v, max_i, max_p, inverter_id, mppt_index))

    def update_string_max(self, inverter_id: int, string_id: int, max_i: float):
        """Cập nhật giá trị max_I cho bản ghi String mới nhất."""
        with self._connect() as conn:
            conn.execute("""
                UPDATE string_cache 
                SET max_I = ?
                WHERE id = (
                    SELECT id FROM string_cache 
                    WHERE inverter_id = ? AND string_id = ? 
                    ORDER BY updated_at DESC LIMIT 1
                )
            """, (max_i, inverter_id, string_id))

    # =========================================================
    # METER CACHE
    # =========================================================
    def get_meter_cache(self, meter_id: int, max_age_seconds: Optional[float] = 300.0) -> Optional[dict]:
        """Lấy bản ghi Meter mới nhất trong vòng max_age_seconds."""
        cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).isoformat() if max_age_seconds is not None else ""
        with self._connect() as conn:
            row = conn.execute("""
                SELECT * FROM meter_cache 
                WHERE meter_id = ? AND (? = '' OR updated_at >= ?)
                ORDER BY updated_at DESC LIMIT 1
            """, (meter_id, cutoff, cutoff)).fetchone()
            return dict(row) if row else None

    def get_meter_cache_by_project(self, project_id: int, max_age_seconds: Optional[float] = 300.0) -> List[dict]:
        """Lấy bản ghi Meter mới nhất theo project trong vòng max_age_seconds."""
        cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).isoformat() if max_age_seconds is not None else ""
        with self.batch_lock:
            with self._connect() as conn:
                query = """
                WITH ranked AS (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY meter_id ORDER BY updated_at DESC) as rn
                    FROM meter_cache
                    WHERE project_id = ? AND (? = '' OR updated_at >= ?)
                )
                SELECT * FROM ranked WHERE rn = 1
                """
                rows = conn.execute(query, (project_id, cutoff, cutoff)).fetchall()
                return [dict(r) for r in rows]

    def upsert_meter_cache(self, meter_id: int, project_id: int, data: dict):
        """Thêm bản ghi Meter mới vào cache."""
        now_str = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO meter_cache (
                    meter_id, project_id,
                    P_total, P_a, P_b, P_c,
                    Q_total, Q_a, Q_b, Q_c,
                    S_total, S_a, S_b, S_c,
                    V_a, V_b, V_c, V_phase_avg,
                    V_ab, V_bc, V_ca, V_line_avg,
                    I_a, I_b, I_c, I_avg,
                    PF, PF_a, PF_b, PF_c,
                    F,
                    exp_st_today, exp_pt_today, exp_qt_today,
                    imp_st_today, imp_pt_today, imp_qt_today,
                    e_pt_import, e_pt_export,
                    e_qt_import, e_qt_export,
                    e_st_import, e_st_export,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                meter_id, project_id,
                data.get("p_total"), data.get("p_a"), data.get("p_b"), data.get("p_c"),
                data.get("q_total"), data.get("q_a"), data.get("q_b"), data.get("q_c"),
                data.get("s_total"), data.get("s_a"), data.get("s_b"), data.get("s_c"),
                data.get("v_a"), data.get("v_b"), data.get("v_c"), data.get("v_phase_avg"),
                data.get("v_ab"), data.get("v_bc"), data.get("v_ca"), data.get("v_line_avg"),
                data.get("i_a"), data.get("i_b"), data.get("i_c"), data.get("i_avg"),
                data.get("pf"), data.get("pf_a"), data.get("pf_b"), data.get("pf_c"),
                data.get("f"),
                data.get("exp_st_today"), data.get("exp_pt_today"), data.get("exp_qt_today"),
                data.get("imp_st_today"), data.get("imp_pt_today"), data.get("imp_qt_today"),
                data.get("e_pt_import"), data.get("e_pt_export"),
                data.get("e_qt_import"), data.get("e_qt_export"),
                data.get("e_st_import"), data.get("e_st_export"),
                now_str,
            ))

    # =========================================================
    # PURGE OLD CACHE
    # =========================================================
    def purge_old_cache(self, max_age_seconds: float = 300.0):
        """Xóa các bản ghi cache cũ hơn max_age_seconds để giải phóng bộ nhớ RAM."""
        cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).isoformat()
        with self.batch_lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM inverter_ac_cache WHERE updated_at < ?", (cutoff,))
                conn.execute("DELETE FROM mppt_cache WHERE updated_at < ?", (cutoff,))
                conn.execute("DELETE FROM string_cache WHERE updated_at < ?", (cutoff,))
                conn.execute("DELETE FROM error_cache WHERE updated_at < ?", (cutoff,))
                conn.execute("DELETE FROM meter_cache WHERE updated_at < ?", (cutoff,))

    # =========================================================
    # BATCH COMMIT
    # =========================================================
    def commit_project_batch(self, batch):
        """Lưu toàn bộ dữ liệu AC, MPPT, String, Error của 1 project trong 1 lần giao dịch an toàn."""
        with self.batch_lock:
            for ac_data in batch.ac_data:
                self.upsert_inverter_ac(ac_data["inverter_id"], batch.project_id, ac_data["data"])
            
            for mppt_data in batch.mppt_data:
                self.upsert_mppt(mppt_data["inverter_id"], mppt_data["mppt_index"], batch.project_id, mppt_data["data"])
                
            for string_data in batch.string_data:
                self.upsert_string(string_data["inverter_id"], string_data["string_id"], batch.project_id, string_data["mppt_id"], string_data["i_string"])
                
            for err_data in batch.error_data:
                self.upsert_error(err_data["inverter_id"], batch.project_id, err_data["status_code"], err_data["fault_code"],
                                  err_data.get("status_text"), err_data.get("fault_text"), err_data.get("fault_json"))

    # =========================================================
    # ZERO EXPORT STATUS CACHE
    # =========================================================
    def upsert_zero_export_status_cache(self, project_id: int, data: dict):
        """Lưu trạng thái runtime của Zero Export vào CacheDB."""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO zero_export_status_cache (
                    project_id, enabled, suspended_by, p_grid_w,
                    p_inv_total_w, p_inv_setpoint_w, last_action,
                    meter_fail_count, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    enabled=excluded.enabled,
                    suspended_by=excluded.suspended_by,
                    p_grid_w=excluded.p_grid_w,
                    p_inv_total_w=excluded.p_inv_total_w,
                    p_inv_setpoint_w=excluded.p_inv_setpoint_w,
                    last_action=excluded.last_action,
                    meter_fail_count=excluded.meter_fail_count,
                    last_updated=excluded.last_updated
            """, (
                project_id,
                1 if data.get("enabled") else 0,
                data.get("suspended_by"),
                data.get("p_grid_w"),
                data.get("p_inv_total_w"),
                data.get("p_inv_setpoint_w"),
                data.get("last_action"),
                data.get("meter_fail_count", 0),
                data.get("last_updated"),
            ))

    def get_zero_export_status_cache(self, project_id: int) -> Optional[dict]:
        """Đọc trạng thái runtime của Zero Export từ CacheDB."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM zero_export_status_cache WHERE project_id = ?", (project_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            res["enabled"] = bool(res["enabled"])
            return res
