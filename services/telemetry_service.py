import logging
from datetime import datetime, timezone

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
        self.buffer_service.save(payload)

        logger.info(
            f"[Telemetry] Buffered telemetry for project_id={project_id} "
            f"at {payload['timestamp']}"
        )
        return True

    # ------------------------------------------------------------------
    # PRIVATE
    # ------------------------------------------------------------------

    def _build_payload(self, project_id: int, snapshot: dict) -> dict:
        """
        Chuẩn hoá snapshot thành telemetry payload theo đúng format server.

        Payload structure:
        {
            "project_id": int,
            "timestamp": str (ISO-8601 UTC),
            "project": { Temp_C, P_ac, P_dc, E_daily, E_monthly, E_total,
                         severity, created_at },
            "inverters": [
                {
                    "serial_number": str,
                    "ac": { IR, Temp_C, P_ac, Q_ac, V_a..V_c, I_a..I_c,
                            PF, H, E_daily, E_monthly, E_total, created_at },
                    "mppts": [
                        {
                            mppt_index, string_on_mppt, V_mppt, I_mppt, P_mppt,
                            Max_I, Max_V, Max_P, created_at,
                            "strings": [{ string_index, I_mppt, Max_I, created_at }]
                        }
                    ],
                    "errors": [{ fault_code, fault_description,
                                 repair_instruction, severity, created_at }]
                }
            ]
        }
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # --- Project realtime ---
        project_rt = snapshot.get("project") or {}
        project_block = {
            "Temp_C":     project_rt.get("Temp_C", 0),
            "P_ac":       project_rt.get("P_ac", 0),
            "P_dc":       project_rt.get("P_dc", 0),
            "E_daily":    project_rt.get("E_daily", 0),
            "E_monthly":  project_rt.get("E_monthly", 0),
            "E_total":    project_rt.get("E_total", 0),
            "severity":   project_rt.get("severity", "STABLE"),
            "created_at": project_rt.get("created_at", timestamp),
        }

        # --- Inverters ---
        inverters_block = []
        for inv in snapshot.get("inverters", []):
            inverters_block.append({
                "serial_number": inv.get("serial_number", ""),
                "ac":     self._build_ac(inv.get("ac") or {}, timestamp),
                "mppts":  [self._build_mppt(m, timestamp) for m in inv.get("mppts") or []],
                "errors": [self._build_error(e, timestamp) for e in inv.get("errors") or []],
            })

        return {
            "project_id": project_id,
            "timestamp":  timestamp,
            "project":    project_block,
            "inverters":  inverters_block,
        }

    # --- Sub-builders ---

    @staticmethod
    def _build_ac(ac: dict, fallback_ts: str) -> dict:
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
            "created_at": ac.get("created_at", fallback_ts),
        }

    @staticmethod
    def _build_mppt(mppt: dict, fallback_ts: str) -> dict:
        strings = [
            {
                "string_index": s.get("string_index", 0),
                "I_mppt":       s.get("I_mppt", 0),
                "Max_I":        s.get("Max_I", 0),
                "created_at":   s.get("created_at", fallback_ts),
            }
            for s in mppt.get("strings") or []
        ]
        return {
            "mppt_index":    mppt.get("mppt_index", 0),
            "string_on_mppt": mppt.get("string_on_mppt", 0),
            "V_mppt":        mppt.get("V_mppt", 0),
            "I_mppt":        mppt.get("I_mppt", 0),
            "P_mppt":        mppt.get("P_mppt", 0),
            "Max_I":         mppt.get("Max_I", 0),
            "Max_V":         mppt.get("Max_V", 0),
            "Max_P":         mppt.get("Max_P", 0),
            "created_at":    mppt.get("created_at", fallback_ts),
            "strings":       strings,
        }

    @staticmethod
    def _build_error(error: dict, fallback_ts: str) -> dict:
        return {
            "fault_code":         error.get("fault_code", 0),
            "fault_description":  error.get("fault_description", ""),
            "repair_instruction": error.get("repair_instruction", ""),
            "severity":           error.get("severity", "STABLE"),
            "created_at":         error.get("created_at", fallback_ts),
        }
