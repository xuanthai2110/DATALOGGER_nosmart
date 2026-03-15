import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:5000"
ADMIN_USER = "admin"
ADMIN_PASS = "adminpassword123"

def print_banner(text):
    print("\n" + "="*50)
    print(f" {text}")
    print("="*50)

def test_monitoring_api():
    print_banner("MONITORING API TEST")
    
    # 1. Login
    print("[1] Logging in...")
    try:
        resp = requests.post(f"{BASE_URL}/api/auth/token", data={
            "username": ADMIN_USER,
            "password": ADMIN_PASS
        })
        if resp.status_code != 200:
            print(f"FAILED: Login status {resp.status_code}")
            return
        
        token = resp.json()['access_token']
        headers = {"Authorization": f"Bearer {token}"}
        print("SUCCESS: Logged in.")
    except Exception as e:
        print(f"ERROR: {e}")
        return

    # 2. Dashboard Summary
    print("\n[2] Testing Dashboard Summary...")
    try:
        resp = requests.get(f"{BASE_URL}/api/monitoring/dashboard/summary", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            print(f"SUCCESS: Dashboard summary received.")
            print(f"Total AC Power: {data.get('total_p_ac')} kW")
            print(f"Total Projects: {data.get('total_projects')}")
            projects = data.get('projects', [])
            if projects:
                first_project_id = projects[0]['id']
                print(f"First Project ID: {first_project_id}")
            else:
                print("No projects found to test further.")
                return
        else:
            print(f"FAILED: Status {resp.status_code}")
            return
    except Exception as e:
        print(f"ERROR: {e}")
        return

    # 3. Project Latest
    print(f"\n[3] Testing Project Latest Data (ID: {first_project_id})...")
    try:
        resp = requests.get(f"{BASE_URL}/api/monitoring/project/{first_project_id}/latest", headers=headers)
        if resp.status_code == 200:
            print(f"SUCCESS: Latest project data received.")
            print(json.dumps(resp.json(), indent=2))
        else:
            print(f"FAILED: Status {resp.status_code}")
    except Exception as e:
        print(f"ERROR: {e}")

    # 4. Inverter Latest
    print("\n[4] Fetching all inverters to test inverter monitoring...")
    try:
        resp = requests.get(f"{BASE_URL}/api/inverters", headers=headers)
        if resp.status_code == 200:
            inverters = resp.json()
            if inverters:
                first_inv_id = inverters[0]['id']
                print(f"Testing Inverter ID: {first_inv_id}")
                
                print(f"\n[4.1] Testing Inverter Latest (ID: {first_inv_id})...")
                resp_inv = requests.get(f"{BASE_URL}/api/monitoring/inverter/{first_inv_id}/latest", headers=headers)
                if resp_inv.status_code == 200:
                    print("SUCCESS: Latest inverter data received.")
                else:
                    print(f"FAILED: Status {resp_inv.status_code}")

                print(f"\n[4.2] Testing Inverter Detail (ID: {first_inv_id})...")
                resp_detail = requests.get(f"{BASE_URL}/api/monitoring/inverter/{first_inv_id}/detail", headers=headers)
                if resp_detail.status_code == 200:
                    print("SUCCESS: Inverter detail received.")
                    # print(json.dumps(resp_detail.json(), indent=2))
                else:
                    print(f"FAILED: Status {resp_detail.status_code}")
            else:
                print("No inverters found.")
        else:
            print(f"FAILED to fetch inverters: {resp.status_code}")
    except Exception as e:
        print(f"ERROR: {e}")

    # 5. Range Tests
    now = datetime.now()
    start = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    end = now.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"\n[5] Testing Range Queries (Start: {start}, End: {end})")
    print(f"[5.1] Project Range (ID: {first_project_id})...")
    try:
        resp = requests.get(f"{BASE_URL}/api/monitoring/project/{first_project_id}/range", 
                            params={"start": start, "end": end}, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            print(f"SUCCESS: Range data received ({len(data)} records).")
        else:
            print(f"FAILED: Status {resp.status_code}")
            print(resp.text)
    except Exception as e:
        print(f"ERROR: {e}")

    if 'first_inv_id' in locals():
        print(f"[5.2] Inverter Range (ID: {first_inv_id})...")
        try:
            resp = requests.get(f"{BASE_URL}/api/monitoring/inverter/{first_inv_id}/range", 
                                params={"start": start, "end": end}, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                print(f"SUCCESS: Range data received ({len(data)} records).")
            else:
                print(f"FAILED: Status {resp.status_code}")
        except Exception as e:
            print(f"ERROR: {e}")

    print_banner("MONITORING TESTS COMPLETED")

if __name__ == "__main__":
    test_monitoring_api()
