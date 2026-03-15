"""
demo_telemetry.py
-----------------
Script chạy thủ công để in ra một telemetry payload mẫu
lấy từ dữ liệu mới nhất trong database thực.

Chạy từ thư mục gốc dự án:
    .\\venv\\Scripts\\python.exe test/demo_telemetry.py
"""

import sys
import json
from pathlib import Path

# Thêm thư mục gốc vào sys.path để import được các module dự án
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database.sqlite_manager import MetadataDB, RealtimeDB
from services.project_service import ProjectService
from services.telemetry_service import TelemetryService


# ─────────────────────────────────────────────
# Kết nối database thực
# ─────────────────────────────────────────────
META_DB_PATH = str(ROOT / "metadata.db")
RT_DB_PATH   = str(ROOT / "realtime.db")

meta_db = MetadataDB(META_DB_PATH)
rt_db   = RealtimeDB(RT_DB_PATH)

# ─────────────────────────────────────────────
# Lấy danh sách project
# ─────────────────────────────────────────────
projects = meta_db.get_projects()
if not projects:
    print("[ERROR] Không tìm thấy project nào trong database.")
    sys.exit(1)

print(f"[INFO] Tìm thấy {len(projects)} project(s):")
for p in projects:
    print(f"  id={p.id}  name={p.name}  location={p.location}")

# Dùng project đầu tiên (mới nhất theo id DESC)
target_project = projects[0]
PROJECT_ID     = target_project.id
print(f"\n[INFO] Lấy telemetry cho project_id={PROJECT_ID} ({target_project.name})\n")

# ─────────────────────────────────────────────
# Build telemetry (không dùng buffer, chỉ in)
# ─────────────────────────────────────────────
project_svc  = ProjectService(meta_db, rt_db)
telemetry_svc = TelemetryService(project_svc, buffer_service=None)

snapshot = project_svc.get_project_snapshot(PROJECT_ID)

if not snapshot:
    print("[WARN] Snapshot trống — chưa có dữ liệu realtime cho project này.")
    sys.exit(0)

payload = telemetry_svc._build_payload(PROJECT_ID, snapshot)

# ─────────────────────────────────────────────
# In kết quả
# ─────────────────────────────────────────────
print("=" * 60)
print("TELEMETRY PAYLOAD (JSON)")
print("=" * 60)
print(json.dumps(payload, indent=2, ensure_ascii=False))
print("=" * 60)

# Thống kê nhanh
n_inverters = len(payload["inverters"])
n_mppts     = sum(len(inv["mppts"]) for inv in payload["inverters"])
n_strings   = sum(
    len(m["strings"])
    for inv in payload["inverters"]
    for m in inv["mppts"]
)
n_errors    = sum(len(inv["errors"]) for inv in payload["inverters"])

print(f"\n[SUMMARY]")
print(f"  Inverters : {n_inverters}")
print(f"  MPPTs     : {n_mppts}")
print(f"  Strings   : {n_strings}")
print(f"  Errors    : {n_errors}")
print(f"  Timestamp : {payload['timestamp']}")
