"""
backend/workers/evn_worker.py — Worker quản lý toàn bộ lifecycle EVN Modbus.

Responsibilities:
1. Cập nhật Input Registers từ DB mỗi chu kỳ polling (~10s)
2. Phát hiện WRITE từ EVN → ghi lệnh vào evn_control_commands (RealtimeDB)
3. Gọi EVNTelemetryService mỗi 5 phút
4. Container Polling sẽ đọc lệnh từ DB và thực hiện điều khiển Inverter
"""

import time
import logging
import threading
from typing import Optional

from backend.db_manager import CacheDB, RealtimeDB, MetadataDB
from backend.services.modbus_server_service import ModbusServerService
from backend.services.evn_telemetry_service import EVNTelemetryService
from backend.services.project_service import ProjectService
from backend.core import settings

logger = logging.getLogger(__name__)


class EVNWorker(threading.Thread):

    def __init__(
        self,
        modbus_server: ModbusServerService,
        cache_db: CacheDB,
        realtime_db: RealtimeDB,
        metadata_db: MetadataDB,
        project_svc: ProjectService,
        control_service=None,  # Giữ lại để tương thích, không sử dụng khi tách container
    ):
        super().__init__()
        self.daemon = True
        self.modbus_server = modbus_server
        self.cache_db = cache_db
        self.realtime_db = realtime_db
        self.metadata_db = metadata_db
        self.project_svc = project_svc
        self.control_service = control_service  # None khi chạy container riêng
        self._stop_event = threading.Event()

        self.evn_telemetry = EVNTelemetryService(
            cache_db=cache_db,
            realtime_db=realtime_db,
            metadata_db=metadata_db,
            modbus_server=modbus_server,
        )

        # Tracking state để phát hiện thay đổi
        self._last_telemetry_time: float = 0
        self._evn_p_active: dict = {}   # {slave_id: bool}
        self._evn_q_active: dict = {}   # {slave_id: bool}

    def stop(self):
        self._stop_event.set()

    def run(self):
        logger.info("[EVNWorker] Started")

        while not self._stop_event.is_set():
            try:
                evn_map = self.metadata_db.get_evn_project_map()

                if not evn_map:
                    time.sleep(5)
                    continue

                # --- 1. Cập nhật Input Registers ---
                for slave_id, project in evn_map.items():
                    self._update_registers(slave_id, project)

                # --- 2. Detect WRITE changes → Ghi lệnh vào DB ---
                for slave_id, project in evn_map.items():
                    self._handle_write_changes(slave_id, project)

                # --- 3. Gửi telemetry định kỳ ---
                now = time.time()
                if (now - self._last_telemetry_time) >= settings.EVN_TELEMETRY_INTERVAL:
                    for slave_id, project in evn_map.items():
                        if project.server_id:
                            self.evn_telemetry.send_to_cloud(
                                project.id, project.server_id, slave_id
                            )
                    self._last_telemetry_time = now

            except Exception as e:
                logger.error("[EVNWorker] Loop error: %s", e, exc_info=True)

            time.sleep(1)

        logger.info("[EVNWorker] Stopped")

    def _update_registers(self, slave_id: int, project):
        """Cập nhật Input Registers (FC04) từ DB cho 1 project/slave."""
        try:
            inverters = self.project_svc.get_inverters_by_project(project.id)
            active_invs = [inv for inv in inverters if getattr(inv, "is_active", True)]
            inverter_ids = [inv.id for inv in active_invs]

            grid = self.evn_telemetry._get_grid_data(project.id, inverter_ids)

            p_inv_out = 0.0
            for inv_id in inverter_ids:
                ac = self.cache_db.get_ac_cache(inv_id)
                if ac:
                    p_inv_out += float(ac.get("P_ac") or 0.0)

            e_yday = self.realtime_db.get_yesterday_energy_by_project(project.id)
            e_yday_per_inv = self.realtime_db.get_yesterday_energy_per_inverter(project.id)

            project_data = {
                "p_out": grid["p_out"],
                "p_inv_out": round(p_inv_out, 2),
                "e_yday": e_yday,
                "q_out": grid["q_out"],
                "ua": grid["ua"], "ub": grid["ub"], "uc": grid["uc"],
                "ia": grid["ia"], "ib": grid["ib"], "ic": grid["ic"],
                "f": grid["f"], "pf": grid["pf"],
            }

            inverter_data = []
            for inv in active_invs:
                ac = self.cache_db.get_ac_cache(inv.id)
                p_inv = float(ac.get("P_ac") or 0.0) if ac else 0.0
                e_yd = e_yday_per_inv.get(inv.id, 0.0)
                inverter_data.append({"p_inv": p_inv, "e_yday": e_yd})

            self.modbus_server.update_read_registers(slave_id, project_data, inverter_data)

        except Exception as e:
            logger.error("[EVNWorker] Update registers error slave=%s: %s", slave_id, e)

    def _handle_write_changes(self, slave_id: int, project):
        """Phát hiện khi EVN ghi lệnh WRITE và xử lý theo từng thanh ghi (FC 0x06)."""
        try:
            result = self.modbus_server.detect_write_changes(slave_id)
            if not result:
                return
            
            changes, changed_keys = result
            logger.info("[EVNWorker] Detected changes on slave=%s: %s", slave_id, changed_keys)

            prev_p = self._evn_p_active.get(slave_id, False)
            prev_q = self._evn_q_active.get(slave_id, False)
            curr_p = changes.get("Enable_Set_P", False)
            curr_q = changes.get("Enable_Set_Q", False)

            # --- P Control ---
            if curr_p:
                if not prev_p:
                    self.realtime_db.push_evn_command(project.id, "P", "LOCK_P", 0.0)
                    logger.info("[EVNWorker] Queued EVN LOCK_P for project %s", project.id)

                # Ưu tiên lệnh theo thanh ghi vừa được ghi xuống (FC 0x06)
                if "Set_P_pct" in changed_keys:
                    val = changes["Set_P_pct"]
                    self.realtime_db.push_evn_command(project.id, "P", "PERCENT", val)
                    logger.info("[EVNWorker] Queued EVN P command: PERCENT=%.2f%%", val)
                elif "Set_P_kW" in changed_keys:
                    val = changes["Set_P_kW"]
                    self.realtime_db.push_evn_command(project.id, "P", "KW", val)
                    logger.info("[EVNWorker] Queued EVN P command: KW=%.2f", val)
                elif "Enable_Set_P" in changed_keys:
                    # Nếu bật Enable mà chưa ghi giá trị, có thể thực hiện theo giá trị hiện có
                    if changes["Set_P_kW"] > 0:
                        self.realtime_db.push_evn_command(project.id, "P", "KW", changes["Set_P_kW"])
                    else:
                        self.realtime_db.push_evn_command(project.id, "P", "PERCENT", changes["Set_P_pct"])

            elif prev_p and not curr_p:
                self.realtime_db.push_evn_command(project.id, "P", "RESET", 0.0)
                self.realtime_db.push_evn_command(project.id, "P", "UNLOCK_P", 0.0)
                logger.info("[EVNWorker] Queued EVN P RESET + UNLOCK_P for project %s", project.id)

            # --- Q Control ---
            if curr_q:
                if not prev_q:
                    self.realtime_db.push_evn_command(project.id, "Q", "LOCK_Q", 0.0)
                    logger.info("[EVNWorker] Queued EVN LOCK_Q for project %s", project.id)

                if "Set_Q_pct" in changed_keys:
                    val = changes["Set_Q_pct"]
                    self.realtime_db.push_evn_command(project.id, "Q", "PERCENT", val)
                    logger.info("[EVNWorker] Queued EVN Q command: PERCENT=%.2f%%", val)
                elif "Set_Q_kVAr" in changed_keys:
                    val = changes["Set_Q_kVAr"]
                    self.realtime_db.push_evn_command(project.id, "Q", "KVAR", val)
                    logger.info("[EVNWorker] Queued EVN Q command: kVAr=%.2f", val)

            elif prev_q and not curr_q:
                self.realtime_db.push_evn_command(project.id, "Q", "RESET", 0.0)
                self.realtime_db.push_evn_command(project.id, "Q", "UNLOCK_Q", 0.0)
                logger.info("[EVNWorker] Queued EVN Q RESET + UNLOCK_Q for project %s", project.id)

            self._evn_p_active[slave_id] = curr_p
            self._evn_q_active[slave_id] = curr_q

        except Exception as e:
            logger.error("[EVNWorker] Write change handling error slave=%s: %s", slave_id, e)
