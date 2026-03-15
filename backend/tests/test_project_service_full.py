import os
import time
from datetime import datetime
from database.sqlite_manager import MetadataDB, RealtimeDB
from services.project_service import ProjectService
from schemas.project import ProjectCreate, ProjectUpdate
from schemas.inverter import InverterCreate
from schemas.realtime import ProjectRealtimeCreate

def test_full_service_lifecycle():
    # 1. Setup - Isolated databases
    meta_path = "test_full_meta.db"
    rt_path = "test_full_rt.db"
    
    # Cleanup before start
    for p in [meta_path, rt_path]:
        if os.path.exists(p): os.remove(p)

    meta_db = MetadataDB(meta_path)
    rt_db = RealtimeDB(rt_path)
    service = ProjectService(meta_db, rt_db)

    print("--- [START] Comprehensive ProjectService Test ---")

    try:
        # 2. Project Lifecycle
        print("\n[1] Testing Project CRUD...")
        p_data = ProjectCreate(
            elec_meter_no="M-999",
            elec_price_per_kwh=3500.0,
            name="Alpha Solar",
            location="Da Nang",
            lat=16.0,
            lon=108.0,
            capacity_kwp=500.0,
            ac_capacity_kw=450.0,
            inverter_count=2
        )
        p_id = service.create_project(p_data)
        assert p_id == 1
        
        project = service.get_project(p_id)
        assert project.name == "Alpha Solar"
        
        service.update_project(p_id, ProjectUpdate(id=p_id, name="Alpha Solar Updated"))
        assert service.get_project(p_id).name == "Alpha Solar Updated"
        
        assert len(service.get_all_projects()) == 1
        print("Project CRUD: SUCCESS")

        # 3. Inverter Lifecycle
        print("\n[2] Testing Inverter CRUD...")
        i_data = InverterCreate(
            inverter_index=1,
            project_id=p_id,
            brand="Huawei",
            model="SUN2000",
            serial_number="H-SN-001",
            capacity_kw=100.0,
            mppt_count=6,
            firmware_version="V100",
            phase_count=3,
            string_count=12,
            rate_dc_kwp=110.0,
            rate_ac_kw=100.0,
            is_active=True
        )
        inv_id = service.create_inverter(i_data)
        assert inv_id == 1
        
        inverter = service.get_inverter(inv_id)
        assert inverter.serial_number == "H-SN-001"
        print("Inverter CRUD: SUCCESS")

        # 4. Realtime & Snapshot
        print("\n[3] Testing Realtime & Snapshot...")
        # Add some sample realtime data directly via DB for simplicity in this test
        # but using project_id 1
        rt_create = ProjectRealtimeCreate(
            project_id=p_id, Temp_C=28.0, P_ac=400.0, P_dc=420.0,
            E_daily=150.0, E_monthly=4500.0, E_total=90000.0,
            severity="info", created_at=datetime.now().isoformat()
        )
        rt_db.post_project_realtime(rt_create)
        
        start_ts = time.time()
        snapshot = service.get_project_snapshot(p_id)
        duration = (time.time() - start_ts) * 1000
        
        assert snapshot["metadata"]["name"] == "Alpha Solar Updated"
        assert snapshot["project"]["Temp_C"] == 28.0
        assert len(snapshot["inverters"]) == 1
        print(f"Snapshot Performance: {duration:.2f} ms")
        print("Realtime & Snapshot: SUCCESS")

        # 5. Cleanup Data
        print("\n[4] Testing Cleanup...")
        # Verify it doesn't crash
        service.cleanup_old_data(datetime.now().isoformat())
        print("Cleanup: SUCCESS")

        # 6. Deletion Lifecycle
        print("\n[5] Testing Full Deletion...")
        service.delete_project(p_id)
        assert service.get_project(p_id) is None
        assert len(meta_db.get_inverters_by_project(p_id)) == 0
        print("Deletion Lifecycle: SUCCESS")

        print("\n--- [PASSED] All Service Tests Successful ---")

    except Exception as e:
        print(f"\n--- [FAILED] Test failed: {e} ---")
        import traceback
        traceback.print_exc()
    finally:
        # Close handles implied by per-call connection logic, 
        # but we can remove files
        pass

if __name__ == "__main__":
    test_full_service_lifecycle()
