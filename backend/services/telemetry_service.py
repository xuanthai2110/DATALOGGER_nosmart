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
        buffer_data = {
            "project_id": project_id,
            "server_id": snapshot.get("metadata", {}).get("server_id"),
            "timestamp": timestamp,
            **payload
        }
        
        self.buffer_service.save(project_id, buffer_data)

        logger.info(
            f"[Telemetry] Buffered telemetry for project_id={project_id} "
            f"at {timestamp}"
        )
        return True

    # ------------------------------------------------------------------
    # PRIVATE
    # ------------------------------------------------------------------

    def _build_payload(self, project_id: int, snapshot: dict) -> dict:
        """
        Chuẩn hoá snapshot thành telemetry payload theo đúng format server.
        Nếu inverter không có lỗi, thêm một bản ghi "RUNNING" vào errors.
        """
        # Server yêu cầu định dạng ISO với chữ Z ở cuối và đầy đủ microsecond (6 chữ số)
        # Sử dụng giờ local của Raspberry Pi (hệ thống) để tránh bị lệch 7 tiếng
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"

        # --- Project realtime ---
        project_rt = snapshot.get("project") or {}
        project_block = {
            "Temp_C":     project_rt.get("Temp_C", 0),
            "P_ac":       project_rt.get("P_ac", 0),
            "P_dc":       project_rt.get("P_dc", 0),
            "E_daily":    project_rt.get("E_daily", 0),
            "E_monthly":  project_rt.get("E_monthly", 0),
            "E_total":    project_rt.get("E_total", 0),
            "severity":   "STABLE", 
            "created_at": timestamp,
        }

        # --- Inverters ---
        inverters_block = []
        for inv in snapshot.get("inverters", []):
            spm_config = inv.get("strings_per_mppt")
            spm_list = [int(x.strip()) for x in spm_config.split(",")] if spm_config else []

            # Xử lý errors
            raw_errors = inv.get("errors") or []
            if not raw_errors:
                # Nếu không có lỗi, tạo object "RUNNING" như server yêu cầu
                errors_block = [
                    {
                        "fault_code": 0,
                        "fault_description": "RUNNING",
                        "repair_instruction": "",
                        "severity": "STABLE",
                        "created_at": timestamp
                    }
                ]
            else:
                errors_block = [self._build_error(e, timestamp) for e in raw_errors]

                # Đảm bảo repair_instruction không null (ưu tiên string rỗng nếu None)
                for e in errors_block:
                    if e.get("repair_instruction") is None:
                        e["repair_instruction"] = ""

            inverters_block.append({
                "serial_number": inv.get("serial_number", ""),
                "ac":     self._build_ac(inv.get("ac") or {}, timestamp),
                "mppts":  [self._build_mppt(m, timestamp, spm_list) for m in inv.get("mppts") or []],
                "errors": errors_block,
            })

        return self._round_floats({
            "project":    project_block,
            "inverters":  inverters_block,
        })

    def _round_floats(self, data: Any) -> Any:
        """Đảm bảo làm tròn 2 chữ số thập phân cho mọi giá trị float trong payload để tránh lỗi precision"""
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, float):
                    data[k] = round(v, 2)
                elif isinstance(v, (dict, list)):
                    self._round_floats(v)
        elif isinstance(data, list):
            for item in data:
                self._round_floats(item)
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
            "severity":           "STABLE",
            "created_at":         self._format_ts(error.get("created_at") or fallback_ts),
        }

    @staticmethod
    def _format_ts(ts: str) -> str:
        """Đảm bảo format ISO và kết thúc bằng Z"""
        if not ts: return ""
        if ts.endswith("Z"): return ts
        
        if " " in ts and "T" not in ts:
            ts = ts.replace(" ", "T")
            
        if "+00:00" in ts:
            return ts.replace("+00:00", "Z")
            
        return ts + "Z"
