import json
import logging
import os

import requests

from backend.core import settings as _cfg
from backend.models.server_account import ServerAccountUpdate

API_BASE_URL = _cfg.API_BASE_URL

logger = logging.getLogger(__name__)

MAX_LOGIN_RETRIES = 1


# Xóa bỏ _get_credentials cũ



class AuthService:
    def __init__(self, metadata_db):
        self.metadata_db = metadata_db

    def get_access_token(self, account_id: int, force_refresh: bool = False) -> str | None:
        """Return a valid access token for a specific server account from metadata.db."""
        if not account_id: return None
            
        # 1. Check Database
        account = self.metadata_db.get_server_account_for_auth(account_id)
        if not account:
            logger.error(f"[Auth] Server account ID {account_id} not found in DB.")
            return None
            
        if account.token and not force_refresh:
            return account.token
            
        # 2. Login if needed (this will update the DB)
        logger.info(f"[Auth] Getting access token for account {account.username} (ID: {account_id})...")
        if self._login(account_id):
            # Re-fetch or get from newly updated DB
            account_updated = self.metadata_db.get_server_account_for_auth(account_id)
            return account_updated.token if account_updated else None
            
        return None

    def refresh_access_token(self, account_id: int) -> bool:
        """Use refresh_token to get a new access_token for an account."""
        account = self.metadata_db.get_server_account_for_auth(account_id)
        if not account or not account.refresh_token:
            return False

        try:
            url = f"{API_BASE_URL}/api/auth/refresh"
            response = requests.post(url, json={"refresh_token": account.refresh_token}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                access = data.get("access_token")
                refresh = data.get("refresh_token") or account.refresh_token
                self._save_tokens(account_id, access, refresh)
                return True
            return False
        except Exception as e:
            logger.error(f"[Auth] Refresh error for account {account_id}: {e}")
            return False

    def handle_unauthorized(self, account_id: int) -> str | None:
        """Recover after a 401 response for a specific account."""
        logger.info(f"[Auth] Handling unauthorized for account {account_id}...")
        if self.refresh_access_token(account_id):
            account = self.metadata_db.get_server_account_for_auth(account_id)
            return account.token if account else None
            
        if self._login(account_id):
            account = self.metadata_db.get_server_account_for_auth(account_id)
            return account.token if account else None
            
        return None

    def _save_tokens(self, account_id: int, access: str, refresh: str):
        """Save tokens to Database."""
        update_data = ServerAccountUpdate(token=access, refresh_token=refresh)
        self.metadata_db.patch_server_account(account_id, update_data)

    def _login(self, account_id: int) -> bool:
        """Login with OAuth2 password flow using stored credentials."""
        account = self.metadata_db.get_server_account_for_auth(account_id)
        if not account or not account.username or not account.password:
            logger.warning(f"[Auth] Missing username/password for account ID {account_id}")
            return False

        url = f"{API_BASE_URL}/api/auth/token"
        payload = {
            "username": account.username,
            "password": account.password,
            "grant_type": "password",
        }

        try:
            response = requests.post(url, data=payload, timeout=15)
            if response.status_code == 200:
                data = response.json()
                self._save_tokens(account_id, data.get("access_token"), data.get("refresh_token"))
                logger.info(f"[Auth] Login successful for {account.username}")
                return True
            logger.warning(f"[Auth] Login failed for {account.username}: {response.status_code}")
        except Exception as e:
            logger.error(f"[Auth] Login error for {account.username}: {e}")
            
        return False

    def _clear_tokens(self, account_id: int):
        """Xóa token trong Database cho một tài khoản."""
        update_data = ServerAccountUpdate(token="", refresh_token="")
        self.metadata_db.patch_server_account(account_id, update_data)
