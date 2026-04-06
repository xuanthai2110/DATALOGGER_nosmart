import json
import logging
import paho.mqtt.client as mqtt
from backend.models.schedule import ControlScheduleCreate, ControlScheduleUpdate
from backend.services.schedule_service import ScheduleService

logger = logging.getLogger(__name__)

class MqttSubscriber:
    def __init__(self, broker: str, port: int, schedule_service: ScheduleService, project_id: int = None):
        self.broker = broker
        self.port = port
        self.schedule_service = schedule_service
        self.project_id_filter = project_id # can be None for all projects
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def connect(self):
        try:
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
            topic = "controls/projects/+/schedules/#"
            if self.project_id_filter:
                topic = f"controls/projects/{self.project_id_filter}/schedules/#"
            self.client.subscribe(topic)
            logger.info(f"[MQTT] Subscribed to {topic}")
        else:
            logger.error(f"[MQTT] Connect return code {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            event = payload.get("event")
            schedule_data = payload.get("schedule")
            
            if not schedule_data or not event:
                return
                
            if event == "schedule_created":
                s = ControlScheduleCreate(**schedule_data)
                self.schedule_service.create(s)
            elif event == "schedule_updated":
                s_id = schedule_data.get("id")
                if "id" in schedule_data:
                    del schedule_data["id"]
                s = ControlScheduleUpdate(**schedule_data)
                self.schedule_service.update(s_id, s)
            elif event == "schedule_deleted":
                s_id = schedule_data.get("id")
                self.schedule_service.delete(s_id)
                
            logger.info(f"[MQTT] Processed {event} for schedule {schedule_data.get('id')}")
                
        except Exception as e:
            logger.error(f"[MQTT] Event Parse Error: {e}")
