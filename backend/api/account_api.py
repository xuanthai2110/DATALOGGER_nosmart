from fastapi import APIRouter, Depends, Body, HTTPException
from fastapi.responses import JSONResponse
from backend.db_manager import MetadataDB
from backend.models.server_account import ServerAccountCreate, ServerAccountUpdate, ServerAccountResponse
from backend.api.auth_api import get_current_user_id
from backend.core import settings as app_config
from dataclasses import asdict
import logging

router = APIRouter(tags=["accounts"])
logger = logging.getLogger(__name__)

def get_metadata_db() -> MetadataDB:
    return MetadataDB(app_config.METADATA_DB)

@router.get("", response_model=list[ServerAccountResponse])
def list_accounts(db: MetadataDB = Depends(get_metadata_db), current_user = Depends(get_current_user_id)):
    """Lấy danh sách các tài khoản server."""
    try:
        accounts = db.get_server_accounts()
        return [ServerAccountResponse(**asdict(a)) for a in accounts]
    except Exception as e:
        logger.error(f"list_accounts error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", response_model=ServerAccountResponse)
def create_account(account: ServerAccountCreate, db: MetadataDB = Depends(get_metadata_db), current_user = Depends(get_current_user_id)):
    """Tạo tài khoản server mới."""
    try:
        new_account = db.upsert_server_account(account)
        return ServerAccountResponse(**asdict(new_account))
    except Exception as e:
        logger.error(f"create_account error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{account_id}", response_model=ServerAccountResponse)
def get_account(account_id: int, db: MetadataDB = Depends(get_metadata_db), current_user = Depends(get_current_user_id)):
    """Lấy thông tin chi tiết một tài khoản."""
    account = db.get_server_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return ServerAccountResponse(**asdict(account))

@router.patch("/{account_id}", response_model=ServerAccountResponse)
def update_account(account_id: int, account: ServerAccountUpdate, db: MetadataDB = Depends(get_metadata_db), current_user = Depends(get_current_user_id)):
    """Cập nhật tài khoản server."""
    try:
        # Convert to Create model for upsert (it handles updates if id is passed internally if we modify it, 
        # but MetadataDB.upsert_server_account expects ServerAccountCreate and optional id)
        updated = db.upsert_server_account(account, account_id=account_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Account not found")
        return ServerAccountResponse(**asdict(updated))
    except Exception as e:
        logger.error(f"update_account error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{account_id}")
def delete_account(account_id: int, db: MetadataDB = Depends(get_metadata_db), current_user = Depends(get_current_user_id)):
    """Xóa tài khoản server."""
    try:
        # Check if any project is using this account
        projects = db.get_projects()
        using_projects = [p for p in projects if p.server_account_id == account_id]
        if using_projects:
            raise HTTPException(status_code=400, detail=f"Cannot delete account. It is being used by {len(using_projects)} projects.")
            
        success = db.delete_server_account(account_id)
        if not success:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_account error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
