"""
backend/workers/evn_worker.py — Worker quản lý toàn bộ lifecycle EVN Modbus.

Responsibilities:
1. Khởi động ModbusServerService (async server trong event loop riêng)
2. Cập nhật Input Registers từ DB mỗi chu kỳ polling (~10s)
3. Phát hiện WRITE từ EVN → gọi ControlService (granular P/Q)
4. Gọi EVNTelemetryService mỗi 5 phút
5. Reset inverter khi EVN tắt Enable
"""

import time
import logging
import threading
from typing import Optional

from backend.db_manager import CacheDB, RealtimeDB, MetadataDB
from backend.services.modbus_server_service import ModbusServerService
from backend.services.evn_telemetry_service import EVNTelemetryService
from backend.services.control_service import ControlService
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
        control_service: ControlService,
        project_svc: ProjectService,
    ):
        super().__init__()
        self.daemon = True
        self.modbus_server = modbus_server
        self.cache_db = cache_db
        self.realtime_db = realtime_db
        self.metadata_db = metadata_db
        self.control_service = control_service
        self.project_svc = project_svc
        self._stop_event = threading.Event()

        self.evn_telemetry = EVNTelemetryService(
            cache_db=cache_db,
            realtime_db=realtime_db,
            metadata_db=metadata_db,
            modbus_server=modbus_server,
        )

        # Tracking state cho detect thay đổi
        self._last_telemetry_time: float = 0
        self._evn_p_active: dict = {}   # {slave_id: bool}
        self._evn_q_active: dict = {}   # {slave_id: bool}

    def stop(self):
        self._stop_event.set()

    def run(self):
        logger.info("[EVNWorker] Started")

        while not self._stop_event.is_set():
            try:
                # Lấy mapping project → slave_id
                evn_map = self.metadata_db.get_evn_project_map()

                if not evn_map:
                    time.sleep(5)
                    continue

                # --- 1. Cập nhật Input Registers ---
                for slave_id, project in evn_map.items():
                    self._update_registers(slave_id, project)

                # --- 2. Detect WRITE changes → apply control ---
                for slave_id, project in evn_map.items():
                    self._handle_write_changes(slave_id, project)

                # --- 3. Gửi telemetry định kỳ (5 phút) ---
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

            time.sleep(1)  # Check mỗi 1s

        logger.info("[EVNWorker] Stopped")

    def _update_registers(self, slave_id: int, project):
        """Cập nhật Input Registers (FC04) từ DB cho 1 project/slave."""
        try:
            inverters = self.project_svc.get_inverters_by_project(project.id)
            active_invs = [inv for inv in inverters if getattr(inv, "is_active", True)]
            inverter_ids = [inv.id for inv in active_invs]

            # Grid data (Meter > Inverter)
            grid = self.evn_telemetry._get_grid_data(project.id, inverter_ids)

            # P_inv_out (tổng P inverter)
            p_inv_out = 0.0
            for inv_id in inverter_ids:
                ac = self.cache_db.get_ac_cache(inv_id)
                if ac:
                    p_inv_out += float(ac.get("P_ac") or 0.0)

            # D-1
            e_yday = self.realtime_db.get_yesterday_energy_by_project(project.id)
            e_yday_per_inv = self.realtime_db.get_yesterday_energy_per_inverter(project.id)

            project_data = {
                "p_out": grid["p_out"],
                "p_inv_out": round(p_inv_out, 2),
                "e_yday": e_yday,
                "q_out": grid["q_out"],
                "ua": grid["ua"],
                "ub": grid["ub"],
                "uc": grid["uc"],
                "ia": grid["ia"],
                "ib": grid["ib"],
                "ic": grid["ic"],
                "f": grid["f"],
                "pf": grid["pf"],
            }

            inverter_data = []
            for inv in active_invs:
                ac = self.cache_db.get_ac_cache(inv.id)
                p_inv = float(ac.get("P_ac") or 0.0) if ac else 0.0
                e_yd = e_yday_per_inv.get(inv.id, 0.0)
                inverter_data.append({"p_inv": p_inv, "e_yday": e_yd})

            self.modbus_server.update_read_registers(
                slave_id, project_data, inverter_data
            )

        except Exception as e:
            logger.error("[EVNWorker] Update registers error slave=%s: %s", slave_id, e)

    def _handle_write_changes(self, slave_id: int, project):
        """Phát hiện khi EVN ghi lệnh WRITE → gọi ControlService."""
        try:
            changes = self.modbus_server.detect_write_changes(slave_id)
            if changes is None:
                return

            logger.info(
                "[EVNWorker] Detected EVN write change on slave=%s: %s",
                slave_id, changes,
            )

            prev_p = self._evn_p_active.get(slave_id, False)
            prev_q = self._evn_q_active.get(slave_id, False)
            curr_p = changes.get("Enable_Set_P", False)
            curr_q = changes.get("Enable_Set_Q", False)

            # --- P Control ---
            if curr_p:
                set_p_pct = changes.get("Set_P_pct", 0.0)
                set_p_kw = changes.get("Set_P_kW", 0.0)

                if set_p_kw > 0:
                    self.control_service.apply_evn_p_control(
                        project.id, "KW", set_p_kw
                    )
                    logger.info(
                        "[EVNWorker] Applied EVN P control KW=%.2f for project %s",
                        set_p_kw, project.id,
                    )
                elif set_p_pct > 0:
                    self.control_service.apply_evn_p_control(
                        project.id, "PERCENT", set_p_pct
                    )
                    logger.info(
                        "[EVNWorker] Applied EVN P control PCT=%.2f%% for project %s",
                        set_p_pct, project.id,
                    )
            elif prev_p and not curr_p:
                # EVN tắt P control → reset 100%
                self.control_service.reset_evn_p_control(project.id)
                logger.info("[EVNWorker] EVN P control disabled → reset project %s", project.id)

            # --- Q Control ---
            if curr_q:
                set_q_pct = changes.get("Set_Q_pct", 0.0)
                set_q_kvar = changes.get("Set_Q_kVAr", 0.0)

                if set_q_kvar > 0:
                    self.control_service.apply_evn_q_control(
                        project.id, "KVAR", set_q_kvar
                    )
                    logger.info(
                        "[EVNWorker] Applied EVN Q control kVAr=%.2f for project %s",
                        set_q_kvar, project.id,
                    )
                elif set_q_pct > 0:
                    self.control_service.apply_evn_q_control(
                        project.id, "PERCENT", set_q_pct
                    )
                    logger.info(
                        "[EVNWorker] Applied EVN Q control PCT=%.2f%% for project %s",
                        set_q_pct, project.id,
                    )
            elif prev_q and not curr_q:
                # EVN tắt Q control → reset
                self.control_service.reset_evn_q_control(project.id)
                logger.info("[EVNWorker] EVN Q control disabled → reset project %s", project.id)

            self._evn_p_active[slave_id] = curr_p
            self._evn_q_active[slave_id] = curr_q

        except Exception as e:
            logger.error("[EVNWorker] Write change handling error slave=%s: %s", slave_id, e)
