from fastapi import APIRouter, Depends, HTTPException, Body
from database.sqlite_manager import MetadataDB
from schemas.user import UserCreate, UserResponse
from services.local_auth_utils import hash_password
from backend.api.auth_api import get_current_user_id, get_db
from typing import List
import logging

router = APIRouter(prefix="/api/users", tags=["users"])
logger = logging.getLogger(__name__)

@router.post("", response_model=UserResponse)
def create_user(user: UserCreate = Body(..., example={
    "username": "admin",
    "password": "strongpassword123",
    "email": "admin@solardatalogger.local",
    "fullname": "Administrator",
    "phone": "0987654321",
    "role": "admin"
}), db: MetadataDB = Depends(get_db)):
    """Tạo user mới."""
    try:
        # Check if username exists
        if db.get_user_by_username(user.username):
            raise HTTPException(status_code=400, detail="Username already exists")
        
        hashed = hash_password(user.password)
        user_id = db.create_user(user, hashed)
        # Refetch to get created_at
        user_dict = db.get_user_by_username(user.username)
        # Filter out hashed_password
        return UserResponse(
            id=user_dict["id"],
            username=user_dict["username"],
            email=user_dict["email"],
            fullname=user_dict["fullname"],
            phone=user_dict["phone"],
            role=user_dict["role"],
            created_at=user_dict["created_at"]
        )
    except Exception as e:
        logger.error(f"create_user error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=List[UserResponse])
def list_users(db: MetadataDB = Depends(get_db), current_user = Depends(get_current_user_id)):
    """Lấy danh sách user (yêu cầu login)."""
    return db.list_users()
