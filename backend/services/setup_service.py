import requests
import logging
import time
from dataclasses import asdict
from config import API_BASE_URL
from backend.models.project import ProjectCreate, ProjectUpdate
from backend.models.inverter import InverterCreate, InverterUpdate

logger = logging.getLogger(__name__)

class SetupService:
    def __init__(self, auth_service, metadata_db):
        self.auth = auth_service
        self.metadata_db = metadata_db

    def scan_inverters(self, transport, project_id: int, driver_class) -> list[int]:
        """
        QUY TRÌNH QUÉT INVERTER:
        1. Lặp qua dải Slave ID (mặc định 1-30).
        2. Với mỗi ID, khởi tạo driver và thử đọc thông tin (read_info).
        3. Nếu inverter phản hồi (is_active), gán project_id và số thứ tự (inverter_index).
        4. Lưu thông tin vào Database local (upsert_inverter).
        """
        found_ids = []
        logger.info(f"[Setup] Starting scan for inverters (Slave 1-30) using {driver_class.__name__}")
        
        for slave_id in range(1, 31):
            success = False
            for attempt in range(2):
                try:
                    driver = driver_class(transport, slave_id=slave_id)
                    info = driver.read_info()
                    
                    if info and info.get("is_active"):
                        logger.info(f"[Setup] Found active inverter at Slave ID {slave_id}: {info['serial_number']}")
                        info["project_id"] = project_id
                        inv_data = InverterCreate(**info)
                        local_id = self.metadata_db.upsert_inverter(inv_data)
                        found_ids.append(local_id)
                        success = True
                        break
                    else:
                        logger.debug(f"[Setup] No active inverter at Slave ID {slave_id} (Attempt {attempt+1})")
                except Exception as e:
                    logger.debug(f"[Setup] Error scanning Slave ID {slave_id} (Attempt {attempt+1}): {e}")
                
                if not success and attempt == 0:
                    time.sleep(1) # Delay 1s before retry
                    
        logger.info(f"[Setup] Scan complete. Found {len(found_ids)} inverters.")
        return found_ids

    def sync_project_to_server(self, project_id: int) -> int | None:
        """
        QUY TRÌNH ĐỒNG BỘ PROJECT:
        1. Lấy dữ liệu project từ Local DB.
        2. Nếu đã có 'server_id' → Project đã được duyệt, trả về ID luôn.
        3. Nếu đã có 'server_request_id' → Đã gửi yêu cầu nhưng chưa có ID thật:
           - Gọi GET /api/projects/requests/{id} để kiểm tra trạng thái (polling).
           - Nếu 'approved' → Cập nhật 'server_id' local và trả về.
        4. Nếu chưa có gì → Gửi yêu cầu mới (POST /api/projects/requests/):
           - Server trả về 'id' (Request ID), lưu lại local dưới dạng 'pending'.
           - Nếu lỗi 409 (đã tồn tại) → Đánh dấu local là 'approved' để tiếp tục đồng bộ inverters.
        """
        local_project = self.metadata_db.get_project(project_id)
        if not local_project: return None

        # Nếu đã có server_id thật, coi như xong bước setup cơ bản
        sid = getattr(local_project, 'server_id', None)
        if sid and str(sid).upper() not in ("NULL", "NONE"):
            return sid

        token = self.auth.get_access_token()
        if not token: return None
        headers = {"Authorization": f"Bearer {token}"}

        req_id = getattr(local_project, 'server_request_id', None)
        if req_id:
            # Poll status
            url = f"{API_BASE_URL}/api/projects/requests/{req_id}"
            try:
                time.sleep(1) # Khoảng cách mỗi request là 1s
                resp = requests.get(url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")
                    if status == "approved":
                        server_id = data.get("approved_project_id")
                        self.metadata_db.update_project_sync(project_id, server_id=server_id, status='approved')
                        logger.info(f"[Sync] Project Request {req_id} APPROVED -> Project ID {server_id}")
                        return server_id
                    elif status == "rejected":
                        logger.warning(f"[Sync] Project Request {req_id} REJECTED")
                        return None
                    return None # Vẫn đang pending
            except Exception as e:
                logger.error(f"[Sync] Error polling project request: {e}")
                return None
        else:
            # Gửi Request mới
            url = f"{API_BASE_URL}/api/projects/requests/"
            
            # Chỉ lấy các trường cần thiết cho server, bỏ qua các trường internal và metadata
            exclude_fields = {'id', 'server_id', 'server_request_id', 'sync_status', 'created_at', 'updated_at'}
            payload = {k: v for k, v in asdict(local_project).items() 
                      if k not in exclude_fields and v is not None}
            
            print(f"DEBUG Project Sync Payload: {payload}")
            try:
                time.sleep(1) # Khoảng cách mỗi request là 1s
                resp = requests.post(url, json=payload, headers=headers, timeout=10)
                logger.info(f"[Sync] Project Request response status: {resp.status_code}")
                if resp.status_code not in (200, 201):
                    logger.error(f"[Sync] Project Request failed: {resp.text}")

                if resp.status_code in (200, 201):
                    req_data = resp.json()
                    print(f"DEBUG Project Sync SUCCESS Response: {req_data}")
                    logger.info(f"[Sync] Project Request SUCCESS. Data: {req_data}")
                    new_req_id = req_data.get("id")
                    self.metadata_db.update_project_sync(project_id, server_request_id=new_req_id, status='pending')
                    logger.info(f"[Sync] Project Request created: ID {new_req_id}")
                    return None # Chờ duyệt
                elif resp.status_code == 409:
                    logger.info(f"[Sync] Project already exists on server (409)")
                    # Mark as approved so UI shows it's okay
                    self.metadata_db.update_project_sync(project_id, status='approved')
                    
                    # Try to fetch existing project ID
                    try:
                        time.sleep(1)
                        if local_project.elec_meter_no:
                            fetch_url = f"{API_BASE_URL}/api/projects/?elec_meter_no={local_project.elec_meter_no}"
                            fetch_resp = requests.get(fetch_url, headers=headers, timeout=5)
                            if fetch_resp.status_code == 200:
                                data_items = fetch_resp.json().get('data', [])
                                if data_items and len(data_items) > 0:
                                    proj_data = data_items[0].get('project', {})
                                    existing_id = proj_data.get('id')
                                    if existing_id:
                                        logger.info(f"[Sync] Recovered existing Project ID {existing_id} for meter {local_project.elec_meter_no}")
                                        self.metadata_db.update_project_sync(project_id, server_id=existing_id, status='approved')
                                        return existing_id
                    except Exception as e:
                        logger.error(f"[Sync] Error fetching existing project details: {e}")

                    try:
                        req_data = resp.json()
                        if "server_id" in req_data:
                             self.metadata_db.update_project_sync(project_id, server_id=req_data["server_id"], status='approved')
                        elif "id" in req_data:
                             self.metadata_db.update_project_sync(project_id, server_request_id=req_data["id"], status='approved')
                    except Exception: pass
                    return None
            except Exception as e:
                logger.error(f"[Sync] Error creating project request: {e}")
        return None

    def sync_inverters_to_server(self, project_id: int) -> int:
        """
        QUY TRÌNH ĐỒNG BỘ INVERTERS:
        1. Lấy danh sách inverters local của project.
        2. Với mỗi inverter chưa có 'server_id':
           - Nếu có 'server_request_id' → Kiểm tra trạng thái duyệt (polling).
           - Nếu chưa gửi yêu cầu → Gửi POST /api/inverters/requests/.
        3. Liên kết: Gửi kèm 'project_id' (nếu đã duyệt) hoặc 'project_request_id' để server tự map.
        4. Xử lý lỗi 409 (đã tồn tại): Đánh dấu local là 'approved' để có thể gửi dữ liệu telemetry sau này.
        """
        local_project = self.metadata_db.get_project(project_id)
        if not local_project: return 0

        local_inverters = self.metadata_db.get_inverters_by_project(project_id)
        token = self.auth.get_access_token()
        if not token: return 0
        headers = {"Authorization": f"Bearer {token}"}

        synced_count = 0
        for inv in local_inverters:
            sid = getattr(inv, 'server_id', None)
            if sid and str(sid).upper() not in ("NULL", "NONE"):
                synced_count += 1
                continue

            req_id = getattr(inv, 'server_request_id', None)
            if req_id:
                # Poll status
                url = f"{API_BASE_URL}/api/inverters/requests/{req_id}"
                try:
                    time.sleep(1) # Khoảng cách mỗi request là 1s
                    resp = requests.get(url, headers=headers, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("status") == "approved":
                            server_id = data.get("approved_inverter_id")
                            self.metadata_db.update_inverter_sync(inv.id, server_id=server_id, status='approved')
                            logger.info(f"[Sync] Inverter {inv.serial_number} APPROVED -> ID {server_id}")
                            synced_count += 1
                        else:
                            # Vẫn đang pending
                            synced_count += 1 
                except Exception: pass
            else:
                # Gửi Request mới
                url = f"{API_BASE_URL}/api/inverters/requests/"
                
                # Chỉ lấy các trường cần thiết cho server, bỏ qua các trường internal và redundant
                # 'slave_id' và 'capacity_kw' không có trong yêu cầu server mới
                exclude_fields = {
                    'id', 'server_id', 'server_request_id', 'sync_status', 
                    'project_id', 'slave_id', 'capacity_kw', 'created_at', 'updated_at'
                }
                payload = {k: v for k, v in asdict(inv).items() 
                          if k not in exclude_fields and v is not None}
                
                # Quyết định dùng project_id hay project_request_id
                if getattr(local_project, 'server_id', None):
                    payload["project_id"] = local_project.server_id
                elif getattr(local_project, 'server_request_id', None):
                    payload["project_request_id"] = local_project.server_request_id
                else:
                    logger.warning(f"[Sync] Cannot request inverter sync for {inv.serial_number}: No project reference.")
                    continue

                print(f"DEBUG Inverter Sync Payload for {inv.serial_number}: {payload}")

                try:
                    time.sleep(1) # Khoảng cách mỗi request là 1s
                    resp = requests.post(url, json=payload, headers=headers, timeout=10)
                    logger.info(f"[Sync] Inverter {inv.serial_number} sync status: {resp.status_code}")
                    if resp.status_code not in (200, 201):
                        logger.error(f"[Sync] Inverter {inv.serial_number} sync failed: {resp.text}")

                    if resp.status_code in (200, 201):
                        resp_data = resp.json()
                        print(f"DEBUG Inverter {inv.serial_number} sync SUCCESS Response: {resp_data}")
                        logger.info(f"[Sync] Inverter {inv.serial_number} SUCCESS. Data: {resp_data}")
                        new_req_id = resp_data.get("id")
                        self.metadata_db.update_inverter_sync(inv.id, server_request_id=new_req_id, status='pending')
                        logger.info(f"[Sync] Inverter Request created for {inv.serial_number}: ID {new_req_id}")
                        synced_count += 1
                    elif resp.status_code == 409:
                        logger.info(f"[Sync] Inverter {inv.serial_number} already exists (409). Body: {resp.text}")
                        # Mark as approved so UI shows it's okay
                        self.metadata_db.update_inverter_sync(inv.id, status='approved')
                        
                        # Try to fetch existing inverter ID
                        try:
                            time.sleep(1)
                            if inv.serial_number:
                                fetch_url = f"{API_BASE_URL}/api/inverters/?serial_number={inv.serial_number}"
                                fetch_resp = requests.get(fetch_url, headers=headers, timeout=5)
                                if fetch_resp.status_code == 200:
                                    data_items = fetch_resp.json().get('data', [])
                                    if data_items and len(data_items) > 0:
                                        inv_data = data_items[0].get('inverter', {})
                                        existing_id = inv_data.get('id')
                                        if existing_id:
                                            logger.info(f"[Sync] Recovered existing Inverter ID {existing_id} for serial {inv.serial_number}")
                                            self.metadata_db.update_inverter_sync(inv.id, server_id=existing_id, status='approved')
                                            synced_count += 1
                                            continue  # Skip the fallback JSON parsing
                        except Exception as e:
                            logger.error(f"[Sync] Error fetching existing inverter details: {e}")

                        try:
                            resp_data = resp.json()
                            if "server_id" in resp_data:
                                self.metadata_db.update_inverter_sync(inv.id, server_id=resp_data["server_id"], status='approved')
                            elif "id" in resp_data:
                                self.metadata_db.update_inverter_sync(inv.id, server_request_id=resp_data["id"], status='approved')
                            elif "existing_id" in resp_data:
                                self.metadata_db.update_inverter_sync(inv.id, server_id=resp_data["existing_id"], status='approved')
                        except Exception: pass
                        synced_count += 1
                except Exception as e:
                    logger.error(f"[Sync] Error creating inverter request: {e}")

        return synced_count
