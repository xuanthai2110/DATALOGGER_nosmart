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
SQLITE_DB    = str(DATABASE_DIR / "datalogger.db")

# ===========================================================
# API
# ===========================================================
API_BASE_URL = "https://api.hirubicsolars.io.vn"
API_USERNAME = "nbc"
API_PASSWORD = "nbc"
DEV_MODE     = True


# ===========================================================
# POLLING   
# ===========================================================
POLL_INTERVAL = 5       # giây

# ===========================================================
# Modbus RTU
# ===========================================================
MODBUS_PORT     = "/dev/ttyUSB0"   # Windows: "COM3"
MODBUS_BAUDRATE = 9600
SLAVE_ID        = 1
PARITY          = "N"
STOPBITS        = 1
TIMEOUT         = 1.0
RETRIES         = 1