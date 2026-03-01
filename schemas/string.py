# schemas/mppt.py

from dataclasses import dataclass
from typing import Optional


# =========================
# CREATE
# =========================

@dataclass
class StringCreate:
    project_id: int
    inverter_id: int
    mppt_id: int
    string_id: int
    I_string: float = 0
    max_I: float = 0
    created_at: Optional[str] = None
    


# =========================
# UPDATE
# =========================

@dataclass
class StringUpdate:
    project_id: int
    inverter_id: int
    mppt_id: int
    string_id: int
    I_string: Optional[float] = None
    max_I: Optional[float] = None
    created_at: Optional[str] = None


# =========================
# RESPONSE
# =========================

@dataclass
class StringResponse:
    project_id: int
    inverter_id: int
    mppt_id: int
    string_id: int
    I_string: Optional[float] = None
    max_I: Optional[float] = None
    created_at: Optional[str] = None