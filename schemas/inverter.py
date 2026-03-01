from dataclasses import dataclass
from typing import Optional

@dataclass
class InverterCreate:
    inverter_index: int
    project_id: int
    brand: str
    model: str
    serial_number: str
    capacity_kw: float
    mppt_count: int
    firmware_version: str
    phase_count: int
    string_count: int
    rate_dc_kwp: float
    rate_ac_kw: float
    is_active: bool
    usage_start_at: Optional[str] = None
    usage_end_at: Optional[str] = None
    replaced_by_id: Optional[int] = None

@dataclass
class InverterUpdate:
    inverter_index: Optional[int] = None
    project_id: Optional[int] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    capacity_kw: Optional[float] = None
    mppt_count: Optional[int] = None
    firmware_version: Optional[str] = None
    phase_count: Optional[int] = None
    string_count: Optional[int] = None
    rate_dc_kwp: Optional[float] = None
    rate_ac_kw: Optional[float] = None
    is_active: Optional[bool] = None
    usage_start_at: Optional[str] = None
    usage_end_at: Optional[str] = None
    replaced_by_id: Optional[int] = None

@dataclass
class InverterResponse:
    id: int
    inverter_index: int
    project_id: int
    brand: str
    model: str
    serial_number: str
    capacity_kw: float
    mppt_count: int
    firmware_version: str
    phase_count: int
    string_count: int
    rate_dc_kwp: float
    rate_ac_kw: float
    is_active: bool
    usage_start_at: Optional[str] = None
    usage_end_at: Optional[str] = None
    replaced_by_id: Optional[int] = None
