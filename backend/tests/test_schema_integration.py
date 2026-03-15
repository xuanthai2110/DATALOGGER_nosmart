import os
import sqlite3
from database.sqlite_manager import MetadataDB, RealtimeDB
from schemas.project import ProjectCreate
from schemas.inverter import InverterCreate
from schemas.realtime import ProjectRealtimeCreate
from datetime import datetime

def test():
    # Setup temporary databases
    meta_db_path = "test_metadata.db"
    rt_db_path = "test_realtime.db"
    
    # Pre-cleanup
    for p in [meta_db_path, rt_db_path]:
        if os.path.exists(p):
            try: os.remove(p)
            except: pass

    try:
        meta = MetadataDB(meta_db_path)
        rt = RealtimeDB(rt_db_path)

        # 1. Test Project
        project_data = ProjectCreate(
            elec_meter_no="METER-001",
            elec_price_per_kwh=3000.0,
            name="Test Project",
            location="Hanoi",
            lat=21.0,
            lon=105.0,
            capacity_kwp=100.0,
            ac_capacity_kw=80.0,
            inverter_count=1
        )
        p_id = meta.post_project(project_data)
        print(f"Project created with ID: {p_id}")
        
        project = meta.get_project(p_id)
        if project:
            print(f"Retrieved project: {project.name}")
            assert project.elec_meter_no == "METER-001"
        else:
            print("Failed to retrieve project")
            return

        # 2. Test Inverter
        inverter_data = InverterCreate(
            inverter_index=1,
            project_id=p_id,
            brand="Sungrow",
            model="SG110CX",
            serial_number="SN-123456",
            capacity_kw=110.0,
            mppt_count=9,
            firmware_version="V11",
            phase_count=3,
            string_count=18,
            rate_dc_kwp=120.0,
            rate_ac_kw=110.0,
            is_active=True
        )
        inv_id = meta.post_inverter(inverter_data)
        print(f"Inverter created with ID: {inv_id}")
        
        inverter = meta.get_inverter(inv_id)
        if inverter:
            print(f"Retrieved inverter serial: {inverter.serial_number}")
            assert inverter.serial_number == "SN-123456"
        else:
            print("Failed to retrieve inverter")
            return

        # 3. Test Realtime
        rt_data = ProjectRealtimeCreate(
            project_id=p_id,
            Temp_C=30.5,
            P_ac=50.0,
            P_dc=55.0,
            E_daily=200.0,
            E_monthly=5000.0,
            E_total=100000.0,
            severity="info",
            created_at=datetime.now().isoformat()
        )
        rt.post_project_realtime(rt_data)
        print("Realtime data posted.")
        
        rt_records = rt.get_project_realtime_range(p_id, "2020-01-01", "2030-01-01")
        print(f"Retrieved {len(rt_records)} realtime records.")
        assert len(rt_records) > 0
        assert rt_records[0].Temp_C == 30.5

        print("\nVerification SUCCESSFUL!")

    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        # Cleanup will happen on next run or manually
        pass

if __name__ == "__main__":
    test()
