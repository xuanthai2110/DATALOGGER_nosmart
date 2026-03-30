from dataclasses import dataclass
from typing import Optional

@dataclass
class CommConfig:
    driver: str 
    comm_type: str

    host: Optional[str] = None
    port: Optional[int] = None

    com_port: Optional[str] = None
    baudrate: Optional[int] = None
    databits: Optional[int] = None
    parity: Optional[str] = None
    stopbits: Optional[int] = None

    timeout: Optional[float] = None
    slave_id_start: Optional[int] = None
    slave_id_end: Optional[int] = None

    id: Optional[int] = None