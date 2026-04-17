import logging
import json
from datetime import datetime
from typing import Any, List
from backend.db_manager import CacheDB

logger = logging.getLogger(__name__)

class TelemetryService:
    """Xây dựng telemetry payload từ CacheDB (RAM) để gửi lên server."""
    def __init__(self, realtime_db):
        self.realtime_db = realtime_db

    def build_payload_from_cache(self, project_id: int, server_id: int, inverters_meta: list, cache_db: CacheDB) -> list:
        now = datetime.now()
        payload_created_at = self._format_ts(now.isoformat())
        
        # Aggregate Project Data from Inverters in Cache
        total_p_ac = 0.0
        total_p_dc = 0.0
        total_e_daily = 0.0
        total_e_monthly = 0.0
        total_e_total = 0.0
        temp_list = []
        
        inverters_json = []
        for inv in inverters_meta:
            inv_id = inv.id
            
            # AC Data (from Cache)
            ac = cache_db.get_ac_cache(inv_id)
            if not ac: continue
            
            # Totals
            total_p_ac += self._num(ac.get("P_ac"))
            total_e_daily += self._num(ac.get("E_daily"))
            total_e_monthly += self._num(ac.get("E_monthly"))
            total_e_total += self._num(ac.get("E_total"))
            if ac.get("Temp_C") is not None:
                temp_list.append(self._num(ac.get("Temp_C")))
            
            # MPPT & Strings (from Cache)
            mppts_cache = cache_db.get_mppt_cache_by_inverter(inv_id)
            strings_cache = cache_db.get_string_cache_by_inverter(inv_id)
            
            inv_dc_sum = 0.0
            mppt_list = []
            for m in mppts_cache:
                m_idx = m["mppt_index"]
                inv_dc_sum += self._num(m.get("P_mppt"))
                
                m_strings = [
                    {
                        "string_index": s["string_id"],
                        "I_mppt": self._num(s.get("I_string")),
                        "Max_I": self._num(s.get("max_I")),
                        "created_at": payload_created_at
                    }
                    for s in strings_cache if s["mppt_id"] == m_idx
                ]
                
                mppt_list.append({
                    "mppt_index": m_idx,
                    "string_on_mppt": m.get("string_on_mppt", 2),
                    "V_mppt": self._num(m.get("V_mppt")),
                    "I_mppt": self._num(m.get("I_mppt")),
                    "P_mppt": self._num(m.get("P_mppt")),
                    "Max_I": self._num(m.get("Max_I")),
                    "Max_V": self._num(m.get("Max_V")),
                    "Max_P": self._num(m.get("Max_P")),
                    "created_at": payload_created_at,
                    "strings": m_strings
                })
            
            total_p_dc += inv_dc_sum

            # Error Payload
            err_row = cache_db.get_error_cache(inv_id)
            errors = []
            if err_row:
                if err_row.get("fault_json"):
                    try:
                        errors = self._normalize_error_items(json.loads(err_row["fault_json"]), payload_created_at)
                    except Exception:
                        logger.warning(f"Invalid fault_json in cache for inverter {inv_id}. Using fallback error payload.")
                        errors = []
                else:
                    errors = self._normalize_error_items([{
                        "fault_code": err_row.get("fault_code", 0),
                        "fault_description": err_row.get("status_text") or err_row.get("fault_text") or "UNKNOWN",
                        "repair_instruction": "",
                        "severity": "STABLE",
                        "created_at": payload_created_at
                    }], payload_created_at)
            if not errors:
                errors = [self._default_error_item(err_row, ac, payload_created_at)]
            
            inv_data = {
                "serial_number": inv.serial_number,
                "ac": {
                    "IR": self._num(ac.get("IR")),
                    "Temp_C": self._num(ac.get("Temp_C")),
                    "P_ac": self._num(ac.get("P_ac")),
                    "Q_ac": self._num(ac.get("Q_ac")),
                    "V_a": self._num(ac.get("V_a")),
                    "V_b": self._num(ac.get("V_b")),
                    "V_c": self._num(ac.get("V_c")),
                    "I_a": self._num(ac.get("I_a")),
                    "I_b": self._num(ac.get("I_b")),
                    "I_c": self._num(ac.get("I_c")),
                    "PF": self._num(ac.get("PF")),
                    "H": self._num(ac.get("H")),
                    "E_daily": self._num(ac.get("E_daily")),
                    "E_monthly": self._num(ac.get("E_monthly")),
                    "E_total": self._num(ac.get("E_total")),
                    "created_at": payload_created_at
                },
                "mppts": mppt_list,
                "errors": errors
            }
            inverters_json.append(inv_data)
        
        if not inverters_json: return []

        # Final Project Summary
        avg_temp = round(sum(temp_list) / len(temp_list), 1) if temp_list else 0.0
        project_json = {
            "Temp_C": avg_temp,
            "P_ac": round(total_p_ac, 2),
            "P_dc": round(total_p_dc, 2),
            "E_daily": round(total_e_daily, 2),
            "E_monthly": round(total_e_monthly, 2),
            "E_total": round(total_e_total, 2),
            "severity": "STABLE",
            "created_at": payload_created_at
        }
            
        # Final Payload EXACTLY as data.json
        payload = {
            "project": project_json,
            "inverters": inverters_json
        }
        return [self._normalize_payload(payload)]

    def is_all_inverters_sleep(self, inverter_ids: list[int], cache_db: CacheDB) -> bool:
        if not inverter_ids:
            return False

        for inv_id in inverter_ids:
            ac_row = cache_db.get_ac_cache(inv_id)
            err_row = cache_db.get_error_cache(inv_id)
            if ac_row is None or err_row is None:
                return False

            status_text = (err_row.get("status_text") or "").strip().upper()
            if status_text != "SLEEP":
                return False

        return True

    def is_all_inverters_disconnect(self, inverter_ids: list[int], cache_db: CacheDB) -> bool:
        if not inverter_ids:
            return False

        for inv_id in inverter_ids:
            ac_row = cache_db.get_ac_cache(inv_id)
            err_row = cache_db.get_error_cache(inv_id)
            if ac_row is None or err_row is None:
                return False

            if self._get_error_severity(err_row) != "DISCONNECT":
                return False

        return True

    def _normalize_payload(self, data: Any) -> Any:
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, float): data[k] = round(v, 2)
                elif isinstance(v, (dict, list)): self._normalize_payload(v)
        elif isinstance(data, list):
            for item in data: self._normalize_payload(item)
        return data

    @staticmethod
    def _format_ts(ts: str) -> str:
        if not ts: return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f") + "+07:00"
        if "T" not in ts: ts = ts.replace(" ", "T")
        if "+" not in ts and not ts.endswith("Z"): ts += "+07:00"
        return ts

    def _normalize_error_items(self, errors: list, payload_created_at: str | None = None) -> list:
        normalized = []
        for item in errors or []:
            if not isinstance(item, dict):
                continue
            normalized.append({
                "fault_code": item.get("fault_code", 0),
                "fault_description": item.get("fault_description", "UNKNOWN"),
                "repair_instruction": item.get("repair_instruction", ""),
                "severity": item.get("severity", "STABLE"),
                "created_at": payload_created_at or self._format_ts(item.get("created_at"))
            })
        return normalized

    def _default_error_item(self, err_row: dict | None, ac_row: dict | None, payload_created_at: str | None = None) -> dict:
        ts = None
        if err_row:
            ts = err_row.get("updated_at")
        if not ts and ac_row:
            ts = ac_row.get("updated_at")
        return {
            "fault_code": 0,
            "fault_description": (err_row or {}).get("status_text") or "UNKNOWN",
            "repair_instruction": "",
            "severity": "STABLE",
            "created_at": payload_created_at or self._format_ts(ts)
        }

    @staticmethod
    def _get_error_severity(err_row: dict | None) -> str:
        if not err_row:
            return ""

        fault_json = err_row.get("fault_json")
        if not fault_json:
            return ""

        try:
            items = json.loads(fault_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            return ""

        if not isinstance(items, list):
            return ""

        for item in items:
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity", "")).strip().upper()
            if severity:
                return severity

        return ""

    @staticmethod
    def _num(value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
