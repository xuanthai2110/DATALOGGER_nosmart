from dataclasses import dataclass
from typing import Optional


@dataclass
class ControlScheduleCreate:
    project_id: int
    scope: str
    mode: str
    start_at: str
    end_at: str

    id: Optional[int] = None
    project_name: Optional[str] = None
    inverter_index: Optional[int] = None
    inverter_id: Optional[int] = None
    serial_number: Optional[str] = None
    limit_watts: Optional[float] = None
    limit_percent: Optional[float] = None
    status: str = "SCHEDULED"
    hours: Optional[float] = None
    day: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class ControlScheduleUpdate:
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    scope: Optional[str] = None
    inverter_index: Optional[int] = None
    inverter_id: Optional[int] = None
    serial_number: Optional[str] = None
    mode: Optional[str] = None
    limit_watts: Optional[float] = None
    limit_percent: Optional[float] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    status: Optional[str] = None
    hours: Optional[float] = None
    day: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class ControlScheduleResponse:
    id: int
    project_id: int
    scope: str
    mode: str
    start_at: str
    end_at: str
    status: str

    project_name: Optional[str] = None
    inverter_index: Optional[int] = None
    inverter_id: Optional[int] = None
    serial_number: Optional[str] = None
    limit_watts: Optional[float] = None
    limit_percent: Optional[float] = None
    hours: Optional[float] = None
    day: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
