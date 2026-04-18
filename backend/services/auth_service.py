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
        # RAM cache for active tokens: {account_id: {"access": str, "refresh": str}}
        self._token_cache = {}

    def get_access_token(self, account_id: int, force_refresh: bool = False) -> str | None:
        """Return a valid access token for a specific server account."""
        if not account_id: return None
        
        # 1. Check RAM Cache
        if not force_refresh and account_id in self._token_cache:
            return self._token_cache[account_id]["access"]
            
        # 2. Check Database
        account = self.metadata_db.get_server_account(account_id)
        if not account:
            logger.error(f"[Auth] Server account ID {account_id} not found in DB.")
            return None
            
        if account.token and not force_refresh:
            self._token_cache[account_id] = {"access": account.token, "refresh": account.refresh_token}
            return account.token
            
        # 3. Login if needed
        logger.info(f"[Auth] Getting access token for account {account.username} (ID: {account_id})...")
        if self._login(account_id):
            return self._token_cache[account_id]["access"]
            
        return None

    def refresh_access_token(self, account_id: int) -> bool:
        """Use refresh_token to get a new access_token for an account."""
        account = self.metadata_db.get_server_account(account_id)
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
        if self.refresh_access_token(account_id):
            return self._token_cache.get(account_id, {}).get("access")
        if self._login(account_id):
            return self._token_cache.get(account_id, {}).get("access")
        return None

    def _save_tokens(self, account_id: int, access: str, refresh: str):
        """Save tokens to both RAM cache and Database."""
        self._token_cache[account_id] = {"access": access, "refresh": refresh}
        update_data = ServerAccountUpdate(token=access, refresh_token=refresh)
        self.metadata_db.patch_server_account(account_id, update_data)

    def _login(self, account_id: int) -> bool:
        """Login with OAuth2 password flow using stored credentials."""
        account = self.metadata_db.get_server_account(account_id)
        if not account or not account.username or not account.password:
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
        """Xóa token trong RAM và Database cho một tài khoản."""
        self._token_cache.pop(account_id, None)
        update_data = ServerAccountUpdate(token="", refresh_token="")
        self.metadata_db.patch_server_account(account_id, update_data)
