import os
from pathlib import Path

# ===========================================================
# BASE DIR – luôn là thư mục chứa file config.py này
# Dù chạy từ bất kỳ working directory nào cũng đúng
# ===========================================================
BASE_DIR = Path(__file__).resolve().parent

# ===========================================================
# PATHS
# ===========================================================
DATABASE_DIR = BASE_DIR / "database"
METADATA_DB    = str(DATABASE_DIR / "metadata.db")
REALTIME_DB    = str(DATABASE_DIR / "realtime.db")
TOKEN_FILE     = str(DATABASE_DIR / "tokens.json")
# ===========================================================
# API
# ===========================================================
API_BASE_URL = "https://api.hirubicsolar.io.vn"
API_USERNAME = "nbc"
API_PASSWORD = "nbc"
DEV_MODE     = True


# ===========================================================
# POLLING   
# ===========================================================
POLL_INTERVAL = 30       # giây

# ===========================================================
# COMMUNICATION (CommConfig defaults)
# ===========================================================
DRIVER = "Huawei"
COMM_TYPE = "TCP"
MODBUS_TCP_HOST = "192.168.1.8"
MODBUS_TCP_PORT = 502
MODBUS_PORT     = "/dev/ttyUSB0"   # Windows: "COM3"
MODBUS_BAUDRATE = 9600
DATABITS        = 8
PARITY          = "N"
STOPBITS        = 1
TIMEOUT         = 1.0
SLAVE_ID_START  = 1
SLAVE_ID_END    = 30
RETRIES         = 1

# ===========================================================
# PROJECT INFO
# ===========================================================
PROJECT_INFO = {
    "elec_meter_no": "PC07FF0169923",
    "elec_price_per_kwh": 1783,
    "name": "NBC-Nha Be",
    "location": "Quảng Ngãi",
    "lat": 14.821533,
    "lon": 108.945834,
    "capacity_kwp": 1000,
    "ac_capacity_kw": 880,
    "inverter_count": 8,
}

# ===========================================================
# LOCAL AUTH (WEB UI)
# ===========================================================
SECRET_KEY = "hirubic_local_secret_key_change_me"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days