from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from backend.db_manager import MetadataDB, RealtimeDB, CacheDB
from backend.services.local_auth_utils import create_access_token, create_refresh_token, verify_password, decode_token
from backend.core import settings as app_config
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class RefreshRequest(BaseModel):
    refresh_token: str

from backend.services.user_service import UserService

def get_user_service() -> UserService:
    # Cần cắm MetadataDB vào. Tốt nhất là khởi tạo MetadataDB từ config.
    from backend.db_manager import MetadataDB
    return UserService(metadata_db=MetadataDB(app_config.METADATA_DB))

async def get_current_user(token: str = Depends(oauth2_scheme), user_svc: UserService = Depends(get_user_service)):
    payload = decode_token(token)
    if not payload or payload.get("sub") is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = int(payload.get("sub"))
    user = user_svc.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def get_current_user_id(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    if not payload or payload.get("sub") is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return int(payload.get("sub"))

@router.get("/me")
async def get_me(current_user = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "role": current_user["role"],
        "fullname": current_user.get("fullname")
    }

@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), user_svc: UserService = Depends(get_user_service)):
    user = user_svc.get_user_by_name(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": str(user["id"]), "role": user["role"]})
    refresh_token = create_refresh_token(data={"sub": str(user["id"])})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/refresh", response_model=Token)
async def refresh(body: RefreshRequest, user_svc: UserService = Depends(get_user_service)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    user_id = payload.get("sub")
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
