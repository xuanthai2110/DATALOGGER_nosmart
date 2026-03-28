from dataclasses import dataclass
from typing import Optional

# =========================
# PROJECT REALTIME
# =========================
@dataclass
class ProjectRealtimeCreate:
    project_id: int
    Temp_C: float = 0
    P_ac: float = 0
    P_dc: float = 0
    E_daily: float = 0
    E_monthly: float = 0
    denta_E_monthly: float = 0
    E_total: float = 0
    severity: str = "STABLE"
    created_at: str = ""


@dataclass
class ProjectRealtimeResponse:
    id: int
    project_id: int
    Temp_C: float = 0
    P_ac: float = 0
    P_dc: float = 0
    E_daily: float = 0
    E_monthly: float = 0
    denta_E_monthly: float = 0
    E_total: float = 0
    severity: str = "STABLE"
    created_at: str = ""

# =========================
# INVERTER AC REALTIME
# =========================
@dataclass
class InverterACRealtimeCreate:
    project_id: int
    inverter_id: int
    IR: float
    Temp_C: float
    P_ac: float
    Q_ac: float
    V_a: float
    V_b: float
    V_c: float
    I_a: float
    I_b: float
    I_c: float
    PF: float
    H: float
    E_daily: float
    E_monthly: float
    E_total: float
    created_at: Optional[str] = None

@dataclass
class InverterACRealtimeResponse:
    id: int
    project_id: int
    inverter_id: int
    IR: float
    Temp_C: float
    P_ac: float
    Q_ac: float
    V_a: float
    V_b: float
    V_c: float
    I_a: float
    I_b: float
    I_c: float
    PF: float
    H: float
    E_daily: float
    E_monthly: float
    E_total: float
    created_at: Optional[str] = None    

# =========================
# INVERTER ERRORS
# =========================
@dataclass
class InverterErrorCreate:
    project_id: int
    inverter_id: int
    fault_code: int
    fault_description: str
    repair_instruction: str
    severity: str
    created_at: Optional[str] = None

@dataclass
class InverterErrorResponse:
    id: int
    project_id: int
    inverter_id: int
    fault_code: int
    fault_description: str
    repair_instruction: str
    severity: str
    created_at: Optional[str] = None
@dataclass
class mpptRealtimeCreate:
    project_id: int
    inverter_id: int
    mppt_index: int
    string_on_mppt: int = 0
    V_mppt: float = 0
    I_mppt: float = 0
    P_mppt: float = 0
    Max_I: float = 0
    Max_P: float = 0
    Max_V: float = 0
    created_at: Optional[str] = None

@dataclass
class mpptRealtimeResponse:
    id: int
    project_id: int
    inverter_id: int
    mppt_index: int
    string_on_mppt: int = 0
    V_mppt: float = 0
    I_mppt: float = 0
    P_mppt: float = 0
    Max_I: float = 0
    Max_P: float = 0
    Max_V: float = 0
    created_at: Optional[str] = None
@dataclass
class stringRealtimeCreate:
    project_id: int
    inverter_id: int
    mppt_id: int
    string_id: int
    I_string: float = 0
    max_I: float = 0
    created_at: Optional[str] = None

@dataclass
class stringRealtimeResponse:
    id: int
    project_id: int
    inverter_id: int
    mppt_id: int
    string_id: int
    I_string: float = 0
    max_I: float = 0
    created_at: Optional[str] = None
    