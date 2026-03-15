# services/polling_service.py

import time
import logging
from datetime import datetime
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
    def __init__(self, metadata_db: MetadataDB, realtime_db: RealtimeDB):
        self.metadata_db = metadata_db
        self.realtime_db = realtime_db
        self.normalization = NormalizationService()
        self.tracking = TrackingService(realtime_db)
        
        # Buffer {inverter_id: last_valid_raw_data}
        self.buffer: Dict[int, Dict[str, Any]] = {}
        self.transports = {}

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

    def poll_all_inverters(self, project_id: int):
        self.tracking.check_resets()
        inverters = self.metadata_db.get_inverters_by_project(project_id)
        active_inverters = [inv for inv in inverters if inv.is_active]
        
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
                
                self.buffer[inv.id] = raw_data
                
            except Exception as e:
                logger.error(f"Error polling inverter {inv.id}: {e}", exc_info=True)

    def save_to_database(self, project_id: int):
        logger.info(f"Saving 5-minute snapshot for project {project_id}")
        now_str = datetime.now().isoformat()
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
                severity="NORMAL", created_at=now_str
            ))
            logger.info(f"Database update complete for project {project_id}")

    def _handle_inverter_replacement(self, old_inv: Any, new_serial: str):
        logger.info(f"REPLACEMENT: {old_inv.serial_number} -> {new_serial}")
        # Logic simplified, should theoretically refresh inverter list after this
        pass

    def run_forever(self):
        project = self.metadata_db.get_project_first()
        if not project: return
        logger.info(f"PollingService started for {project.name}")
        poll_count = 0
        while True:
            t0 = time.time()
            self.poll_all_inverters(project.id)
            poll_count += 1
            if poll_count >= 10:
                self.save_to_database(project.id)
                poll_count = 0
            time.sleep(max(0.1, config.POLL_INTERVAL - (time.time() - t0)))
