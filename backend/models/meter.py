from dataclasses import dataclass
from typing import Optional


# =========================
# CREATE
# =========================
@dataclass
class MeterCreate:
    """Tạo mới Meter — thiết bị đo lường tại điểm đấu nối lưới."""
    # ===== Identity (bắt buộc) =====
    project_id: int
    brand: str              # "Acrel", "Eastron", "Schneider", "ABB"...
    model: str              # "SDM630", "PM5110", "DTSD1352"...
    serial_number: str

    # ===== Configuration =====
    slave_id: Optional[int] = None
    comm_id: Optional[int] = None       # Liên kết comm config (RTU/TCP)
    ct_ratio: Optional[float] = 1.0     # Tỉ lệ biến dòng
    is_active: bool = True


# =========================
# UPDATE (PATCH)
# =========================
@dataclass
class MeterUpdate:
    project_id: Optional[int] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    slave_id: Optional[int] = None
    comm_id: Optional[int] = None
    ct_ratio: Optional[float] = None
    is_active: Optional[bool] = None


# =========================
# RESPONSE (READ)
# =========================
@dataclass
class MeterResponse:
    id: int
    project_id: int
    brand: str
    model: str
    serial_number: str
    slave_id: Optional[int]
    comm_id: Optional[int]
    ct_ratio: Optional[float] = 1.0
    is_active: Optional[bool] = True