import json
import logging
from typing import Callable, Iterable, Optional

import paho.mqtt.client as mqtt

from backend.services.schedule_service import ScheduleService


logger = logging.getLogger(__name__)


class MqttSubscriber:
    def __init__(
        self,
        broker: str,
        port: int,
        schedule_service: ScheduleService,
        project_id: int = None,
        username: str = None,
        password: str = None,
        project_server_ids_provider: Optional[Callable[[], Iterable[int]]] = None,
    ):
        self.broker = broker
        self.port = port
        self.schedule_service = schedule_service
        self.project_id_filter = project_id
        self.username = username
        self.password = password
        self.project_server_ids_provider = project_server_ids_provider
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def _get_subscription_topics(self):
        if self.project_id_filter is not None:
            return [f"controls/projects/{self.project_id_filter}/schedules/#"]

        if not self.project_server_ids_provider:
            return []

        try:
            server_ids = self.project_server_ids_provider() or []
        except Exception as e:
            logger.error(f"[MQTT] Failed to load project server_ids for subscription: {e}")
            return []

        topics = []
        seen = set()
        for server_id in server_ids:
            if server_id in (None, ""):
                continue
            try:
                normalized = int(server_id)
            except (TypeError, ValueError):
                logger.warning(f"[MQTT] Ignoring invalid project server_id for subscription: {server_id}")
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            topics.append(f"controls/projects/{normalized}/schedules/#")
        return topics

    def connect(self):
        try:
            if self.username:
                self.client.username_pw_set(self.username, self.password)
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            logger.info(f"[MQTT] Connected to {self.broker}:{self.port}")
        except Exception as e:
            logger.error(f"[MQTT] Connection failed: {e}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            topics = self._get_subscription_topics()
            if not topics:
                logger.warning("[MQTT] No project server_id available, schedule subscriber did not subscribe to any topic.")
                return

            for topic in topics:
                self.client.subscribe(topic)
                logger.info(f"[MQTT] Subscribed to {topic}")
        else:
            logger.error(f"[MQTT] Connect return code {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            event = payload.get("event")
            schedule_data = payload.get("schedule") or {}
            schedule_id = schedule_data.get("id")

            if not event or schedule_id is None:
                return

            if event in ("schedule_created", "schedule_updated"):
                synced = self.schedule_service.sync_schedule_from_server(schedule_id)
                if not synced:
                    logger.error(f"[MQTT] Failed to sync {event} for schedule {schedule_id}")
            elif event == "schedule_deleted":
                self.schedule_service.delete(schedule_id)

            logger.info(f"[MQTT] Processed {event} for schedule {schedule_id}")

        except Exception as e:
            logger.error(f"[MQTT] Event Parse Error: {e}")
