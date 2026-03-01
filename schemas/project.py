# schemas/project.py

from dataclasses import dataclass
from typing import Optional


# =========================
# CREATE
# =========================

@dataclass
class ProjectCreate:
    elec_meter_no: str
    elec_price_per_kwh: float
    name: str
    location: str
    lat: float
    lon: float
    capacity_kwp: float
    ac_capacity_kw: float
    inverter_count: int
    created_at: Optional[str] = None


# =========================
# UPDATE
# =========================

@dataclass
class ProjectUpdate:
    id: int
    elec_meter_no: Optional[str] = None
    elec_price_per_kwh: Optional[float] = None
    name: Optional[str] = None
    location: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    capacity_kwp: Optional[float] = None
    ac_capacity_kw: Optional[float] = None
    inverter_count: Optional[int] = None
    created_at: Optional[str] = None

# =========================
# RESPONSE
# =========================

@dataclass
class ProjectResponse:
    id: int
    elec_meter_no: str
    elec_price_per_kwh: float
    name: str
    location: str
    lat: float
    lon: float
    capacity_kwp: float
    ac_capacity_kw: float
    inverter_count: int
    created_at: Optional[str] = None