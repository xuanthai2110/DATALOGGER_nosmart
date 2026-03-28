import os
import sys

# Add backend vào path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BASE_DIR)

from database.sqlite_manager import RealtimeDB
from config import REALTIME_DB

def test_realtime():
    rt_db = RealtimeDB(REALTIME_DB)

    print("REALTIME DB:", REALTIME_DB)

    # ==========================
    # 1. Project realtime
    # ==========================
    print("\n=== PROJECT REALTIME ===")
    project_rt = rt_db.get_latest_project_realtime(project_id=1)
    print(project_rt)

    # ==========================
    # 2. Inverter AC realtime
    # ==========================
    print("\n=== INVERTER AC REALTIME ===")
    inv_rt = rt_db.get_latest_inverter_ac_realtime(inverter_id=1)
    print(inv_rt)

    # ==========================
    # 3. MPPT realtime
    # ==========================
    print("\n=== MPPT REALTIME ===")
    mppts = rt_db.get_latest_mppt_batch(inverter_id=1)
    for m in mppts:
        print(m)

    # ==========================
    # 4. String realtime
    # ==========================
    print("\n=== STRING REALTIME ===")
    strings = rt_db.get_latest_string_batch(inverter_id=1)
    for s in strings:
        print(s)

    # ==========================
    # 5. Range query test
    # ==========================
    print("\n=== RANGE TEST ===")
    data = rt_db.get_inverter_ac_range(
        inverter_id=1,
        start="2026-03-24T00:00:00",
        end="2026-03-24T23:59:59"
    )

    for d in data[:5]:  # chỉ in 5 dòng
        print(d)


if __name__ == "__main__":
    test_realtime()