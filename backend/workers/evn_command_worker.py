"""
backend/workers/evn_command_worker.py — Đọc lệnh EVN từ DB và thực thi điều khiển Inverter.

Chạy trong container Polling, đọc lệnh từ bảng evn_control_commands do container EVN ghi vào.

Hỗ trợ EVN Priority Lock:
  - LOCK_P / UNLOCK_P: Khóa/mở khóa trục P cho Server/MQTT
  - LOCK_Q / UNLOCK_Q: Khóa/mở khóa trục Q cho Server/MQTT
  - KW, PERCENT, KVAR: Thực thi lệnh điều khiển từ EVN
  - RESET: Đặt lại giới hạn về 100%
"""

import time
import logging
import threading

from backend.db_manager import RealtimeDB
from backend.services.control_service import ControlService

logger = logging.getLogger(__name__)


class EVNCommandWorker(threading.Thread):
    """
    Worker đọc lệnh EVN từ DB và thực hiện điều khiển Inverter qua ControlService.
    Chạy trong container Polling.
    """

    POLL_INTERVAL = 2  # Kiểm tra lệnh mới mỗi 2 giây

    def __init__(self, realtime_db: RealtimeDB, control_service: ControlService):
        super().__init__()
        self.daemon = True
        self.realtime_db = realtime_db
        self.control_service = control_service
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        logger.info("[EVNCommandWorker] Started — Waiting for EVN control commands...")

        while not self._stop_event.is_set():
            try:
                self._process_pending_commands()
            except Exception as e:
                logger.error("[EVNCommandWorker] Error: %s", e, exc_info=True)

            time.sleep(self.POLL_INTERVAL)

        logger.info("[EVNCommandWorker] Stopped")

    def _process_pending_commands(self):
        """Đọc và thực thi tất cả lệnh PENDING từ DB."""
        commands = self.realtime_db.get_pending_evn_commands()
        if not commands:
            return

        for cmd in commands:
            cmd_id     = cmd["id"]
            project_id = cmd["project_id"]
            axis       = cmd["axis"]   # 'P' hoặc 'Q'
            mode       = cmd["mode"]   # 'KW', 'KVAR', 'PERCENT', 'RESET', 'LOCK_P', 'UNLOCK_P', 'LOCK_Q', 'UNLOCK_Q'
            value      = cmd["value"]

            try:
                # --- Xử lý lệnh LOCK/UNLOCK (EVN Priority) ---
                if mode == "LOCK_P":
                    self.control_service.set_evn_lock(project_id, lock_p=True, lock_q=self.control_service.is_evn_locked_q(project_id))
                    logger.warning(
                        "[EVNCommandWorker] EVN LOCKED P axis for project %s — Server/MQTT P commands blocked.",
                        project_id,
                    )

                elif mode == "UNLOCK_P":
                    self.control_service.set_evn_lock(project_id, lock_p=False, lock_q=self.control_service.is_evn_locked_q(project_id))
                    logger.info(
                        "[EVNCommandWorker] EVN UNLOCKED P axis for project %s — Server/MQTT P commands allowed.",
                        project_id,
                    )

                elif mode == "LOCK_Q":
                    self.control_service.set_evn_lock(project_id, lock_p=self.control_service.is_evn_locked_p(project_id), lock_q=True)
                    logger.warning(
                        "[EVNCommandWorker] EVN LOCKED Q axis for project %s — Server/MQTT Q commands blocked.",
                        project_id,
                    )

                elif mode == "UNLOCK_Q":
                    self.control_service.set_evn_lock(project_id, lock_p=self.control_service.is_evn_locked_p(project_id), lock_q=False)
                    logger.info(
                        "[EVNCommandWorker] EVN UNLOCKED Q axis for project %s — Server/MQTT Q commands allowed.",
                        project_id,
                    )

                # --- Xử lý lệnh điều khiển thực tế ---
                elif axis == "P":
                    if mode == "RESET":
                        self.control_service.reset_evn_p_control(project_id)
                        logger.info("[EVNCommandWorker] Executed P RESET for project %s", project_id)
                    elif mode == "KW":
                        self.control_service.apply_evn_p_control(project_id, "KW", value)
                        logger.info("[EVNCommandWorker] Executed P control KW=%.2f for project %s", value, project_id)
                    elif mode == "PERCENT":
                        self.control_service.apply_evn_p_control(project_id, "PERCENT", value)
                        logger.info("[EVNCommandWorker] Executed P control PCT=%.2f%% for project %s", value, project_id)

                elif axis == "Q":
                    if mode == "RESET":
                        self.control_service.reset_evn_q_control(project_id)
                        logger.info("[EVNCommandWorker] Executed Q RESET for project %s", project_id)
                    elif mode == "KVAR":
                        self.control_service.apply_evn_q_control(project_id, "KVAR", value)
                        logger.info("[EVNCommandWorker] Executed Q control kVAr=%.2f for project %s", value, project_id)
                    elif mode == "PERCENT":
                        self.control_service.apply_evn_q_control(project_id, "PERCENT", value)
                        logger.info("[EVNCommandWorker] Executed Q control PCT=%.2f%% for project %s", value, project_id)

                else:
                    logger.warning("[EVNCommandWorker] Unknown command: axis=%s mode=%s", axis, mode)

                # Đánh dấu đã xử lý xong
                self.realtime_db.mark_evn_command_done(cmd_id)

            except Exception as e:
                logger.error(
                    "[EVNCommandWorker] Failed command id=%s (axis=%s mode=%s value=%s): %s",
                    cmd_id, axis, mode, value, e,
                )
