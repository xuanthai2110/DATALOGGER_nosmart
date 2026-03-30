from dataclasses import dataclass
from typing import Optional

@dataclass
class UserCreate:
    username: str
    password: str
    email: Optional[str] = None
    fullname: Optional[str] = None
    phone: Optional[str] = None
    role: str = "user"

@dataclass
class UserResponse:
    id: int
    username: str
    email: Optional[str]
    fullname: Optional[str]
    phone: Optional[str]
    role: str
    created_at: str

@dataclass
class UserLogin:
    username: str
    password: str

@dataclass
class TokenResponse:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
