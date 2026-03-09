import requests
import logging
from config import API_BASE_URL, API_USERNAME, API_PASSWORD

logger = logging.getLogger(__name__)

MAX_LOGIN_RETRIES = 1  # số lần retry khi login thất bại


class AuthService:
    def __init__(self):
        self.access_token: str | None = None
        self.refresh_token: str | None = None

    # ------------------------------------------------------------------
    # PUBLIC
    # ------------------------------------------------------------------

    def get_access_token(self) -> str | None:
        """Trả về access token hợp lệ.
        Nếu chưa có → login.
        """
        if not self.access_token:
            self._login()
        return self.access_token

    def refresh_access_token(self) -> bool:
        """Dùng refresh_token để lấy access_token mới.
        Trả về True nếu thành công, False nếu thất bại.
        """
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
                # Một số API trả về refresh_token mới kèm theo
                new_refresh = data.get("refresh_token")
                if new_refresh:
                    self.refresh_token = new_refresh
                logger.info("[Auth] Access token refreshed successfully")
                return True
            else:
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
        """Gọi khi nhận 401 từ API.
        Thứ tự: refresh → re-login → retry login → None.
        Trả về access_token mới nếu thành công, None nếu không phục hồi được.
        """
        logger.info("[Auth] Handling 401 - attempting token refresh...")

        # Bước 1: thử refresh
        if self.refresh_access_token():
            return self.access_token

        # Bước 2: refresh thất bại → login lại
        logger.info("[Auth] Refresh failed, re-logging in...")
        if self._login():
            return self.access_token

        logger.error("[Auth] All authentication attempts failed, giving up")
        return None

    # ------------------------------------------------------------------
    # PRIVATE
    # ------------------------------------------------------------------

    def _login(self) -> bool:
        """Thực hiện login với retry MAX_LOGIN_RETRIES lần.
        Trả về True nếu thành công.
        Dùng OAuth2 Password Flow: POST /api/auth/token với form-encoded body.
        """
        url = f"{API_BASE_URL}/api/auth/token"
        # OAuth2 Password Flow yêu cầu application/x-www-form-urlencoded
        payload = {
            "username": API_USERNAME,
            "password": API_PASSWORD,
            "grant_type": "password",
        }

        for attempt in range(1, MAX_LOGIN_RETRIES + 2):  # lần 1 + 1 retry
            try:
                response = requests.post(url, data=payload, timeout=10)  # data= form-encoded
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                    logger.info("[Auth] Login successful")
                    return True
                else:
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