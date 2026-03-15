"""
test_login.py
-------------
Test thử login lên server và in ra token response.

Chạy từ thư mục gốc dự án:
    .\venv\Scripts\python.exe test/test_login.py
"""

import sys
import json
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import API_BASE_URL, API_USERNAME, API_PASSWORD

print(f"[INFO] Server  : {API_BASE_URL}")
print(f"[INFO] Username: {API_USERNAME}")
print(f"[INFO] Endpoint: POST /api/auth/token")
print("-" * 50)

url = f"{API_BASE_URL}/api/auth/token"
payload = {
    "username": API_USERNAME,
    "password": API_PASSWORD,
    "grant_type": "password",
}

try:
    response = requests.post(url, data=payload, timeout=10)

    print(f"[HTTP] Status Code : {response.status_code}")
    print(f"[HTTP] Content-Type: {response.headers.get('Content-Type', '')}")
    print("-" * 50)

    try:
        data = response.json()
        print("[RESPONSE JSON]")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("-" * 50)

        if response.status_code == 200:
            access_token  = data.get("access_token")
            refresh_token = data.get("refresh_token")
            token_type    = data.get("token_type", "bearer")
            expires_in    = data.get("expires_in")

            print("[RESULT] ✅ Login thành công!")
            print(f"  token_type   : {token_type}")
            print(f"  access_token : {access_token[:40]}..." if access_token else "  access_token : None")
            print(f"  refresh_token: {refresh_token[:40]}..." if refresh_token else "  refresh_token: None")
            if expires_in:
                print(f"  expires_in   : {expires_in}s")
        else:
            print(f"[RESULT] ❌ Login thất bại (status={response.status_code})")
            detail = data.get("detail") or data.get("message") or ""
            if detail:
                print(f"  detail: {detail}")

    except Exception:
        print("[RESPONSE TEXT] (không phải JSON)")
        print(response.text[:500])

except requests.exceptions.ConnectionError:
    print(f"[ERROR] ❌ Không kết nối được tới server: {API_BASE_URL}")
except requests.exceptions.Timeout:
    print("[ERROR] ❌ Request timeout (>10s)")
except Exception as e:
    print(f"[ERROR] ❌ Lỗi không mong đợi: {e}")
