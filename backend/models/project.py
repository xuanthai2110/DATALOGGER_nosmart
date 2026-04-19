from dataclasses import dataclass
from typing import Optional
from datetime import datetime

# =========================
# CREATE
# =========================
@dataclass
class ProjectCreate:
    # ===== Required =====
    name: str

    # ===== Optional info =====
    elec_meter_no: Optional[str] = None
    elec_price_per_kwh: Optional[float] = None

    location: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

    # ===== Electrical =====
    capacity_kwp: Optional[float] = None
    ac_capacity_kw: Optional[float] = None
    inverter_count: Optional[int] = None

    # ===== Sync =====
    server_id: Optional[int] = None
    server_request_id: Optional[int] = None
    server_account_id: Optional[int] = None
    evn_slave_id: Optional[int] = 1
    evn_project_id: Optional[int] = None


# =========================
# UPDATE (PATCH)
# =========================
@dataclass
class ProjectUpdate:
    # KHÔNG nên có id ở đây (lấy từ URL)

    project_index: Optional[int] = None
    name: Optional[str] = None

    elec_meter_no: Optional[str] = None
    elec_price_per_kwh: Optional[float] = None

    location: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

    capacity_kwp: Optional[float] = None
    ac_capacity_kw: Optional[float] = None
    inverter_count: Optional[int] = None

    server_id: Optional[int] = None
    server_request_id: Optional[int] = None
    server_account_id: Optional[int] = None
    sync_status: Optional[str] = None

    # ===== EVN =====
    evn_slave_id: Optional[int] = None
    evn_project_id: Optional[int] = None


# =========================
# RESPONSE
# =========================
@dataclass
class ProjectResponse:
    id: int
    project_index: Optional[int] = None

    name: str = ""

    elec_meter_no: Optional[str] = None
    elec_price_per_kwh: Optional[float] = None

    location: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

    capacity_kwp: Optional[float] = None
    ac_capacity_kw: Optional[float] = None
    inverter_count: Optional[int] = None

    # ===== Sync =====
    server_id: Optional[int] = None
    server_request_id: Optional[int] = None
    server_account_id: Optional[int] = None
    sync_status: str = "pending"

    # ===== EVN =====
    evn_slave_id: Optional[int] = 0
    evn_project_id: Optional[int] = None

    # ===== Metadata =====
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None