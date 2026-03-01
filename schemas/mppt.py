from dataclasses import dataclass
from typing import Optional

@dataclass
class MPPTCreate:
    project_id: int
    inverter_id: int
    mppt_index: int
    string_on_mppt: int = 0
    V_mppt: float = 0.0
    I_mppt: float = 0.0
    P_mppt: float = 0.0
    Max_I: float = 0.0
    Max_V: float = 0.0
    Max_P: float = 0.0
    created_at: Optional[str] = None

@dataclass
class MPPTUpdate:
    project_id: Optional[int] = None
    inverter_id: Optional[int] = None
    mppt_index: Optional[int] = None
    string_on_mppt: Optional[int] = None
    V_mppt: Optional[float] = None
    I_mppt: Optional[float] = None
    P_mppt: Optional[float] = None
    Max_I: Optional[float] = None
    Max_V: Optional[float] = None
    Max_P: Optional[float] = None
    created_at: Optional[str] = None

@dataclass
class MPPTResponse:
    id: int
    project_id: int
    inverter_id: int
    mppt_index: int
    string_on_mppt: int
    V_mppt: float
    I_mppt: float
    P_mppt: float
    Max_I: float
    Max_V: float
    Max_P: float
    created_at: Optional[str] = None
