import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class TelemetryService:
    """
    Xây dựng telemetry payload từ snapshot và lưu vào buffer
    để UploaderService gửi lên server.

    Luồng: get_project_snapshot() → _build_payload() → buffer.save()
    """

    def __init__(self, project_service, buffer_service):
        self.project_service = project_service
        self.buffer_service = buffer_service

    # ------------------------------------------------------------------
    # PUBLIC
    # ------------------------------------------------------------------

    def build_from_memory(self, project_id: int, server_id: int, inverters: list, cache_buffer: dict, tracking_service) -> dict:
        """
        Builds telemetry payload directly from memory buffer (Bước 4)
        """
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f") + "+07:00"
        
        project_rt = {
            "Temp_C": -99.0, "P_ac": 0.0, "P_dc": 0.0,
            "E_daily": 0.0, "E_monthly": 0.0, "E_total": 0.0,
        }
        
        inverters_block = []
        for inv in inverters:
            if inv.id not in cache_buffer:
                continue
                
            data = cache_buffer[inv.id]
            
            def s_get(key, default=0.0):
                v = data.get(key, default)
                return v if v is not None else default

            ac_block = {
                "IR": s_get("ir"), "Temp_C": s_get("temp_c"),
                "P_ac": s_get("p_inv_w"), "Q_ac": s_get("q_inv_var"),
                "V_a": s_get("v_a"), "V_b": s_get("v_b"), "V_c": s_get("v_c"),
                "I_a": s_get("i_a"), "I_b": s_get("i_b"), "I_c": s_get("i_c"),
                "PF": s_get("pf"), "H": s_get("grid_hz"),
                "E_daily": s_get("e_daily"), "E_monthly": s_get("e_monthly"), "E_total": s_get("e_total"),
                "created_at": timestamp
            }
            
            project_rt["P_ac"] += ac_block["P_ac"]
            project_rt["P_dc"] += s_get("p_dc_w")
            project_rt["E_daily"] += ac_block["E_daily"]
            project_rt["E_monthly"] += ac_block["E_monthly"]
            project_rt["E_total"] += ac_block["E_total"]
            project_rt["Temp_C"] = max(project_rt["Temp_C"], ac_block["Temp_C"])
            
            max_data = tracking_service.get_max_data(inv.id)
            strings_per_mppt_list = [int(x.strip()) for x in (inv.strings_per_mppt or "").split(",")] if inv.strings_per_mppt else []
            
            mppts_block = []
            for i in range(1, inv.mppt_count + 1):
                v = s_get(f"mppt_{i}_voltage")
                curr = s_get(f"mppt_{i}_current")
                mx = max_data["mppt"].get(i, {"Max_V": 0, "Max_I": 0, "Max_P": 0})
                
                string_count_on_this = strings_per_mppt_list[i-1] if i <= len(strings_per_mppt_list) else 0
                
                strings_block = []
                for s_i in range(1, string_count_on_this + 1):
                    global_s_i = sum(strings_per_mppt_list[:i-1]) + s_i if strings_per_mppt_list else s_i
                    strings_block.append({
                        "string_index": s_i,
                        "I_mppt": s_get(f"string_{global_s_i}_current"),
                        "Max_I": max_data["string"].get(global_s_i, 0.0),
                        "created_at": timestamp
                    })

                mppts_block.append({
                    "mppt_index": i,
                    "string_on_mppt": string_count_on_this,
                    "V_mppt": v,
                    "I_mppt": curr,
                    "P_mppt": round(v * curr, 2),
                    "Max_I": mx["Max_I"],
                    "Max_V": mx["Max_V"],
                    "Max_P": mx["Max_P"],
                    "created_at": timestamp,
                    "strings": strings_block
                })

            # Lấy thông tin lỗi/trạng thái đã được mapping từ PollingService
            mapped_status = data.get("mapped_status")
            if mapped_status:
                inv_severity = mapped_status["severity"]
                errors_block = [mapped_status]
            else:
                # Fallback cũ nếu không có mapped_status
                fc = data.get("fault_code", 0)
                if fc == 0:
                    state_name = data.get("state_name", "RUNNING")
                    inv_severity = data.get("severity", "STABLE")
                    errors_block = [{
                        "fault_code": 0,
                        "fault_description": state_name,
                        "repair_instruction": "",
                        "severity": inv_severity,
                        "created_at": timestamp
                    }]
                else:
                    inv_severity = data.get("severity") or "STABLE"
                    errors_block = [{
                        "fault_code": fc,
                        "fault_description": data.get("fault_description") or "",
                        "repair_instruction": data.get("repair_instruction") or "",
                        "severity": inv_severity,
                        "created_at": timestamp
                    }]
                
            inverters_block.append({
                "serial_number": inv.serial_number,
                "ac": ac_block,
                "mppts": mppts_block,
                "errors": errors_block
            })
            
        if project_rt["Temp_C"] == -99.0:
            project_rt["Temp_C"] = 0.0
            
        # Dữ liệu project: Chỉ làm tròn, không chạy qua NormalizationService (Tránh range check)
        project_block = {
            "Temp_C": round(project_rt["Temp_C"], 2),
            "P_ac": round(project_rt["P_ac"], 2) if project_rt["P_ac"] > 0 else None,
            "P_dc": round(project_rt["P_dc"], 2) if project_rt["P_dc"] > 0 else None,
            "E_daily": round(project_rt["E_daily"], 2),
            "E_monthly": round(project_rt["E_monthly"], 2),
            "E_total": round(project_rt["E_total"], 2),
            "severity": "STABLE",
            "created_at": timestamp
        }
        
        # Dữ liệu inverters: Vẫn chuẩn hóa (đã làm trong bước build inverters_block ở trên)
        # Nhưng để chắc chắn, ta chạy _normalize_payload cho riêng danh sách inverters
        inverters_block = self._normalize_payload(inverters_block)
        
        return {
            "project": project_block,
            "inverters": inverters_block
        }

    def build_and_buffer(self, project_id: int) -> bool:
        """
        Lấy snapshot của project, build telemetry payload và đẩy vào buffer.
        Trả về True nếu thành công, False nếu không có dữ liệu.
        """
        snapshot = self.project_service.get_project_snapshot(project_id)

        if not snapshot:
            logger.warning(
                f"[Telemetry] No snapshot data for project_id={project_id}, skipping"
            )
            return False

        payload = self._build_payload(project_id, snapshot)
        
        # BufferService và UploaderService cần các metadata ở mức ngoài cùng
        timestamp = payload.get("project", {}).get("created_at")
        buffer_data = payload
        
        self.buffer_service.save(project_id, buffer_data)

        logger.info(
            f"[Telemetry] Buffered telemetry for project_id={project_id} "
            f"at {timestamp}"
        )
        return True

    # ------------------------------------------------------------------
    # PRIVATE
    # ------------------------------------------------------------------

    def _build_payload(self, project_id: int, snapshot: dict) -> list:
        """
        Chuẩn hoá snapshot thành telemetry payload theo đúng format server.
        Trả về một LIST chứa OBJECT project (Server yêu cầu array).
        """
        # Lấy metadata project để lấy server_id
        project_meta = self.project_service.get_project(project_id)
        server_id = getattr(project_meta, "server_id", 0) if project_meta else 0

        # Sử dụng giờ local và gắn cứng múi giờ +07:00
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f") + "+07:00"

        # --- Project realtime ---
        project_rt = snapshot.get("project") or {}
        project_block = {
            "Temp_C":     project_rt.get("Temp_C", 0),
            "P_ac":       project_rt.get("P_ac") if project_rt.get("P_ac") is not None and project_rt.get("P_ac") > 0 else None,
            "P_dc":       project_rt.get("P_dc") if project_rt.get("P_dc") is not None and project_rt.get("P_dc") > 0 else None,
            "E_daily":    project_rt.get("E_daily", 0),
            "E_monthly":  project_rt.get("E_monthly", 0),
            "E_total":    project_rt.get("E_total", 0),
            "severity":   snapshot.get("project", {}).get("severity", "STABLE"), 
            "created_at": timestamp,
        }

        # --- Inverters ---
        inverters_block = []
        for inv in snapshot.get("inverters", []):
            spm_config = inv.get("strings_per_mppt")
            spm_list = [int(x.strip()) for x in spm_config.split(",")] if spm_config else []

            # Xử lý errors (Đã mapping qua FaultStateService)
            raw_errors = inv.get("errors") or []
            mapped_status = inv.get("mapped_status")
            
            if not raw_errors:
                if mapped_status:
                    inv_severity = mapped_status["severity"]
                    errors_block = [mapped_status]
                    if "created_at" not in errors_block[0]:
                        errors_block[0]["created_at"] = timestamp
                else:
                    inv_severity = inv.get("severity") or "STABLE"
                    errors_block = [
                        {
                            "fault_code": 0,
                            "fault_description": inv.get("state_name") or "RUNNING",
                            "repair_instruction": "",
                            "severity": inv_severity,
                            "created_at": timestamp
                        }
                    ]
            else:
                errors_block = [self._build_error(e, timestamp) for e in raw_errors]

            inverters_block.append({
                "serial_number": inv.get("serial_number", ""),
                "ac":     self._build_ac(inv.get("ac") or {}, timestamp),
                "mppts":  [self._build_mppt(m, timestamp, spm_list) for m in inv.get("mppts") or []],
                "errors": errors_block,
            })

        # Project block: Chỉ làm tròn
        for k, v in project_block.items():
            if isinstance(v, float):
                project_block[k] = round(v, 2)

        # Inverters block: Chạy chuẩn hóa
        inverters_block = self._normalize_payload(inverters_block)

        # Tạo payload cuối cùng (Object trong một List)
        result = {
            "project":    project_block,
            "inverters":  inverters_block,
        }
        
        return [result]

    def _normalize_payload(self, data: Any) -> Any:
        """Chuẩn hoá và làm tròn toàn bộ JSON telemetry payload trước khi gửi"""
        if not hasattr(self, '_norm_svc'):
            from services.normalization_service import NormalizationService, VALID_RANGE
            self._norm_svc = NormalizationService()
            self._norm_keys = VALID_RANGE

        if isinstance(data, dict):
            for k, v in data.items():
                if k in self._norm_keys:
                    data[k] = self._norm_svc._process_field(k, v)
                elif isinstance(v, float):
                    data[k] = round(v, 2)
                elif isinstance(v, (dict, list)):
                    self._normalize_payload(v)
        elif isinstance(data, list):
            for item in data:
                self._normalize_payload(item)
        return data

    # --- Sub-builders ---

    def _build_ac(self, ac: dict, snapshot_ts: str) -> dict:
        return {
            "IR":        ac.get("IR", 0),
            "Temp_C":    ac.get("Temp_C", 0),
            "P_ac":      ac.get("P_ac", 0),
            "Q_ac":      ac.get("Q_ac", 0),
            "V_a":       ac.get("V_a", 0),
            "V_b":       ac.get("V_b", 0),
            "V_c":       ac.get("V_c", 0),
            "I_a":       ac.get("I_a", 0),
            "I_b":       ac.get("I_b", 0),
            "I_c":       ac.get("I_c", 0),
            "PF":        ac.get("PF", 0),
            "H":         ac.get("H", 0),
            "E_daily":   ac.get("E_daily", 0),
            "E_monthly": ac.get("E_monthly", 0),
            "E_total":   ac.get("E_total", 0),
            "created_at": snapshot_ts,
        }

    def _build_mppt(self, mppt: dict, snapshot_ts: str, spm_list: list = None) -> dict:
        m_idx = mppt.get("mppt_index", 0)
        config_val = 0
        if spm_list and 0 < m_idx <= len(spm_list):
            config_val = spm_list[m_idx - 1]
        
        string_count = config_val or mppt.get("string_on_mppt", 0) or len(mppt.get("strings") or [])

        strings = [
            {
                "string_index": s.get("string_index", 0),
                "I_mppt":       s.get("I_mppt", 0),
                "Max_I":        s.get("Max_I", 0),
                "created_at":   snapshot_ts,
            }
            for s in mppt.get("strings") or []
        ]
        return {
            "mppt_index":    m_idx,
            "string_on_mppt": string_count,
            "V_mppt":        mppt.get("V_mppt", 0),
            "I_mppt":        mppt.get("I_mppt", 0),
            "P_mppt":        mppt.get("P_mppt", 0),
            "Max_I":         mppt.get("Max_I", 0),
            "Max_V":         mppt.get("Max_V", 0),
            "Max_P":         mppt.get("Max_P", 0),
            "created_at":    snapshot_ts,
            "strings":       strings,
        }

    def _build_error(self, error: dict, fallback_ts: str) -> dict:
        return {
            "fault_code":         error.get("fault_code", 0),
            "fault_description":  error.get("fault_description", ""),
            "repair_instruction": error.get("repair_instruction") or "",
            "severity":           error.get("severity") or "STABLE",
            "created_at":         self._format_ts(error.get("created_at") or fallback_ts),
        }

    @staticmethod
    def _format_ts(ts: str) -> str:
        """Đảm bảo format ISO với múi giờ +07:00"""
        if not ts: return ""
        
        # Nếu đã có offset múi giờ (+xx:xx) thì giữ nguyên, 
        # Nếu kết thúc bằng Z hoặc không có múi giờ thì gắn +07:00
        if "+" in ts or (ts.count("-") >= 3 and ":" in ts): 
            return ts
            
        if ts.endswith("Z"):
            return ts.replace("Z", "+07:00")
            
        if " " in ts and "T" not in ts:
            ts = ts.replace(" ", "T")
            
        return ts + "+07:00"
