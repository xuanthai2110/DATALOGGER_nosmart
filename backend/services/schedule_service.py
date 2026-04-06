from typing import List, Optional
import logging
import time

import requests

from backend.core.config import API_BASE_URL
from backend.db_manager.realtime import RealtimeDB
from backend.models.schedule import ControlScheduleCreate, ControlScheduleUpdate, ControlScheduleResponse
from backend.services.auth_service import AuthService


logger = logging.getLogger(__name__)


class ScheduleService:
    def __init__(self, db: RealtimeDB):
        self.db = db
        self.auth = AuthService()
        self.fetch_retry_count = 5
        self.fetch_retry_delay_sec = 0.5

    def _short_body(self, value, limit: int = 500) -> str:
        text = value if isinstance(value, str) else str(value)
        return text if len(text) <= limit else text[:limit] + "...<truncated>"

    def _get_headers(self) -> Optional[dict]:
        token = self.auth.get_access_token()
        if not token:
            logger.error("[ScheduleService] Cannot call server schedule API because auth token is unavailable.")
            return None
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _build_local_schedule(self, remote_schedule: dict) -> ControlScheduleCreate:
        maxp_kw = remote_schedule.get("maxp_kw")
        return ControlScheduleCreate(
            id=remote_schedule.get("id"),
            project_id=remote_schedule.get("project_id"),
            project_name=remote_schedule.get("project_name"),
            scope=remote_schedule.get("scope"),
            mode=remote_schedule.get("mode"),
            start_at=remote_schedule.get("start_at"),
            end_at=remote_schedule.get("end_at"),
            status=remote_schedule.get("status", "SCHEDULED"),
            inverter_id=remote_schedule.get("inverter_id"),
            serial_number=remote_schedule.get("serial_number"),
            limit_watts=None if maxp_kw is None else float(maxp_kw) * 1000.0,
            limit_percent=remote_schedule.get("percent"),
            hours=remote_schedule.get("hours"),
            day=remote_schedule.get("day"),
            created_at=remote_schedule.get("created_at"),
            updated_at=remote_schedule.get("updated_at"),
        )

    def get_all(self) -> List[ControlScheduleResponse]:
        return self.db.get_all_schedules()

    def get(self, schedule_id: int) -> Optional[ControlScheduleResponse]:
        return self.db.get_schedule(schedule_id)

    def create(self, data: ControlScheduleCreate) -> ControlScheduleResponse:
        logger.info(f"[ScheduleService] Creating schedule: {data}")
        return self.db.upsert_schedule(data, schedule_id=data.id)

    def update(self, schedule_id: int, data: ControlScheduleUpdate):
        logger.info(f"[ScheduleService] Updating schedule {schedule_id}")
        self.db.patch_schedule(schedule_id, data)

    def update_status(self, schedule_id: int, status: str, sync_remote: bool = False):
        logger.info(f"[ScheduleService] Updating status of schedule {schedule_id} to {status}")
        self.db.patch_schedule(schedule_id, ControlScheduleUpdate(status=status))
        if sync_remote:
            self.patch_remote_status(schedule_id, status)

    def delete(self, schedule_id: int):
        logger.info(f"[ScheduleService] Deleting schedule {schedule_id}")
        self.db.delete_schedule(schedule_id)

    def fetch_remote_schedule(self, schedule_id: int) -> Optional[dict]:
        headers = self._get_headers()
        if not headers:
            return None

        base = API_BASE_URL.rstrip("/")
        url = f"{base}/api/control-schedules/{schedule_id}"
        for attempt in range(1, self.fetch_retry_count + 1):
            logger.info("[ScheduleService] GET %s attempt=%s/%s", url, attempt, self.fetch_retry_count)
            try:
                response = requests.get(url, headers=headers, timeout=10)
                logger.info(
                    "[ScheduleService] GET %s -> status=%s body=%s",
                    url,
                    response.status_code,
                    self._short_body(response.text),
                )
                if response.status_code == 200:
                    return response.json()

                is_retryable_404 = response.status_code == 404 and attempt < self.fetch_retry_count
                if is_retryable_404:
                    logger.warning(
                        "[ScheduleService] Remote schedule %s not visible yet. Retrying in %.1fs...",
                        schedule_id,
                        self.fetch_retry_delay_sec,
                    )
                    time.sleep(self.fetch_retry_delay_sec)
                    continue

                logger.error(
                    "[ScheduleService] Fetch remote schedule %s failed (status=%s): %s",
                    schedule_id,
                    response.status_code,
                    response.text,
                )
                return None
            except Exception as e:
                if attempt < self.fetch_retry_count:
                    logger.warning(
                        "[ScheduleService] Fetch remote schedule %s attempt %s error: %s. Retrying in %.1fs...",
                        schedule_id,
                        attempt,
                        e,
                        self.fetch_retry_delay_sec,
                    )
                    time.sleep(self.fetch_retry_delay_sec)
                    continue
                logger.error(f"[ScheduleService] Fetch remote schedule {schedule_id} error: {e}")
                return None

    def sync_schedule_from_server(self, schedule_id: int) -> Optional[ControlScheduleResponse]:
        remote_schedule = self.fetch_remote_schedule(schedule_id)
        if not remote_schedule:
            return None

        if remote_schedule.get("scope") == "INVERTER" and not remote_schedule.get("serial_number"):
            logger.error(
                "[ScheduleService] Remote inverter schedule %s has no serial_number; control will be rejected.",
                schedule_id,
            )

        local_schedule = self._build_local_schedule(remote_schedule)
        logger.info(f"[ScheduleService] Synced schedule {schedule_id} from server")
        return self.create(local_schedule)

    def patch_remote_status(self, schedule_id: int, status: str) -> bool:
        headers = self._get_headers()
        if not headers:
            return False

        base = API_BASE_URL.rstrip("/")
        url = f"{base}/api/control-schedules/{schedule_id}"
        payload = {"status": status}
        logger.info("[ScheduleService] PATCH %s payload=%s", url, payload)
        try:
            response = requests.patch(url, json=payload, headers=headers, timeout=10)
            logger.info(
                "[ScheduleService] PATCH %s -> status=%s body=%s",
                url,
                response.status_code,
                self._short_body(response.text),
            )
            if response.status_code not in (200, 201):
                logger.error(
                    "[ScheduleService] Patch remote schedule %s -> %s failed (status=%s): %s",
                    schedule_id,
                    status,
                    response.status_code,
                    response.text,
                )
                return False
            logger.info(f"[ScheduleService] Patched remote schedule {schedule_id} -> {status}")
            return True
        except Exception as e:
            logger.error(f"[ScheduleService] Patch remote schedule {schedule_id} -> {status} error: {e}")
            return False
