import json
import logging
import os

import requests

from backend.core import settings as _cfg

API_BASE_URL = _cfg.API_BASE_URL
TOKEN_FILE = _cfg.TOKEN_FILE

logger = logging.getLogger(__name__)

MAX_LOGIN_RETRIES = 1


def _get_credentials() -> tuple[str, str]:
    # Read env from settings now
    from backend.core import settings
    return settings.API_USERNAME, settings.API_PASSWORD



class AuthService:
    def __init__(self):
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self._load_tokens()

    def get_access_token(self) -> str | None:
        """Return a valid access token if available."""
        if not self.access_token:
            self._login()
        return self.access_token

    def refresh_access_token(self) -> bool:
        """Use refresh_token to get a new access_token."""
        if not self.refresh_token:
            logger.warning("[Auth] No refresh_token available, will re-login")
            return False

        try:
            url = f"{API_BASE_URL}/api/auth/refresh"
            response = requests.post(
                url,
                json={"refresh_token": self.refresh_token},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                new_refresh = data.get("refresh_token")
                if new_refresh:
                    self.refresh_token = new_refresh

                self._save_tokens()
                logger.info("[Auth] Access token refreshed successfully")
                return True

            logger.warning(
                f"[Auth] Refresh failed (status={response.status_code}), will re-login"
            )
            self._clear_tokens()
            return False
        except Exception as e:
            logger.error(f"[Auth] Refresh error: {e}")
            self._clear_tokens()
            return False

    def handle_unauthorized(self) -> str | None:
        """Recover after a 401 response from the API."""
        logger.info("[Auth] Handling 401 - attempting token refresh...")

        if self.refresh_access_token():
            return self.access_token

        logger.info("[Auth] Refresh failed, re-logging in...")
        if self._login():
            return self.access_token

        logger.error("[Auth] All authentication attempts failed, giving up")
        return None

    def _load_tokens(self):
        """Load tokens from disk if present."""
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, "r") as f:
                    data = json.load(f)
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                logger.info("[Auth] Tokens loaded from disk")
            except Exception as e:
                logger.error(f"[Auth] Error loading tokens: {e}")

    def _save_tokens(self):
        """Persist tokens to disk."""
        try:
            data = {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
            }
            with open(TOKEN_FILE, "w") as f:
                json.dump(data, f)
            logger.info("[Auth] Tokens saved to disk")
        except Exception as e:
            logger.error(f"[Auth] Error saving tokens: {e}")

    def _login(self) -> bool:
        """Login with OAuth2 password flow."""
        api_username, api_password = _get_credentials()
        if not api_username or not api_password:
            logger.warning(
                "[Auth] API_USERNAME / API_PASSWORD not set in environment. "
                "Upload to server will fail. Set env vars before running."
            )
            return False

        url = f"{API_BASE_URL}/api/auth/token"
        payload = {
            "username": api_username,
            "password": api_password,
            "grant_type": "password",
        }

        for attempt in range(1, MAX_LOGIN_RETRIES + 2):
            try:
                response = requests.post(url, data=payload, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                    self._save_tokens()
                    logger.info("[Auth] Login successful")
                    return True

                logger.warning(
                    f"[Auth] Login attempt {attempt} failed (status={response.status_code})"
                )
            except Exception as e:
                logger.warning(f"[Auth] Login attempt {attempt} error: {e}")

            if attempt <= MAX_LOGIN_RETRIES:
                logger.info(f"[Auth] Retrying login ({attempt}/{MAX_LOGIN_RETRIES})...")

        logger.error("[Auth] Login failed after all retries, skipping upload")
        self._clear_tokens()
        return False

    def _clear_tokens(self):
        self.access_token = None
        self.refresh_token = None
        if os.path.exists(TOKEN_FILE):
            try:
                os.remove(TOKEN_FILE)
            except Exception:
                pass
