from dataclasses import dataclass
from typing import Optional

@dataclass
class CommConfig:
    driver: str 
    comm_type: str
    host: str = "127.0.0.1"
    port: int = 502
    com_port: str = "COM1"
    baudrate: int = 9600
    databits: int = 8
    parity: str = "N"
    stopbits: int = 1
    timeout: float = 1.0
    slave_id_start: int = 1
    slave_id_end: int = 10
    id: Optional[int] = None