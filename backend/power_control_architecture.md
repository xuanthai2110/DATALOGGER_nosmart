# Power Control Scheduling System Architecture

## Overview

This document defines the architecture for a Power Control system using
MQTT, scheduling, execution engine, and inverter control.

------------------------------------------------------------------------

## 1. MQTT Subscriber

### Topic

    controls/projects/{project_id}/schedules/#

### Payload

``` json
{
  "event": "schedule_created | schedule_updated | schedule_deleted",
  "schedule": {
    "id": 1,
    "project_id": 1,
    "scope": "PROJECT | INVERTER",
    "inverter_index": 0,
    "mode": "MAXP | LIMIT_PERCENT",
    "limit_watts": 10000,
    "limit_percent": 0.8,
    "start_at": "ISO8601",
    "end_at": "ISO8601",
    "status": "SCHEDULED"
  },
  "timestamp": "ISO8601"
}
```

### Logic

``` python
def on_message(payload):
    event = payload["event"]
    schedule = payload["schedule"]

    if event == "schedule_created":
        schedule_service.create(schedule)

    elif event == "schedule_updated":
        schedule_service.update(schedule)

    elif event == "schedule_deleted":
        schedule_service.delete(schedule["id"])
```

------------------------------------------------------------------------

## 2. Schedule Service

### Purpose

-   Store schedules
-   Manage state

### Data Model

``` python
class ControlSchedule:
    id: int
    project_id: int
    scope: str
    inverter_index: Optional[int]
    mode: str
    limit_watts: Optional[float]
    limit_percent: Optional[float]
    start_at: datetime
    end_at: datetime
    status: str
```

------------------------------------------------------------------------

## 3. Execution Engine

### Loop

``` python
while True:
    now = datetime.now()

    for s in schedule_service.get_all():
        if s.start_at <= now <= s.end_at:
            if s.status != "RUNNING":
                execute_start(s)

        elif now > s.end_at:
            if s.status == "RUNNING":
                execute_stop(s)

    sleep(1)
```

------------------------------------------------------------------------

## 4. Control Service

``` python
class ControlService:

    def apply(self, schedule):
        if schedule.mode == "MAXP":
            self.set_max_power(schedule)

        elif schedule.mode == "LIMIT_PERCENT":
            self.set_percent(schedule)

    def reset(self, schedule):
        self.set_percent(1.0)
```

------------------------------------------------------------------------

## 5. API Update

### Endpoint

    PATCH /api/control-schedules/{schedule_id}

### Payload

``` json
{
  "status": "RUNNING","COMPLETED","CANCELED","FAILED" }
}
```

------------------------------------------------------------------------

## Flow

MQTT → Schedule Service → Execution Engine → Control → API Update

------------------------------------------------------------------------

## Rules

-   Separate layers
-   Non-blocking
-   Idempotent
-   Fail-safe
