from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class ServerAccountCreate:
    name: str
    username: str
    password: str

@dataclass
class ServerAccountUpdate:
    name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[str] = None

@dataclass
class ServerAccountResponse:
    id: int
    name: str
    username: str
    
    token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class ServerAccountStored:
    id: int
    name: str
    username: str
    password: Optional[str] = None
    token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: Optional[datetime] = None
