# services/polling_service.py

import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from database.sqlite_manager import MetadataDB, RealtimeDB
from drivers.huawei_sun2000110KTL import HuaweiSUN2000
from communication.modbus_tcp import ModbusTCP
from communication.modbus_rtu import ModbusRTU
from services.normalization_service import NormalizationService
from services.tracking_service import TrackingService
from schemas.realtime import (
    InverterACRealtimeCreate, 
    ProjectRealtimeCreate,
    mpptRealtimeCreate,
    stringRealtimeCreate
)
import config

logger = logging.getLogger(__name__)

class PollingService:
    def __init__(self, metadata_db: MetadataDB, realtime_db: RealtimeDB, uploader=None, telemetry_service=None, cache_db=None):
        self.metadata_db = metadata_db
        self.realtime_db = realtime_db
        self.cache_db = cache_db
        self.uploader = uploader
        self.telemetry_service = telemetry_service
        self.normalization = NormalizationService()
        self.tracking = TrackingService(realtime_db)
        
        # Buffer {inverter_id: last_valid_raw_data}
        self.buffer: Dict[int, Dict[str, Any]] = {}
        # Theo dõi trạng thái để gửi instant alert
        self.last_states: Dict[int, int] = {} 
        self.last_faults: Dict[int, int] = {}
        self.transports = {}
        self.night_mode_projects: Dict[int, bool] = {}

    def _get_transport(self, brand: str):
        if "Huawei" in brand:
            key = f"TCP_{config.MODBUS_TCP_HOST}"
            if key not in self.transports:
                t = ModbusTCP(host=config.MODBUS_TCP_HOST, port=config.MODBUS_TCP_PORT)
                t.connect()
                self.transports[key] = t
            return self.transports[key]
        else:
            key = "RTU"
            if key not in self.transports:
                t = ModbusRTU(port=config.MODBUS_PORT, baudrate=config.MODBUS_BAUDRATE)
                t.connect()
                self.transports[key] = t
            return self.transports[key]

    def _get_driver(self, brand: str, transport, slave_id: int):
        if "Huawei" in brand:
            return HuaweiSUN2000(transport, slave_id=slave_id)
        elif "Sungrow" in brand:
            return SungrowSG110CXDriver(transport, slave_id=slave_id)
        return None

    def poll_all_inverters(self, project_id: int) -> float:
        """Quét tất cả inverter của dự án, trả về tổng công suất AC phát được"""
        self.tracking.check_resets()
        inverters = self.metadata_db.get_inverters_by_project(project_id)
        active_inverters = [inv for inv in inverters if inv.is_active]
        total_p_ac = 0.0
        
        for inv in active_inverters:
            try:
                transport = self._get_transport(inv.brand)
                driver = self._get_driver(inv.brand, transport, inv.slave_id)
                if not driver: continue
                
                raw_data = driver.read_all()
                if not raw_data: continue
                
                # Replacement logic
                read_serial = raw_data.get("serial_number")
                if read_serial and read_serial != inv.serial_number:
                    self._handle_inverter_replacement(inv, read_serial)
                    continue
                
                # Calculate E_monthly
                e_monthly = self.tracking.update_energy(inv.id, raw_data.get("e_total", 0.0) or 0.0)
                raw_data["e_monthly"] = e_monthly

                # Update Max Values & Check Reverse Polarity
                self.tracking.update_max_values(project_id, inv.id, raw_data, inv.mppt_count, inv.string_count)
                
                # Log errors if any
                self.tracking.log_inverter_error(inv, raw_data)
                
                # Check for instant alerts (Step 5)
                self._check_and_send_immediate(inv, raw_data)
                
                # Save to memory buffer
                self.buffer[inv.id] = raw_data
                
                # Save to Realtime Cache (Step 3, Type 2 - 10s update)
                if self.cache_db:
                    normalized = self.normalization.normalize(raw_data)
                    self.cache_db.upsert_latest_realtime(inv.id, project_id, normalized)
                
                # Accumulate total power for Night Mode check
                total_p_ac += normalized.get("p_inv_w", 0.0) or 0.0
                
            except Exception as e:
                logger.error(f"Error polling inverter {inv.id}: {e}")
        
        return total_p_ac

    def _check_and_send_immediate(self, inv: Any, raw_data: dict):
        """Kiểm tra thay đổi trạng thái hoặc lỗi để gửi ngay lên server"""
        current_state = raw_data.get("state_id")
        current_fault = raw_data.get("fault_code", 0)
        
        state_changed = (inv.id in self.last_states and self.last_states[inv.id] != current_state)
        fault_changed = (inv.id in self.last_faults and self.last_faults[inv.id] != current_fault)
        
        if (state_changed or fault_changed) and self.telemetry_service:
            logger.info(f"IMMEDIATE TRIGGER: Inverter {inv.id} changed state/fault. Sending full project telemetry.")
            # Tạo snapshot và đẩy vào buffer ngay lập tức
            self.telemetry_service.build_and_buffer(inv.project_id)
            # Kích hoạt uploader gửi ngay các bản ghi trong outbox
            if self.uploader:
                self.uploader.upload()
            
        self.last_states[inv.id] = current_state
        self.last_faults[inv.id] = current_fault

    def save_to_database(self, project_id: int):
        logger.info(f"Saving 5-minute snapshot for project {project_id}")
        now_str = datetime.now(timezone.utc).isoformat()
        inverters = self.metadata_db.get_inverters_by_project(project_id)
        
        ac_records, mppt_records, string_records = [], [], []
        p_sums = {"pac": 0.0, "pdc": 0.0, "edaily": 0.0, "emonthly": 0.0, "etotal": 0.0, "temp": -99.0}
        
        for inv in inverters:
            if not inv.is_active or inv.id not in self.buffer: continue
            
            data = self.buffer[inv.id]
            clean = self.normalization.normalize(data)
            
            # Helper to safely get clean float values
            def s_get(key, default=0.0):
                val = clean.get(key, default)
                return val if val is not None else default

            # AC
            inv_ac = InverterACRealtimeCreate(
                project_id=project_id, inverter_id=inv.id,
                IR=s_get("ir"), Temp_C=s_get("temp_c"),
                P_ac=s_get("p_inv_w"), Q_ac=s_get("q_inv_var"),
                V_a=s_get("v_a"), V_b=s_get("v_b"), V_c=s_get("v_c"),
                I_a=s_get("i_a"), I_b=s_get("i_b"), I_c=s_get("i_c"),
                PF=s_get("pf"), H=s_get("grid_hz"),
                E_daily=s_get("e_daily"), E_monthly=s_get("e_monthly"),
                E_total=s_get("e_total"), created_at=now_str
            )
            ac_records.append(inv_ac)
            
            # Trackers for this inv
            max_data = self.tracking.get_max_data(inv.id)
            
            # MPPT
            for i in range(1, inv.mppt_count + 1):
                v = s_get(f"mppt_{i}_voltage")
                curr = s_get(f"mppt_{i}_current")
                mx = max_data["mppt"].get(i, {"Max_V": 0, "Max_I": 0, "Max_P": 0})
                mppt_records.append(mpptRealtimeCreate(
                    project_id=project_id, inverter_id=inv.id, mppt_index=i,
                    V_mppt=v, I_mppt=curr, P_mppt=(v * curr) / 1000.0,
                    Max_I=mx["Max_I"], Max_V=mx["Max_V"], Max_P=mx["Max_P"],
                    created_at=now_str
                ))
            
            # String
            for i in range(1, inv.string_count + 1):
                m_id = (i - 1) // (inv.string_count // inv.mppt_count) + 1 if inv.mppt_count > 0 else 1
                curr = s_get(f"string_{i}_current")
                string_records.append(stringRealtimeCreate(
                    project_id=project_id, inverter_id=inv.id, mppt_id=m_id, string_id=i,
                    I_string=curr, max_I=max_data["string"].get(i, 0.0),
                    created_at=now_str
                ))
            
            # Sums
            p_sums["pac"] += inv_ac.P_ac
            p_sums["pdc"] += s_get("p_dc_w")
            p_sums["edaily"] += inv_ac.E_daily
            p_sums["emonthly"] += inv_ac.E_monthly
            p_sums["etotal"] += inv_ac.E_total
            p_sums["temp"] = max(p_sums["temp"], inv_ac.Temp_C)

        if ac_records:
            self.realtime_db.post_inverter_ac_batch(ac_records)
            self.realtime_db.post_mppt_batch(mppt_records)
            self.realtime_db.post_string_batch(string_records)
            self.realtime_db.post_project_realtime(ProjectRealtimeCreate(
                project_id=project_id, Temp_C=p_sums["temp"] if p_sums["temp"] > -99 else 0.0,
                P_ac=p_sums["pac"], P_dc=p_sums["pdc"], E_daily=p_sums["edaily"],
                E_monthly=p_sums["emonthly"], E_total=p_sums["etotal"],
                severity="STABLE", created_at=now_str
            ))
            
            # Step 3, Type 1: Lưu snapshot 5 phút cho server qua TelemetryService
            if self.telemetry_service:
                self.telemetry_service.build_and_buffer(project_id)
            
            logger.info(f"Database update total complete for project {project_id}")

    def _handle_inverter_replacement(self, old_inv: Any, new_serial: str):
        logger.info(f"REPLACEMENT: {old_inv.serial_number} -> {new_serial}")
        # Logic simplified, should theoretically refresh inverter list after this
        pass

    def run_forever(self):
        logger.info("PollingService started with multi-project & night-mode support")
        last_snapshot_time = 0
        
        while True:
            t0 = time.time()
            projects = self.metadata_db.get_all_projects()
            
            for project in projects:
                # Step 4: Check Night Mode
                is_night = self.night_mode_projects.get(project.id, False)
                
                # Nếu đang là ban đêm, chúng ta có thể giảm tần suất check 
                # Ở đây đơn giản là vẫn poll nhưng nếu P_ac vẫn 0 thì skip xử lý nặng
                # Hoặc skip hẳn việc gọi Modbus nếu muốn tối ưu tuyệt đối.
                # Tuy nhiên để "tự thức dậy", ta vẫn nên poll.
                
                total_p_ac = self.poll_all_inverters(project.id)
                
                # Cập nhật trạng thái Night Mode cho chu kỳ sau
                self.night_mode_projects[project.id] = (total_p_ac <= 0)
                if is_night and total_p_ac > 0:
                    logger.info(f"Project {project.id} woke up from Night Mode!")
                elif not is_night and total_p_ac <= 0:
                    logger.info(f"Project {project.id} entered Night Mode (P_ac=0)")

            # Step 3, Type 1: Lưu snapshot 5 phút cho server
            if time.time() - last_snapshot_time >= config.SNAPSHOT_INTERVAL:
                for project in projects:
                    self.save_to_database(project.id)
                last_snapshot_time = time.time()
                
            # Step 5: Thực hiện gửi dữ liệu lên server (cả snapshot định kỳ và dữ liệu tức thời nếu còn sót)
            if self.uploader:
                self.uploader.upload()

            # Duy trì chu kỳ POLL_INTERVAL (10s)
            elapsed = time.time() - t0
            sleep_time = max(0.1, config.POLL_INTERVAL - elapsed)
            time.sleep(sleep_time)
