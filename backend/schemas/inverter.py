from dataclasses import dataclass
from typing import Optional
from datetime import datetime

# =========================
# CREATE
# =========================
@dataclass
class InverterCreate:
    # ===== Identity (bắt buộc) =====
    project_id: int
    brand: str
    model: str
    serial_number: str

    # ===== Communication (rất quan trọng) =====
    slave_id: Optional[int] = None
    comm_id: Optional[int] = None

    # ===== Electrical config =====
    capacity_kw: Optional[float] = None
    rate_dc_kwp: Optional[float] = None
    rate_ac_kw: Optional[float] = None
    mppt_count: Optional[int] = None
    string_count: Optional[int] = None
    phase_count: Optional[int] = None
    # ===== Optional info =====
    firmware_version: Optional[str] = None
    strings_per_mppt: Optional[int] = None

    # ===== Logic =====
    inverter_index: Optional[int] = None
    is_active: bool = True

    # ===== Lifecycle =====
    usage_start_at: Optional[datetime] = None
    usage_end_at: Optional[datetime] = None
    replaced_by_id: Optional[int] = None


# =========================
# UPDATE (PATCH)
# =========================
@dataclass
class InverterUpdate:
    # ===== Identity =====
    project_id: Optional[int] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None

    # ===== Communication =====
    slave_id: Optional[int] = None
    comm_id: Optional[int] = None

    # ===== Electrical config =====
    capacity_kw: Optional[float] = None
    rate_dc_kwp: Optional[float] = None
    rate_ac_kw: Optional[float] = None
    mppt_count: Optional[int] = None
    string_count: Optional[int] = None
    phase_count: Optional[int] = None
    # ===== Optional info =====
    firmware_version: Optional[str] = None
    strings_per_mppt: Optional[int] = None

    # ===== Logic =====
    inverter_index: Optional[int] = None
    is_active: Optional[bool] = None

    # ===== Lifecycle =====
    usage_start_at: Optional[datetime] = None
    usage_end_at: Optional[datetime] = None
    replaced_by_id: Optional[int] = None


# =========================
# RESPONSE (READ)
# =========================
@dataclass
class InverterResponse:
    # ===== Primary =====
    id: int
    project_id: int

    # ===== Identity =====
    brand: str
    model: str
    serial_number: str

    # ===== Communication =====
    slave_id: Optional[int]
    comm_id: Optional[int]

    # ===== Electrical config =====
    capacity_kw: Optional[float]
    rate_dc_kwp: Optional[float]
    rate_ac_kw: Optional[float]
    mppt_count: Optional[int]
    string_count: Optional[int]
    phase_count: Optional[int]
    # ===== Optional info =====
    firmware_version: Optional[str]
    strings_per_mppt: Optional[int] = None

    # ===== Logic =====
    inverter_index: Optional[int] = None
    is_active: Optional[bool] = None

    # ===== Lifecycle =====
    usage_start_at: Optional[datetime] = None
    usage_end_at: Optional[datetime] = None
    replaced_by_id: Optional[int] = None

    # ===== System / Sync =====
    server_id: Optional[int] = None
    server_request_id: Optional[int] = None
    sync_status: Optional[str] = None

    # ===== Optional info moved to end to avoid TypeError =====
    strings_per_mppt: Optional[int] = None