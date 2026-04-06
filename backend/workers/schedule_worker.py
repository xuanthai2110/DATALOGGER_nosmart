import time
import logging
import threading
from datetime import datetime
from dateutil import parser
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

    def run(self):
        logger.info(f"Schedule Worker started (Interval: {self.interval}s)")
        while not self._stop_event.is_set():
            t0 = time.time()
            try:
                now = datetime.now()
                schedules = self.schedule_service.get_all()
                
                for s in schedules:
                    try:
                        start_time = parser.parse(s.start_at)
                        end_time = parser.parse(s.end_at)
                        
                        # Support naiive and timezone aware matching
                        if start_time.tzinfo and not now.tzinfo:
                            now = now.astimezone(start_time.tzinfo)
                        elif not start_time.tzinfo and now.tzinfo:
                            start_time = start_time.replace(tzinfo=now.tzinfo)
                            end_time = end_time.replace(tzinfo=now.tzinfo)
                            
                        if start_time <= now <= end_time:
                            if s.status == "SCHEDULED":
                                # Trigger Start
                                success = self.control_service.apply(s)
                                if success:
                                    self.schedule_service.update_status(s.id, "RUNNING")
                                else:
                                    self.schedule_service.update_status(s.id, "FAILED")
                        elif now > end_time:
                            if s.status == "RUNNING":
                                # Trigger Stop
                                success = self.control_service.reset(s)
                                if success:
                                    self.schedule_service.update_status(s.id, "COMPLETED")
                                else:
                                    self.schedule_service.update_status(s.id, "FAILED")
                                    
                    except Exception as e:
                        logger.error(f"Error processing schedule {s.id}: {e}")
                        
            except Exception as e:
                logger.error(f"Error in Schedule Worker cycle: {e}")
            
            elapsed = time.time() - t0
            sleep_time = max(0.1, self.interval - elapsed)
            time.sleep(sleep_time)
