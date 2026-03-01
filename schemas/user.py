from dataclasses import dataclass
from typing import Optional

# =========================
# CREATE
# =========================
@dataclass
class UserCreate:
    username: str
    password: str
    role: str
# =========================
# UPDATE
# =========================
@dataclass
class UserUpdate:
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
# =========================
# RESPONSE
# =========================
@dataclass
class UserResponse:
    id: int
    username: str
    role: str
