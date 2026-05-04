"""
backend/services/evn_telemetry_service.py — Đóng gói và gửi dữ liệu EVN lên Cloud qua Uploader.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from backend.db_manager import CacheDB, RealtimeDB, MetadataDB
from backend.services.modbus_server_service import ModbusServerService

logger = logging.getLogger(__name__)

# Timezone Việt Nam
VN_TZ = timezone(timedelta(hours=7))


class EVNTelemetryService:

    def __init__(
        self,
        cache_db: CacheDB,
        realtime_db: RealtimeDB,
        metadata_db: MetadataDB,
        modbus_server: ModbusServerService,
    ):
        self.cache_db = cache_db
        self.realtime_db = realtime_db
        self.metadata_db = metadata_db
        self.modbus_server = modbus_server

    def _get_grid_data(self, project_id: int, inverter_ids: List[int]) -> dict:
        """
        Lấy dữ liệu lưới (P_out, Q_out, U, I, F, PF) theo thứ tự ưu tiên:
            1. Meter (nếu có) → meter_cache
            2. Inverter (fallback):
               - U, F, PF → từ inverter đầu tiên
               - I → tổng I của tất cả inverter

        Returns: dict với các trường dữ liệu đo lường thô và năng lượng.
        """
        result = {
            "p_out": 0.0, "q_out": 0.0,
            "ua": 0.0, "ub": 0.0, "uc": 0.0,
            "ia": 0.0, "ib": 0.0, "ic": 0.0,
            "f": 0.0, "pf": 0.0,
        }

        # --- Thử đọc từ Meter trước ---
        meter_rows = self.cache_db.get_meter_cache_by_project(project_id)
        if meter_rows:
            # Lấy meter đầu tiên
            m = meter_rows[0]
            result["p_out"] = float(m.get("P_total") or 0.0)
            result["q_out"] = float(m.get("Q_total") or 0.0)
            result["ua"] = float(m.get("V_a") or 0.0)
            result["ub"] = float(m.get("V_b") or 0.0)
            result["uc"] = float(m.get("V_c") or 0.0)
            result["ia"] = float(m.get("I_a") or 0.0)
            result["ib"] = float(m.get("I_b") or 0.0)
            result["ic"] = float(m.get("I_c") or 0.0)
            result["f"] = float(m.get("F") or 0.0)
            result["pf"] = float(m.get("PF") or 0.0)
            return result

        # --- Fallback: Đọc từ Inverter ---
        all_caches = []
        for inv_id in inverter_ids:
            ac = self.cache_db.get_ac_cache(inv_id)
            if ac:
                all_caches.append(ac)

        if not all_caches:
            return result

        # Lưu ý: P_ac và Q_ac từ Inverter thường là W/VAr
        result["p_out"] = sum(float(c.get("P_ac") or 0.0) for c in all_caches)
        result["q_out"] = sum(float(c.get("Q_ac") or 0.0) for c in all_caches)

        first = all_caches[0]
        result["ua"] = float(first.get("V_a") or 0.0)
        result["ub"] = float(first.get("V_b") or 0.0)
        result["uc"] = float(first.get("V_c") or 0.0)
        result["f"] = float(first.get("H") or 0.0)
        result["pf"] = float(first.get("PF") or 0.0)

        result["ia"] = round(sum(float(c.get("I_a") or 0.0) for c in all_caches), 2)
        result["ib"] = round(sum(float(c.get("I_b") or 0.0) for c in all_caches), 2)
        result["ic"] = round(sum(float(c.get("I_c") or 0.0) for c in all_caches), 2)

        return result

    def build_evn_payload(self, project_id: int, slave_id: int) -> dict:
        """Đóng gói payload EVN telemetry."""
        inverters = self.metadata_db.get_inverters_by_project(project_id)
        active_invs = [inv for inv in inverters if getattr(inv, "is_active", True)]
        inverter_ids = [inv.id for inv in active_invs]

        grid = self._get_grid_data(project_id, inverter_ids)

        p_inv_out = 0.0
        e_daily_total = 0.0
        for inv_id in inverter_ids:
            ac = self.cache_db.get_ac_cache(inv_id)
            if ac:
                p_inv_out += float(ac.get("P_ac") or 0.0)
                e_daily_total += float(ac.get("E_daily") or 0.0)

        e_yday = self.realtime_db.get_yesterday_energy_by_project(project_id)
        e_yday_per_inv = self.realtime_db.get_yesterday_energy_per_inverter(project_id)
        evn_state = self.modbus_server.get_evn_control_state(slave_id)

        # --- Xác định trạng thái điều khiển P ---
        enable_p = evn_state.get("Enable_Set_P", False)
        type_set_p = None
        set_p_pct = None
        set_p_kw = None

        if enable_p:
            if evn_state.get("Set_P_kW", 0.0) > 0:
                type_set_p = 1
                set_p_kw = evn_state["Set_P_kW"]
            else:
                type_set_p = 0
                set_p_pct = evn_state["Set_P_pct"]

        # --- Xác định trạng thái điều khiển Q ---
        enable_q = evn_state.get("Enable_Set_Q", False)
        type_set_q = None
        set_q_pct = None
        set_q_kvar = None

        if enable_q:
            if evn_state.get("Set_Q_kVAr", 0.0) > 0:
                type_set_q = 1
                set_q_kvar = evn_state["Set_Q_kVAr"]
            else:
                type_set_q = 0
                set_q_pct = evn_state["Set_Q_pct"]

        invs_data = []
        for inv in active_invs:
            ac = self.cache_db.get_ac_cache(inv.id)
            p_inv = float(ac.get("P_ac") or 0.0) if ac else 0.0
            p_inv_kw = round(p_inv / 1000.0, 3)
            e_yd = e_yday_per_inv.get(inv.id, 0.0)
            invs_data.append([p_inv_kw, round(e_yd, 2)])

        now_str = datetime.now(VN_TZ).isoformat()

        payload = {
            "EVN_connect": self.modbus_server.get_connection_status(),
            "Logger_connect": True,
            "P_out": round(grid["p_out"] / 1000.0, 3),
            "Q_out": round(grid["q_out"] / 1000.0, 3),
            "P_inv_out": round(p_inv_out / 1000.0, 3),
            "E_daily": round(e_daily_total, 2),
            "E_yday": round(e_yday, 2),
            "F": round(grid["f"], 2),
            "PF": round(grid["pf"], 4),
            "I_a": round(grid["ia"], 2),
            "I_b": round(grid["ib"], 2),
            "I_c": round(grid["ic"], 2),
            "U_a": round(grid["ua"], 2),
            "U_b": round(grid["ub"], 2),
            "U_c": round(grid["uc"], 2),
            
            "Enable_Set_P": enable_p,
            "Type_Set_P": type_set_p,
            "Set_P_pct": set_p_pct,
            "Set_P_kW": set_p_kw,
            
            "Enable_Set_Q": enable_q,
            "Type_Set_Q": type_set_q,
            "Set_Q_pct": set_q_pct,
            "Set_Q_kVAr": set_q_kvar,
            
            "Invs_Data": invs_data,
            "created_at": now_str,
        }
        return payload

    def send_to_cloud(self, project_id: int, server_id: int, slave_id: int) -> bool:
        """Đóng gói và đẩy vào outbox để UploaderService xử lý gửi đi."""
        try:
            payload = self.build_evn_payload(project_id, slave_id)
            logger.info(
                "[EVNTelemetry] Built payload project=%s slave_id=%s server_id=%s payload=%s",
                project_id,
                slave_id,
                server_id,
                json.dumps(payload, ensure_ascii=False),
            )
            self.realtime_db.post_to_outbox(project_id, server_id, payload, data_type="EVN")
            logger.info("[EVNTelemetry] Queued to outbox project=%s (server_id=%s)", project_id, server_id)
            return True
        except Exception as e:
            logger.error("[EVNTelemetry] Failed to queue: %s", e)
            return False
