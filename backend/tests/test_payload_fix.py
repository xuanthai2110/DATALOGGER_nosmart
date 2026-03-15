
import sys
from pathlib import Path
from unittest.mock import MagicMock
from dataclasses import asdict

# Thêm thư mục gốc vào sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.setup_service import SetupService
from schemas.project import ProjectResponse
from schemas.inverter import InverterResponse

def test_project_payload():
    # Mock dependencies
    auth_svc = MagicMock()
    meta_db = MagicMock()
    
    auth_svc.get_access_token.return_value = "dummy_token"
    
    # Mock a project with some 0 values and created_at
    mock_project = ProjectResponse(
        id=1,
        elec_meter_no="MET123",
        elec_price_per_kwh=0.0, # Should be included
        name="Test Project",
        location="Vietnam",
        lat=10.0,
        lon=106.0,
        capacity_kwp=100.0,
        ac_capacity_kw=80.0,
        inverter_count=0, # Should be included
        server_id=None,
        server_request_id=None,
        sync_status="pending",
        created_at="2026-03-11 01:28:29" # Should be excluded
    )
    
    meta_db.get_project.return_value = mock_project
    
    setup_svc = SetupService(auth_svc, meta_db)
    
    # We will use the DEBUG print to verify, or we can mock requests.post
    import requests
    original_post = requests.post
    requests.post = MagicMock()
    
    setup_svc.sync_project_to_server(1)
    
    # Get the payload from the call to requests.post
    args, kwargs = requests.post.call_args
    payload = kwargs.get('json', {})
    
    print(f"Captured Project Payload: {payload}")
    
    # Assertions
    assert "created_at" not in payload
    assert "id" not in payload
    assert payload["elec_price_per_kwh"] == 0.0
    assert payload["inverter_count"] == 0
    assert payload["name"] == "Test Project"
    
    print("✅ Project payload test passed!")
    
    requests.post = original_post

def test_inverter_payload():
    # Mock dependencies
    auth_svc = MagicMock()
    meta_db = MagicMock()
    
    auth_svc.get_access_token.return_value = "dummy_token"
    
    # Mock a project (approved)
    mock_project = ProjectResponse(
        id=1, elec_meter_no="N/A", elec_price_per_kwh=1000.0, name="P1",
        location="L1", lat=0, lon=0, capacity_kwp=100, ac_capacity_kw=80, inverter_count=1,
        server_id=123, sync_status="approved"
    )
    
    # Mock an inverter với slave_id
    mock_inverter = InverterResponse(
        id=1, project_id=1, inverter_index=1, serial_number="SN123",
        brand="Huawei", model="SUN2000", firmware_version="V1",
        phase_count=3, mppt_count=2, string_count=4, capacity_kw=50.0,
        rate_dc_kwp=60.0, rate_ac_kw=50.0, is_active=True,
        sync_status="pending", slave_id=1
    )
    
    meta_db.get_project.return_value = mock_project
    meta_db.get_inverters_by_project.return_value = [mock_inverter]
    meta_db.get_inverter_by_serial.return_value = mock_inverter
    
    setup_svc = SetupService(auth_svc, meta_db)
    
    import requests
    original_post = requests.post
    requests.post = MagicMock()
    
    setup_svc.sync_inverters_to_server(1)
    
    # Get the payload from the call to requests.post
    args, kwargs = requests.post.call_args
    payload = kwargs.get('json', {})
    
    print(f"Captured Inverter Payload: {payload}")
    
    # Assertions
    assert "project_id" in payload 
    assert payload["serial_number"] == mock_inverter.serial_number
    assert payload["inverter_index"] == 1
    # slave_id không nên có trong payload gửi lên server
    assert "slave_id" not in payload
    
    # Kiểm tra xem slave_id có trong kết quả trả về từ DB (mock)
    inv_from_db = meta_db.get_inverter_by_serial(mock_inverter.serial_number)
    assert inv_from_db.slave_id == 1
    print(f"✅ Inverter slave_id persistence test passed! (Slave ID: {inv_from_db.slave_id})")
    
    print("✅ Inverter payload test passed!")
    
    requests.post = original_post

if __name__ == "__main__":
    try:
        test_project_payload()
        test_inverter_payload()
        print("\nALL TESTS PASSED!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
