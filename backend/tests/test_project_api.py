import requests
import json
import uuid

BASE_URL = "http://localhost:5000"
ADMIN_USER = "admin"
ADMIN_PASS = "adminpassword123"

def print_banner(text):
    print("\n" + "="*50)
    print(f" {text}")
    print("="*50)

def test_project_crud():
    print_banner("PROJECT API CRUD TEST")
    
    # 1. Login
    print("[1] Logging in...")
    try:
        resp = requests.post(f"{BASE_URL}/api/auth/token", data={
            "username": ADMIN_USER,
            "password": ADMIN_PASS
        })
        if resp.status_code != 200:
            print(f"FAILED: Login status {resp.status_code}")
            print(resp.text)
            return
        
        token = resp.json()['access_token']
        headers = {"Authorization": f"Bearer {token}"}
        print("SUCCESS: Logged in.")
    except Exception as e:
        print(f"ERROR during login: {e}")
        return

    # 2. Get All Projects
    print("\n[2] Listing projects...")
    try:
        resp = requests.get(f"{BASE_URL}/api/projects", headers=headers)
        if resp.status_code == 200:
            count = len(resp.json().get('projects', []))
            print(f"SUCCESS: Found {count} projects.")
        else:
            print(f"FAILED: Status {resp.status_code}")
            return
    except Exception as e:
        print(f"ERROR: {e}")
        return

    # 3. Create Project
    unique_name = f"Test Project {uuid.uuid4().hex[:6]}"
    print(f"\n[3] Creating Project: {unique_name}")
    payload = {
        "name": unique_name,
        "location": "Virtual Office",
        "capacity_kwp": 123.45,
        "ac_capacity_kw": 100.0,
        "elec_price_per_kwh": 1800.0,
        "inverter_count": 5
    }
    try:
        resp = requests.post(f"{BASE_URL}/api/projects", json=payload, headers=headers)
        if resp.status_code in [200, 201]:
            project = resp.json()
            p_id = project['id']
            print(f"SUCCESS: Project created with ID {p_id}")
            print(json.dumps(project, indent=2))
        else:
            print(f"FAILED: Status {resp.status_code}")
            print(resp.text)
            return
    except Exception as e:
        print(f"ERROR: {e}")
        return

    # 4. Update Project
    print(f"\n[4] Updating Project ID {p_id}")
    update_payload = {
        "name": f"{unique_name} (Updated)",
        "capacity_kwp": 200.0
    }
    try:
        resp = requests.patch(f"{BASE_URL}/api/projects/{p_id}", json=update_payload, headers=headers)
        if resp.status_code == 200:
            updated = resp.json()
            print(f"SUCCESS: Project updated.")
            print(f"New Name: {updated['name']}")
            print(f"New Capacity: {updated['capacity_kwp']}")
        else:
            print(f"FAILED: Status {resp.status_code}")
            print(resp.text)
            return
    except Exception as e:
        print(f"ERROR: {e}")
        return

    # 5. Delete Project
    print(f"\n[5] Deleting Project ID {p_id}")
    try:
        resp = requests.delete(f"{BASE_URL}/api/projects/{p_id}", headers=headers)
        if resp.status_code == 200:
            print("SUCCESS: Project deleted.")
        else:
            print(f"FAILED: Status {resp.status_code}")
            print(resp.text)
            return
    except Exception as e:
        print(f"ERROR: {e}")
        return

    print_banner("ALL TESTS PASSED")

if __name__ == "__main__":
    test_project_crud()
