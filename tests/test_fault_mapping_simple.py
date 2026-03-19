
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.fault_state_service import FaultStateService

def test():
    svc = FaultStateService()
    
    # Test Huawei DERATING (raw 0x0201 = 513)
    print("--- Huawei DERATING (raw 513, fault 0) ---")
    payload = svc.get_inverter_status_payload("HUAWEI", 513, 0)
    print(f"Result: {payload}")
    assert payload["fault_description"] == "DERATING"
    assert payload["fault_code"] == 7  # Unified DERATING ID
    assert payload["severity"] == "WARNING"
    
    # Test Huawei RUNNING (raw 0x0200 = 512) with Fault 2001
    print("\n--- Huawei RUNNING (raw 512, fault 2001) ---")
    payload = svc.get_inverter_status_payload("HUAWEI", 512, 2001)
    print(f"Result: {payload}")
    assert payload["fault_description"] == "GRID_OVERVOLTAGE"
    assert payload["fault_code"] == 1001 # Unified GRID_OVERVOLTAGE
    assert payload["severity"] == "ERROR"
    
    # Test Sungrow DERATING (raw 4)
    print("\n--- Sungrow DERATING (raw 4, fault 0) ---")
    payload = svc.get_inverter_status_payload("SUNGROW", 4, 0)
    print(f"Result: {payload}")
    assert payload["fault_description"] == "DERATING"
    assert payload["fault_code"] == 7
    assert payload["severity"] == "WARNING"

    print("\n✅ Verification SUCCESS!")

if __name__ == "__main__":
    test()
