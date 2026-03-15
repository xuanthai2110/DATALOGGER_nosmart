import json
import time
from database.sqlite_manager import MetadataDB, RealtimeDB
from services.project_service import ProjectService

def test_service():
    meta_db = MetadataDB("metadata.db")
    rt_db = RealtimeDB("realtime.db")
    service = ProjectService(meta_db, rt_db)

    print("--- Testing ProjectService ---")
    
    # 1. Test get_project (Response as Dataclass)
    project = service.get_project(1)
    if project:
        print(f"Project Found: {project.name} (Type: {type(project).__name__})")
    else:
        print("Project 1 not found. Please ensure project exists in metadata.db")
        return

    # 2. Test get_project_snapshot (Batch Optimized)
    print("\n--- Testing Optimized Snapshot ---")
    start_time = time.time()
    snapshot = service.get_project_snapshot(1)
    end_time = time.time()

    if snapshot:
        # Check metadata inclusion
        meta = snapshot.get("metadata")
        print(f"Snapshot Metadata: {meta.get('name') if meta else 'N/A'}")
        
        # Check inverters and nested data
        inverters = snapshot.get("inverters", [])
        print(f"Total Inverters in Snapshot: {len(inverters)}")
        
        if inverters:
            first_inv = inverters[0]
            print(f"First Inverter SN: {first_inv.get('serial_number')}")
            print(f"MPPT Count: {len(first_inv.get('mppts', []))}")
            
            # Check string nesting in first MPPT
            if first_inv.get('mppts'):
                first_mppt = first_inv['mppts'][0]
                print(f"String Count in first MPPT: {len(first_mppt.get('strings', []))}")

        print(f"\nSnapshot Performance: {(end_time - start_time)*1000:.2f} ms")
    else:
        print("Snapshot failed.")

if __name__ == "__main__":
    test_service()
