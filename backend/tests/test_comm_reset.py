
import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from database.sqlite_manager import MetadataDB
from schemas.comm import CommConfig
import config as app_config

def test_reset_comm(test_db_path):
    print(f"=== Testing reset_comm_configs logic on {test_db_path} ===")
    
    # Use a temporary test database
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        
    db = MetadataDB(test_db_path)
    
    # 1. Add some dummy configs
    print("[1] Adding dummy comm configs...")
    config1 = CommConfig(
        driver="Huawei",
        comm_type="TCP",
        host="192.168.1.10",
        port=502,
        com_port="",
        baudrate=9600,
        databits=8,
        parity="N",
        stopbits=1,
        timeout=1.0,
        slave_id_start=1,
        slave_id_end=10
    )
    db.post_comm_config(config1)
    
    config2 = CommConfig(
        driver="Sungrow",
        comm_type="RTU",
        host="",
        port=0,
        com_port="/dev/ttyUSB0",
        baudrate=9600,
        databits=8,
        parity="N",
        stopbits=1,
        timeout=1.0,
        slave_id_start=11,
        slave_id_end=20
    )
    db.post_comm_config(config2)
    
    # configs = db.get_all_comm_configs() # This returns dataclasses which don't have ID
    # We'll use a manual query to check IDs
    with db._connect() as conn:
        rows = conn.execute("SELECT id, driver FROM comm_config").fetchall()
        print(f"Initial configs count: {len(rows)}")
        for r in rows:
            print(f" - ID: {r['id']}, Driver: {r['driver']}")
            
        if len(rows) != 2:
            print("FAILED: Expected 2 configs.")
            return

    # 2. Reset configs
    print("\n[2] Resetting comm configs...")
    db.reset_comm_configs()
    
    with db._connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM comm_config").fetchone()[0]
        print(f"Configs count after reset: {count}")
        
        if count != 0:
            print("FAILED: Table not empty after reset.")
            return
            
    # 3. Verify sequence reset (next ID should be 1)
    print("\n[3] Verifying sequence reset (adding new config)...")
    db.post_comm_config(config1)
    
    with db._connect() as conn:
        row = conn.execute("SELECT id FROM comm_config LIMIT 1").fetchone()
        if row and row['id'] == 1:
            print("SUCCESS: Sequence reset verified. New config ID is 1.")
        else:
            actual_id = row['id'] if row else "None"
            print(f"FAILED: Sequence NOT reset. New config ID is {actual_id}")
            return

    print("\n=== ALL LOGIC TESTS PASSED ===")
    
if __name__ == "__main__":
    test_db_path = "test_metadata.db"
    try:
        test_reset_comm(test_db_path)
    finally:
        # Give a small delay for SQLite to release the file
        import time
        time.sleep(0.5)
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception as e:
                print(f"Cleanup warning: Could not remove {test_db_path}: {e}")
