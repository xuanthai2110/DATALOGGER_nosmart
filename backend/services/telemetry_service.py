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
        ts_str = now.isoformat()
        
        # 1. AC Data
        ac_list = cache_db.get_ac_cache_by_project(project_id)
        ac_map = {r["inverter_id"]: r for r in ac_list}
        
        # 2. Results assembly
        inverters_json = []
        for inv in inverters_meta:
            inv_id = inv.id
            ac = ac_map.get(inv_id)
            if not ac: continue
            
            # Error Payload (Lấy từ fault_json đã xử lý sẵn)
            err_row = cache_db.get_error_cache(inv_id)
            errors = json.loads(err_row["fault_json"]) if err_row and err_row.get("fault_json") else []
            
            inv_data = {
                "serial_number": inv.serial_number,
                "p_ac": ac.get("P_ac", 0),
                "e_daily": ac.get("E_daily", 0),
                "e_monthly": ac.get("E_monthly", 0),
                "e_total": ac.get("E_total", 0),
                "temp_c": ac.get("Temp_C", 0),
                "errors": errors,
                "created_at": self._format_ts(ac.get("updated_at"))
            }
            inverters_json.append(inv_data)
            
        if not inverters_json: return []
            
        payload = [{
            "project_id": project_id,
            "server_id": server_id,
            "timestamp": ts_str,
            "inverters": inverters_json
        }]
        return self._normalize_payload(payload)

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
