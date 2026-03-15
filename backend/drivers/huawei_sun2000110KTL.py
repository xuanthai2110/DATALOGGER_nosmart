# drivers/huawei_sun2000110KTL.py

from typing import Dict, Any
from drivers.base import BaseDriver
class HuaweiSUN2000(BaseDriver):

    def __init__(self, transport, slave_id=1):
        self.transport = transport
        self.slave_id = slave_id

    # =========================================================
    # ================= REGISTER MAP ==========================
    # =========================================================
    fault_dict = {
        2001: {
            "fault_description": "High String Input Voltage",
            "repair_instruction": "Kiểm tra số tấm pin trong chuỗi và đo điện áp DC để đảm bảo không vượt điện áp tối đa của inverter.",
            "severity": "Error"
        },
        2002: {
            "fault_description": "DC Arc Fault",
            "repair_instruction": "Kiểm tra đầu nối MC4, dây DC và các điểm tiếp xúc lỏng gây hồ quang.",
            "severity": "Error"
        },
        2011: {
            "fault_description": "String Reverse Connection",
            "repair_instruction": "Kiểm tra cực tính dây DC (+/-) của chuỗi PV và đấu lại đúng cực.",
            "severity": "Error"
        },
        2012: {
            "fault_description": "String Current Backfeed",
            "repair_instruction": "Kiểm tra sự chênh lệch điện áp giữa các chuỗi và khả năng đấu nhầm hoặc diode lỗi.",
            "severity": "Warning"
        },
        2013: {
            "fault_description": "Abnormal String Power",
            "repair_instruction": "Kiểm tra tấm pin bị che bóng, bẩn, hỏng hoặc mismatch giữa các chuỗi.",
            "severity": "Warning"
        },
        2021: {
            "fault_description": "AFCI Self-Check Fail",
            "repair_instruction": "Khởi động lại inverter. Nếu lỗi tiếp tục xảy ra cần kiểm tra module AFCI hoặc liên hệ hãng.",
            "severity": "Error"
        },
        2031: {
            "fault_description": "Phase Wire Short-Circuited to PE",
            "repair_instruction": "Kiểm tra dây AC pha và dây tiếp địa có bị chạm nhau hay không.",
            "severity": "Error"
        },
        2032: {
            "fault_description": "Grid Loss",
            "repair_instruction": "Kiểm tra nguồn lưới, ACB/MCCB AC và trạng thái điện lưới tại điểm đấu nối.",
            "severity": "Error"
        },
        2033: {
            "fault_description": "Grid Undervoltage",
            "repair_instruction": "Đo điện áp lưới tại điểm đấu nối và kiểm tra máy biến áp hoặc dây dẫn.",
            "severity": "Error"
        },
        2034: {
            "fault_description": "Grid Overvoltage",
            "repair_instruction": "Kiểm tra điện áp lưới và cấu hình grid code của inverter.",
            "severity": "Error"
        },
        2035: {
            "fault_description": "Grid Voltage Imbalance",
            "repair_instruction": "Kiểm tra cân bằng điện áp giữa các pha lưới.",
            "severity": "Error"
        },
        2036: {
            "fault_description": "Grid Overfrequency",
            "repair_instruction": "Kiểm tra tần số lưới và cấu hình grid code.",
            "severity": "Error"
        },
        2037: {
            "fault_description": "Grid Underfrequency",
            "repair_instruction": "Kiểm tra nguồn điện lưới hoặc máy phát.",
            "severity": "Error"
        },
        2038: {
            "fault_description": "Unstable Grid Frequency",
            "repair_instruction": "Kiểm tra chất lượng điện lưới.",
            "severity": "Error"
        },
        2039: {
            "fault_description": "Output Overcurrent",
            "repair_instruction": "Kiểm tra dây AC, tải AC và khả năng ngắn mạch.",
            "severity": "Error"
        },
        2040: {
            "fault_description": "Output DC Component Overhigh",
            "repair_instruction": "Khởi động lại inverter và kiểm tra mạch inverter nếu lỗi tiếp tục.",
            "severity": "Error"
        },
        2051: {
            "fault_description": "Abnormal Residual Current",
            "repair_instruction": "Kiểm tra rò điện từ hệ thống PV xuống đất.",
            "severity": "Error"
        },
        2061: {
            "fault_description": "Abnormal Grounding",
            "repair_instruction": "Kiểm tra hệ thống tiếp địa của inverter và khung pin.",
            "severity": "Error"
        },
        2062: {
            "fault_description": "Low Insulation Resistance",
            "repair_instruction": "Đo điện trở cách điện giữa DC và đất, kiểm tra cáp hoặc tấm pin.",
            "severity": "Error"
        },
        2063: {
            "fault_description": "Overtemperature",
            "repair_instruction": "Kiểm tra thông gió, vệ sinh quạt và bộ tản nhiệt.",
            "severity": "Warning"
        },
        2064: {
            "fault_description": "Device Fault",
            "repair_instruction": "Khởi động lại inverter, nếu lỗi vẫn còn cần liên hệ hãng.",
            "severity": "Error"
        },
        2065: {
            "fault_description": "Upgrade Failed or Version Mismatch",
            "repair_instruction": "Kiểm tra firmware và thực hiện nâng cấp lại.",
            "severity": "Warning"
        },
        2066: {
            "fault_description": "License Expired",
            "repair_instruction": "Gia hạn hoặc cập nhật license thiết bị.",
            "severity": "Warning"
        },
        2067: {
            "fault_description": "Faulty Power Collector",
            "repair_instruction": "Kiểm tra datalogger hoặc power collector.",
            "severity": "Error"
        },
        2068: {
            "fault_description": "Battery Abnormal",
            "repair_instruction": "Kiểm tra hệ thống pin hoặc hệ thống lưu trữ.",
            "severity": "Warning"
        },
        2070: {
            "fault_description": "Active Islanding",
            "repair_instruction": "Kiểm tra kết nối lưới và relay bảo vệ chống islanding.",
            "severity": "Error"
        },
        2071: {
            "fault_description": "Passive Islanding",
            "repair_instruction": "Kiểm tra tín hiệu lưới và relay bảo vệ.",
            "severity": "Error"
        },
        2072: {
            "fault_description": "Transient AC Overvoltage",
            "repair_instruction": "Kiểm tra SPD và chất lượng điện lưới.",
            "severity": "Error"
        },
        2075: {
            "fault_description": "Peripheral Port Short Circuit",
            "repair_instruction": "Kiểm tra các cổng giao tiếp và thiết bị ngoại vi.",
            "severity": "Warning"
        },
        2080: {
            "fault_description": "Abnormal PV Module Configuration",
            "repair_instruction": "Kiểm tra cấu hình chuỗi PV.",
            "severity": "Error"
        },
        2081: {
            "fault_description": "Optimizer Fault",
            "repair_instruction": "Kiểm tra optimizer hoặc thiết bị MLPE.",
            "severity": "Warning"
        },
        2086: {
            "fault_description": "External Fan Abnormal",
            "repair_instruction": "Kiểm tra quạt làm mát bên ngoài inverter.",
            "severity": "Error"
        },
        2087: {
            "fault_description": "Internal Fan Abnormal",
            "repair_instruction": "Kiểm tra quạt làm mát bên trong inverter.",
            "severity": "Error"
        },
        2088: {
            "fault_description": "DC Protection Unit Abnormal",
            "repair_instruction": "Kiểm tra bộ bảo vệ DC hoặc cầu chì DC.",
            "severity": "Error"
        },
        2093: {
            "fault_description": "DC Switch Abnormal",
            "repair_instruction": "Kiểm tra công tắc DC và tiếp điểm.",
            "severity": "Warning"
        }
    }
    DEVICE_STATUS_DICT = {
        0x0000: "Standby: initializing",
        0x0001: "Standby: detecting insulation resistance",
        0x0002: "Standby: detecting irradiation",
        0x0003: "Standby: grid detecting",

        0x0100: "Starting",

        0x0200: "On-grid running",
        0x0201: "Grid connection: power limited",
        0x0202: "Grid connection: self-derating",
        0x0203: "Off-grid running",

        0x0300: "Shutdown: fault",
        0x0301: "Shutdown: command",
        0x0302: "Shutdown: OVGR",
        0x0303: "Shutdown: communication disconnected",
        0x0304: "Shutdown: power limited",
        0x0305: "Shutdown: manual startup required",
        0x0306: "Shutdown: DC switches disconnected",
        0x0307: "Shutdown: rapid cutoff",
        0x0308: "Shutdown: input underpower",

        0x0401: "Grid scheduling: cosφ-P curve",
        0x0402: "Grid scheduling: Q-U curve",
        0x0403: "Grid scheduling: PF-U curve",
        0x0404: "Grid scheduling: dry contact",
        0x0405: "Grid scheduling: Q-P curve",

        0x0500: "Spot-check ready",
        0x0501: "Spot-checking",

        0x0600: "Inspecting",

        0x0700: "AFCI self check",

        0x0800: "I-V scanning",

        0x0900: "DC input detection",
    }
    def register_map(self) -> Dict[str, Any]:

        return {

            "info": [
                {"name": "serial_number", "address": 30015, "length": 10, "type": "string", "scale": None},
                {"name": "string_count", "address": 30071, "length": 1, "type": "uint16", "scale": None},
                {"name": "mppt_count", "address": 30072, "length": 1, "type": "uint16", "scale": None},
                {"name": "rate_dc_kwp", "address": 30073, "length": 2, "type": "uint32", "scale": 0.001},
                {"name": "rate_ac_kw", "address": 30075, "length": 2, "type": "uint32", "scale": 0.001},
            ],

            "ac": [
                {"name": "v_a", "address": 32069, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "v_b", "address": 32070, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "v_c", "address": 32071, "length": 1, "type": "uint16", "scale": 0.1},

                {"name": "i_a", "address": 32072, "length": 2, "type": "sint32", "scale": 0.001},    
                {"name": "i_b", "address": 32074, "length": 2, "type": "sint32", "scale": 0.001},
                {"name": "i_c", "address": 32076, "length": 2, "type": "sint32", "scale": 0.001},

                {"name": "p_inv_w", "address": 32080, "length": 2, "type": "sint32", "scale": 0.001},
                {"name": "q_inv_var", "address": 32082, "length": 2, "type": "sint32", "scale": 0.001},
                {"name": "pf", "address": 32084, "length": 1, "type": "sint16", "scale": 0.001},
                {"name": "grid_hz", "address": 32085, "length": 1, "type": "uint16", "scale": 0.01},
            ],

            "dc": [
                {"name": "p_dc_w", "address": 32064, "length": 2, "type": "uint32", "scale": 0.001},

                {"name": "mppt_1_voltage", "address": 32016, "length": 1, "type": "sint16", "scale": 0.1},
                {"name": "mppt_2_voltage", "address": 32018, "length": 1, "type": "sint16", "scale": 0.1},
                {"name": "mppt_3_voltage", "address": 32020, "length": 1, "type": "sint16", "scale": 0.1},
                {"name": "mppt_4_voltage", "address": 32022, "length": 1, "type": "sint16", "scale": 0.1},
                {"name": "mppt_5_voltage", "address": 32024, "length": 1, "type": "sint16", "scale": 0.1},
                {"name": "mppt_6_voltage", "address": 32026, "length": 1, "type": "sint16", "scale": 0.1},
                {"name": "mppt_7_voltage", "address": 32028, "length": 1, "type": "sint16", "scale": 0.1},
                {"name": "mppt_8_voltage", "address": 32030, "length": 1, "type": "sint16", "scale": 0.1},
                {"name": "mppt_9_voltage", "address": 32032, "length": 1, "type": "sint16", "scale": 0.1},
                {"name": "mppt_10_voltage", "address": 32034, "length": 1, "type": "sint16", "scale": 0.1},
            ],

            "string": [
                {
                    "name": f"string_{i}_current",
                    "address": 32017 + (i - 1) * 2,
                    "length": 1,
                    "type": "sint16",
                    "scale": 0.01
                }
                for i in range(1, 21)
            ],

            "stat": [
                # Nhiệt độ bộ tản nhiệt inverter (C)
                {"name": "temp_c",   "address": 32087, "length": 1, "type": "sint16", "scale": 0.1},
                # Điện trở cách điện PV (Ω)
                {"name": "ir",       "address": 32088, "length": 1, "type": "uint16", "scale": 1},
                # Sản lượng ngày (kWh)
                {"name": "e_daily",  "address": 32114, "length": 2, "type": "uint32", "scale": 0.01},
                # Sản lượng tổng (kWh)
                {"name": "e_total",  "address": 32106, "length": 2, "type": "uint32", "scale": 0.1},
            ]

        }

    # =========================================================
    # ================= MODBUS READ ===========================
    # =========================================================

    def _read_block(self, start: int, length: int):

        response = self.transport.read_holding_registers(
            address=start,
            count=length,
            slave=self.slave_id
        )

        if response.isError():
            raise Exception("Modbus read error")

        return response.registers

    # =========================================================
    # ================= PARSER ================================
    # =========================================================

    def _convert(self, registers, data_type):

        if not registers:
            return None

        if data_type == "uint16":
            return registers[0] & 0xFFFF

        if data_type == "sint16":
            v = registers[0] & 0xFFFF
            if v & 0x8000:
                v -= 0x10000
            return v

        # Huawei word order: high word first

        if data_type == "uint32":
            high = registers[0]
            low = registers[1]
            return ((high & 0xFFFF) << 16) | (low & 0xFFFF)

        if data_type == "sint32":
            high = registers[0]
            low = registers[1]

            v = ((high & 0xFFFF) << 16) | (low & 0xFFFF)

            if v & 0x80000000:
                v -= 0x100000000

            return v

        if data_type == "string":

            raw_bytes = bytearray()

            for reg in registers:
                high = (reg >> 8) & 0xFF
                low = reg & 0xFF
                raw_bytes.append(high)
                raw_bytes.append(low)

            return raw_bytes.decode("utf-8", errors="ignore").rstrip("\x00").strip()

        return None

    # =========================================================
    # ================= PARSE BLOCK ===========================
    # =========================================================

    def parse(self, raw_block: Dict[str, Any], reg_list: list = None) -> Dict[str, Any]:
        """ Implement base parsing compatibility. The original API takes block and list. """
        if reg_list is None:
            return {}

        result = {}
        offset = 0

        for reg in reg_list:

            length = reg["length"]

            raw = raw_block[offset: offset + length]

            value = self._convert(raw, reg["type"])

            if value is not None and reg["scale"] is not None:
                value *= reg["scale"]

            result[reg["name"]] = value

            offset += length

        return result

    # =========================================================
    # ================= READ GROUPS ===========================
    # =========================================================

    def read_info(self) -> Dict[str, Any]:
        from datetime import datetime
        try:
            regs = self.register_map()["info"]

            start = min(r["address"] for r in regs)
            end = max(r["address"] + r["length"] - 1 for r in regs)

            raw = self._read_block(start, end - start + 1)

            ordered = []

            for r in regs:
                idx = r["address"] - start
                ordered.extend(raw[idx: idx + r["length"]])

            parsed = self.parse(ordered, regs)

            rate_dc = parsed.get("rate_dc_kwp", 110.0)
            rate_ac = parsed.get("rate_ac_kw", 110.0)
            
            # Nếu giá trị đọc được là W (ví dụ 110000), scale 0.001 sẽ biến nó thành 110.0 kW.
            # Nếu scale đã được áp dụng trong self.parse, rate_dc/ac sẽ là float.

            return {
                "brand": "Huawei",
                "model": "SUN2000-110KTL",
                "serial_number": parsed.get("serial_number", ""),
                "capacity_kw": rate_ac,
                "mppt_count": int(parsed.get("mppt_count", 10)),
                "firmware_version": "1.0",
                "phase_count": 3,
                "string_count": int(parsed.get("string_count", 20)),
                "rate_dc_kwp": rate_dc,
                "rate_ac_kw": rate_ac,
                "is_active": True,
                "slave_id": self.slave_id,
                "usage_start_at": datetime.now().isoformat(),
                "usage_end_at": None,
                "replaced_by_id": None
            }
        except Exception as e:
            return {
                "brand": "Huawei",
                "model": "SUN2000-110KTL",
                "serial_number": "",
                "capacity_kw": 110.0,
                "mppt_count": 10,
                "firmware_version": "1.0",
                "phase_count": 3,
                "string_count": 20,
                "rate_dc_kwp": 110.0,
                "rate_ac_kw": 110.0,
                "is_active": False,
                "slave_id": self.slave_id,
                "usage_start_at": datetime.now().isoformat(),
                "usage_end_at": None,
                "replaced_by_id": None
            }

    def read_ac(self) -> Dict[str, Any]:

        regs = self.register_map()["ac"]

        start = min(r["address"] for r in regs)
        end = max(r["address"] + r["length"] - 1 for r in regs)

        raw = self._read_block(start, end - start + 1)

        ordered = []

        for r in regs:
            idx = r["address"] - start
            ordered.extend(raw[idx: idx + r["length"]])

        return self.parse(ordered, regs)

    def read_dc(self) -> Dict[str, Any]:

        regs = self.register_map()["dc"]

        start = min(r["address"] for r in regs)
        end = max(r["address"] + r["length"] - 1 for r in regs)

        raw = self._read_block(start, end - start + 1)

        ordered = []

        for r in regs:
            idx = r["address"] - start
            ordered.extend(raw[idx: idx + r["length"]])

        return self.parse(ordered, regs)

    def read_string(self) -> Dict[str, Any]:

        regs = self.register_map()["string"]

        start = regs[0]["address"]
        end = regs[-1]["address"]

        raw = self._read_block(start, end - start + 1)

        result = {}

        for r in regs:

            idx = r["address"] - start
            val = self._convert([raw[idx]], r["type"])

            if val is not None:
                val *= r["scale"]

            result[r["name"]] = val

        return result

    def read_stat(self) -> Dict[str, Any]:
        """Đọc thống kê vận hành: nhiệt độ, điện trở cách điện, sản lượng ngày và tổng."""
        regs  = self.register_map()["stat"]
        start = min(r["address"] for r in regs)
        end   = max(r["address"] + r["length"] - 1 for r in regs)
        raw   = self._read_block(start, end - start + 1)
        ordered = []
        for r in regs:
            idx = r["address"] - start
            ordered.extend(raw[idx: idx + r["length"]])
        return self.parse(ordered, regs)

    # =========================================================
    # ================= FAULTS & STATES =======================
    # =========================================================

    def read_states_and_faults(self) -> str:
        """
        Đọc trạng thái và lỗi từ inverter Huawei:
        - Đọc state (32089)
        - Đọc fault (32090)
        - Nếu có fault > 0, trả về JSON của Fault (dùng mapping TÙY CHỈNH dataLogger)
        - Nếu không có fault, trả về JSON của State (dùng mapping TÙY CHỈNH dataLogger)
        """
        import json
        from services.fault_state_service import (
            HUAWEI_STATE_MAP, 
            HUAWEI_FAULT_MAP, 
            UNIFIED_STATES, 
            UNIFIED_FAULTS,
            create_unified_fault_payload
        )

        # Ánh xạ mã Modbus status (32089) sang id_huawei (0-13) theo HUAWEI_STATE_MAP
        MODBUS_TO_HUAWEI_STATE = {
            0x0000: 0,  # INITIAL_STANDBY
            0x0001: 2,  # INSULATION_CHECK
            0x0002: 1,  # GRID_DETECTING
            0x0003: 1,  # GRID_DETECTING
            0x0100: 4,  # STARTING
            0x0200: 5,  # RUNNING
            0x0201: 7,  # DERATING
            0x0202: 7,  # DERATING
            0x0203: 5,  # RUNNING (Off-grid)
            0x0300: 9,  # FAULT
            0x0301: 8,  # STOPPED
            0x0302: 9,  # FAULT (OVGR)
            0x0303: 9,  # FAULT (Comm disconnect)
            0x0304: 8,  # STOPPED (Power limited)
            0x0305: 8,  # STOPPED (Manual startup req)
            0x0306: 8,  # STOPPED (DC disconnect)
            0x0307: 8,  # STOPPED (Rapid cutoff)
            0x0308: 8,  # STOPPED (Input underpower)
        }

        # 1. Đọc Device Status
        res_state = self.transport.read_holding_registers(
            address=32089,
            count=1,
            slave=self.slave_id
        )

        if res_state.isError():
            err_payload = create_unified_fault_payload(
                fault_code=None,
                fault_description="Modbus error: cannot read register 32089",
                repair_instruction="Kiểm tra kết nối cáp RS485/TCP tới inverter",
                severity="ERROR"
            )
            return json.dumps(err_payload, ensure_ascii=False)

        status_code = res_state.registers[0]
        id_huawei = MODBUS_TO_HUAWEI_STATE.get(status_code, 5) # Default RUNNING
        hw_state = HUAWEI_STATE_MAP.get(id_huawei)

        unified_status_id = None
        unified_status_name = None
        
        if hw_state:
            unified_status_id = hw_state["id_unified"]
            unified_status_name = UNIFIED_STATES.get(unified_status_id, "Unknown State")

        # 2. Đọc Fault
        res_fault = self.transport.read_holding_registers(
            address=32090,
            count=1,
            slave=self.slave_id
        )

        if res_fault.isError():
            err_payload = create_unified_fault_payload(
                fault_code=None,
                fault_description="Modbus error: cannot read register 32090",
                repair_instruction="Kiểm tra kết nối cáp RS485/TCP tới inverter",
                severity="ERROR"
            )
            return json.dumps(err_payload, ensure_ascii=False)

        fault_code = res_fault.registers[0]

        # 3. Trả về
        if fault_code != 0:
            hw_fault = HUAWEI_FAULT_MAP.get(fault_code)
            if hw_fault:
                unified_fault_id = hw_fault["id_unified"]
                payload = create_unified_fault_payload(
                    fault_code=unified_fault_id,
                    fault_description=UNIFIED_FAULTS.get(unified_fault_id, hw_fault["name"]),
                    repair_instruction=hw_fault["repair_instruction"],
                    severity=hw_fault["severity"],
                    state_id=unified_status_id,
                    state_name=unified_status_name
                )
            else:
                # Lỗi không có trong mapping
                payload = create_unified_fault_payload(
                    fault_code=fault_code,
                    fault_description=f"Unknown Huawei Fault: {fault_code}",
                    repair_instruction="Tra cứu tài liệu hướng dẫn sử dụng của Huawei",
                    severity="ERROR",
                    state_id=unified_status_id,
                    state_name=unified_status_name
                )
        else:
            # Không có lỗi
            payload = create_unified_fault_payload(
                fault_code=0,
                severity=hw_state["severity"] if hw_state else "STABLE",
                state_id=unified_status_id,
                state_name=unified_status_name
            )

        # Trả về chuỗi JSON
        return json.dumps(payload, ensure_ascii=False)


    # =========================================================
    # ================= READ ALL ==============================
    # =========================================================

    def read_all(self) -> Dict[str, Any]:
        import json
        data = {}

        data.update(self.read_info())
        data.update(self.read_ac())

        dc = self.read_dc()
        strings = self.read_string()

        data.update(dc)
        data.update(strings)

        # Đọc thống kê: nhiệt độ, IR, sản lượng ngày/tổng
        try:
            data.update(self.read_stat())
        except Exception:
            pass

        # calculate MPPT current
        for i in range(1, 11):
            s1 = strings.get(f"string_{2*i-1}_current")
            s2 = strings.get(f"string_{2*i}_current")
            if s1 is not None and s2 is not None:
                data[f"mppt_{i}_current"] = s1 + s2

        # Đọc trạng thái và lỗi
        try:
            states_and_faults = self.read_states_and_faults()
            data.update(json.loads(states_and_faults))
        except Exception:
            pass

        return data


    # =========================================================
    # ================= CONTROL ===============================
    # =========================================================

    def enable_power_limit(self, enable: bool) -> bool:
        # Tạm thời chưa có địa chỉ cho enable limit riêng trên Huawei
        return True

    def write_power_limit_kw(self, kw: float) -> bool:
        return self.set_power_kw(kw)

    def set_power_percent(self, percent):

        addr = 40125

        value = int(percent * 10)

        self.transport.write_register(
            address=addr,
            value=value,
            slave=self.slave_id
        )

        return True


    # --------------------------------
    # Set power limit by kW
    # --------------------------------
    def set_power_kw(self, kw):

        addr = 40120

        value = int(kw * 10)

        self.transport.write_register(
            address=addr,
            value=value,
            slave=self.slave_id
        )

        return True


    # --------------------------------
    # Set power limit by W
    # --------------------------------
    def set_power_w(self, watt):

        addr = 40126

        high = (watt >> 16) & 0xFFFF
        low = watt & 0xFFFF

        # Thay vì viết thuần pymodbus, ta sử dụng method write_multiple_registers của communication ModbusTCP
        self.transport.write_multiple_registers(
            address=addr,
            values=[high, low],
            slave=self.slave_id
        )

        return True


    # --------------------------------
    # Read power limit
    # --------------------------------
    def read_power_limit(self):

        # Huawei requires 35300-35303 to be read as a single block.
        # Otherwise, reading individually may cause Exception 131 IllegalValue.
        res = self.transport.read_holding_registers(
            address=35300,
            count=4,
            slave=self.slave_id
        )

        if res.isError():
            raise Exception(f"Read power limit failed: {res}")

        regs = res.registers

        # 35300 (Mode)
        mode = regs[0]

        # 35302, 35303 (Active power limit)
        limit_w = (regs[2] << 16) + regs[3]

        return {
            "mode": mode,
            "limit_w": limit_w
        }

    # --------------------------------
    # Read actual inverter power
    # --------------------------------
    def read_power(self):

        res = self.transport.read_holding_registers(
            address=32080,
            count=2,
            slave=self.slave_id
        )

        if res.isError():
            raise Exception(f"Read inverter power failed: {res}")

        regs = res.registers

        value = (regs[0] << 16) + regs[1]

        if value > 0x7FFFFFFF:
            value -= 0x100000000

        return value

