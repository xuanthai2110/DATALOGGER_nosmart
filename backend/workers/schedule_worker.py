import time
import logging
import threading
from datetime import datetime

from backend.services.schedule_service import ScheduleService
from backend.services.control_service import ControlService


logger = logging.getLogger(__name__)


class ScheduleWorker(threading.Thread):
    def __init__(self, schedule_service: ScheduleService, control_service: ControlService, interval: float = 1.0):
        super().__init__()
        self.schedule_service = schedule_service
        self.control_service = control_service
        self.interval = interval
        self.daemon = True
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    @staticmethod
    def _parse_iso(dt_str: str) -> datetime:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)

    def run(self):
        logger.info(f"Schedule Worker started (Interval: {self.interval}s)")
        while not self._stop_event.is_set():
            t0 = time.time()
            try:
                now = datetime.now()
                schedules = self.schedule_service.get_all()

                for s in schedules:
                    try:
                        start_time = self._parse_iso(s.start_at)
                        end_time = self._parse_iso(s.end_at)

                        if start_time.tzinfo and not now.tzinfo:
                            now = now.astimezone(start_time.tzinfo)
                        elif not start_time.tzinfo and now.tzinfo:
                            start_time = start_time.replace(tzinfo=now.tzinfo)
                            end_time = end_time.replace(tzinfo=now.tzinfo)

                        if start_time <= now <= end_time:
                            if s.status == "SCHEDULED":
                                self.schedule_service.update_status(s.id, "RUNNING", sync_remote=True)
                                success = self.control_service.apply(s)
                                if not success:
                                    self.schedule_service.update_status(s.id, "FAILED", sync_remote=True)
                        elif now > end_time:
                            if s.status == "RUNNING":
                                success = self.control_service.reset(s)
                                if success:
                                    self.schedule_service.update_status(s.id, "COMPLETED", sync_remote=True)
                                else:
                                    self.schedule_service.update_status(s.id, "FAILED", sync_remote=True)

                    except Exception as e:
                        logger.error(f"Error processing schedule {s.id}: {e}")

            except Exception as e:
                logger.error(f"Error in Schedule Worker cycle: {e}")

            elapsed = time.time() - t0
            sleep_time = max(0.1, self.interval - elapsed)
            time.sleep(sleep_time)
