from dataclasses import dataclass
from typing import Optional

# =========================
# CREATE
# =========================
@dataclass
class ControlScheduleCreate:
    project_id: int
    scope: str
    mode: str
    start_at: str
    end_at: str
    
    inverter_index: Optional[int] = None
    limit_watts: Optional[float] = None
    limit_percent: Optional[float] = None
    status: str = "SCHEDULED"


# =========================
# UPDATE (PATCH)
# =========================
@dataclass
class ControlScheduleUpdate:
    project_id: Optional[int] = None
    scope: Optional[str] = None
    inverter_index: Optional[int] = None
    mode: Optional[str] = None
    limit_watts: Optional[float] = None
    limit_percent: Optional[float] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    status: Optional[str] = None


# =========================
# RESPONSE
# =========================
@dataclass
class ControlScheduleResponse:
    id: int
    project_id: int
    scope: str
    mode: str
    start_at: str
    end_at: str
    status: str

    inverter_index: Optional[int] = None
    limit_watts: Optional[float] = None
    limit_percent: Optional[float] = None
    created_at: Optional[str] = None
