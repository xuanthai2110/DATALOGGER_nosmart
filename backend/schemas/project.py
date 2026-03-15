# schemas/project.py

from dataclasses import dataclass
from typing import Optional


# =========================
# CREATE
# =========================

@dataclass
class ProjectCreate:
    name: str
    project_index: Optional[int] = None
    elec_meter_no: Optional[str] = None
    elec_price_per_kwh: float = 1783.0
    location: Optional[str] = None
    lat: float = 0.0
    lon: float = 0.0
    capacity_kwp: float = 0.0
    ac_capacity_kw: float = 0.0
    inverter_count: int = 0
    server_id: Optional[int] = None
    server_request_id: Optional[int] = None
    sync_status: str = 'pending'
    created_at: Optional[str] = None


# =========================
# UPDATE
# =========================

@dataclass
class ProjectUpdate:
    id: int
    project_index: Optional[int] = None
    elec_meter_no: Optional[str] = None
    elec_price_per_kwh: Optional[float] = None
    name: Optional[str] = None
    location: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    capacity_kwp: Optional[float] = None
    ac_capacity_kw: Optional[float] = None
    inverter_count: Optional[int] = None
    server_id: Optional[int] = None
    server_request_id: Optional[int] = None
    sync_status: Optional[str] = None
    created_at: Optional[str] = None

# =========================
# RESPONSE
# =========================

@dataclass
class ProjectResponse:
    id: int
    project_index: int
    name: str
    elec_meter_no: Optional[str] = None
    elec_price_per_kwh: float = 1783.0
    location: Optional[str] = None
    lat: float = 0.0
    lon: float = 0.0
    capacity_kwp: float = 0.0
    ac_capacity_kw: float = 0.0
    inverter_count: int = 0
    server_id: Optional[int] = None
    server_request_id: Optional[int] = None
    sync_status: str = 'pending'
    created_at: Optional[str] = None