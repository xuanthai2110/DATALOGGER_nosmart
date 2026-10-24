import requests
import json
import logging
from backend.core.settings import API_BASE_URL
from backend.services.auth_service import AuthService

logger = logging.getLogger(__name__)

class UploaderService:
    def __init__(self, realtime_db, metadata_db):
        self.db = realtime_db
        self.metadata_db = metadata_db
        self.auth = AuthService(metadata_db)

    def upload(self):
        data_list = self.db.get_all_outbox()
        if not data_list: return
        for data in data_list:
            try:
                project_id = data.get("project_id")
                server_id = data.get("server_id")
                if not project_id or not server_id: continue
                
                # Look up server_account_id
                proj_meta = self.metadata_db.get_project(project_id)
                if not proj_meta or not proj_meta.server_account_id:
                    logger.warning(f"Project {project_id} has no server account. Skipping upload.")
                    continue
                
                token = self.auth.get_access_token(proj_meta.server_account_id)
                if not token: continue

                data_type = data.get("data_type", "Project")
                payload = data.copy()
                payload.pop("id", None)
                payload.pop("project_id", None)
                payload.pop("server_id", None)
                payload.pop("data_type", None)
                payload.pop("timestamp", None)
                
                if data_type == "EVN":
                    url = f"{API_BASE_URL}/api/telemetry/evn/project/{server_id}"
                else:
                    url = f"{API_BASE_URL}/api/telemetry/project/{server_id}"

                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                
                inv_sns = [inv.get("serial_number") for inv in payload.get("inverters", []) if isinstance(inv, dict) and inv.get("serial_number")]
                sns_str = f".{{{', '.join(inv_sns)}}}" if inv_sns else ""
                
                logger.info(f"[Uploader] Sending {data_type} telemetry for project {server_id} to {url}{sns_str}...")
                response = requests.post(url, json=payload, headers=headers, timeout=15)
                
                if response.status_code == 401:
                    logger.warning(f"[Uploader] 401 Unauthorized for project {server_id}. Attempting token refresh...")
                    token = self.auth.handle_unauthorized(proj_meta.server_account_id)
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        response = requests.post(url, json=payload, headers=headers, timeout=15)
                        logger.info(f"[Uploader] Retry result for project {server_id}: status={response.status_code}")
                
                if response.status_code in (200, 201):
                    self.db.delete_from_outbox(data["id"])
                    logger.info(f"[Uploader] SUCCESS: Uploaded {data_type} for project {server_id} (status={response.status_code}){sns_str}")
                elif response.status_code == 422:
                    err_text = response.text
                    logger.warning(f"Validation error (422) for project {server_id}: {err_text}. Attempting to fix payload and retry once...")
                    self._fix_payload_severity(payload)

                    # Tự động loại bỏ inverter chưa approved / không thuộc project nếu có
                    if "không thuộc project này" in err_text:
                        invalid_sns = self._extract_invalid_inverter_sns(err_text)
                        if invalid_sns and "inverters" in payload and isinstance(payload["inverters"], list):
                            logger.warning(f"[Uploader] Removing unapproved inverters {invalid_sns} from payload for project {server_id} and retrying...")
                            payload["inverters"] = [inv for inv in payload["inverters"] if inv.get("serial_number") not in invalid_sns]
                            inv_sns = [inv.get("serial_number") for inv in payload.get("inverters", []) if isinstance(inv, dict) and inv.get("serial_number")]
                            sns_str = f".{{{', '.join(inv_sns)}}}" if inv_sns else ""

                    if data_type == "EVN" or payload.get("inverters"):
                        response = requests.post(url, json=payload, headers=headers, timeout=15)
                        if response.status_code in (200, 201):
                            self.db.delete_from_outbox(data["id"])
                            logger.info(f"[Uploader] SUCCESS after fix & retry: Uploaded {data_type} for project {server_id} (status={response.status_code}){sns_str}")
                        else:
                            self.db.delete_from_outbox(data["id"])
                            logger.error(f"Upload failed twice for record {data['id']} (status={response.status_code}). Deleted from outbox. Error: {response.text}")
                    else:
                        self.db.delete_from_outbox(data["id"])
                        logger.warning(f"[Uploader] No approved inverters left in payload for project {server_id}. Deleted record {data['id']} from outbox.")
                elif response.status_code == 409:
                    self.db.delete_from_outbox(data["id"])
                    logger.warning(f"Upload conflict (409) for project {server_id}. Data already exists. Record {data['id']} deleted from outbox.")
                else:
                    logger.warning(f"Upload failed for project {server_id} (status={response.status_code}): {response.text}")
            except Exception as e:
                logger.error(f"Upload error: {e}")

    def _fix_payload_severity(self, obj):
        """Hàm đệ quy để sửa 'NORMAL' thành 'STABLE' trong payload telemetry."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "severity" and v == "NORMAL":
                    obj[k] = "STABLE"
                else:
                    self._fix_payload_severity(v)
        elif isinstance(obj, list):
            for item in obj:
                self._fix_payload_severity(item)

    def _extract_invalid_inverter_sns(self, err_text: str) -> set:
        """Trích xuất danh sách serial number inverter không thuộc project từ lỗi 422."""
        try:
            import re
            match = re.search(r"không thuộc project này\s*:\s*([^\"\'\}]+)", err_text)
            if match:
                raw_sns = match.group(1).strip()
                return {s.strip() for s in raw_sns.split(",") if s.strip()}
        except Exception as e:
            logger.debug(f"[Uploader] Error parsing invalid inverter SNs: {e}")
        return set()

    def send_immediate(self, data: dict):
        project_id = data.get("project_id")
        server_id = data.get("server_id")
        if not project_id or not server_id: return

        proj_meta = self.metadata_db.get_project(project_id)
        if not proj_meta or not proj_meta.server_account_id: return
        
        token = self.auth.get_access_token(proj_meta.server_account_id)
        if not token: return

        data_type = data.get("data_type", "Project")
        payload = data.copy()
        payload.pop("project_id", None)
        payload.pop("server_id", None)
        payload.pop("data_type", None)
        payload.pop("timestamp", None)
        
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        if data_type == "EVN":
            url = f"{API_BASE_URL}/api/telemetry/evn/project/{server_id}"
        else:
            url = f"{API_BASE_URL}/api/telemetry/project/{server_id}"

        inv_sns = [inv.get("serial_number") for inv in payload.get("inverters", []) if isinstance(inv, dict) and inv.get("serial_number")]
        sns_str = f".{{{', '.join(inv_sns)}}}" if inv_sns else ""

        try:
            logger.info(f"[Uploader] Sending IMMEDIATE {data_type} for project {server_id} to {url}{sns_str}...")
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 401:
                logger.warning(f"[Uploader] Immediate 401 for project {server_id}. Refreshing token...")
                token = self.auth.handle_unauthorized(proj_meta.server_account_id)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    resp = requests.post(url, json=payload, headers=headers, timeout=10)
            
            logger.info(f"[Uploader] Immediate result for project {server_id}: status={resp.status_code}")
        except Exception as e:
            logger.error(f"[Uploader] Immediate send error: {e}")
