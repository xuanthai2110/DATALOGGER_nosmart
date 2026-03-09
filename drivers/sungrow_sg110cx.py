# drivers/sungrow_sg110cx.py

from typing import Dict, Any
from drivers.base_driver import BaseDriver

class SungrowSG110CXDriver(BaseDriver):

    def __init__(self, transport, slave_id: int):
        self.transport = transport
        self.slave_id = slave_id

    # =========================================================
    # ================= REGISTER MAP ==========================
    # =========================================================

    def register_map(self):

        return {
            "info": [
                {"name": "serial_number", "address": 4990, "length": 10, "type": "string", "scale": None},
                {"name": "type_code", "address": 5000, "length": 1, "type": "uint16", "scale": None},
                {"name": "rated_power", "address": 5001, "length": 1, "type": "uint16", "scale": 0.1},
            ],

            "ac": [
                {"name": "v_a", "address": 5019, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "v_b", "address": 5020, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "v_c", "address": 5021, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "i_a", "address": 5022, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "i_b", "address": 5023, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "i_c", "address": 5024, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "p_inv_w", "address": 5031, "length": 2, "type": "uint32", "scale": 1},
                {"name": "q_inv_var", "address": 5033, "length": 2, "type": "sint32", "scale": 1},
                {"name": "pf", "address": 5035, "length": 1, "type": "sint16", "scale": 0.001},
                {"name": "grid_hz", "address": 5148, "length": 1, "type": "uint16", "scale": 0.01},
            ],

            "dc": [
                {"name": "p_dc_w", "address": 5017, "length": 2, "type": "uint32", "scale": 1},
                {"name": "mppt_1_voltage", "address": 5011, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_1_current", "address": 5012, "length": 1, "type": "uint16", "scale": 0.1}, 
                { "name": "mppt_2_voltage", "address": 5013, "length": 1, "type": "uint16", "scale": 0.1 }, 
                { "name": "mppt_2_current", "address": 5014, "length": 1, "type": "uint16", "scale": 0.1 }, 
                { "name": "mppt_3_voltage", "address": 5015, "length": 1, "type": "uint16", "scale": 0.1 }, 
                { "name": "mppt_3_current", "address": 5016, "length": 1, "type": "uint16", "scale": 0.1 }, 
                { "name": "mppt_4_voltage", "address": 5115, "length": 1, "type": "uint16", "scale": 0.1 }, 
                { "name": "mppt_4_current", "address": 5116, "length": 1, "type": "uint16", "scale": 0.1 }, 
                { "name": "mppt_5_voltage", "address": 5117, "length": 1, "type": "uint16", "scale": 0.1 }, 
                { "name": "mppt_5_current", "address": 5118, "length": 1, "type": "uint16", "scale": 0.1 }, 
                { "name": "mppt_6_voltage", "address": 5119, "length": 1, "type": "uint16", "scale": 0.1 }, 
                { "name": "mppt_6_current", "address": 5120, "length": 1, "type": "uint16", "scale": 0.1 }, 
                { "name": "mppt_7_voltage", "address": 5121, "length": 1, "type": "uint16", "scale": 0.1 }, 
                { "name": "mppt_7_current", "address": 5122, "length": 1, "type": "uint16", "scale": 0.1 }, 
                { "name": "mppt_8_voltage", "address": 5123, "length": 1, "type": "uint16", "scale": 0.1 }, 
                { "name": "mppt_8_current", "address": 5124, "length": 1, "type": "uint16", "scale": 0.1 }, 
                { "name": "mppt_9_voltage", "address": 5130, "length": 1, "type": "uint16", "scale": 0.1 }, { "name": "mppt_9_current", "address": 5131, "length": 1, "type": "uint16", "scale": 0.1 },
            ],

            "string": [
                {"name": f"string_{i}_current",
                 "address": 7012 + i,
                 "length": 1,
                 "type": "uint16",
                 "scale": 0.01}
                for i in range(1, 19)
            ]
        }

    # =========================================================
    # ================= LOW LEVEL READ ========================
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

    def _convert(self, registers: list[int], data_type: str,):

        if not registers:
            return None
        # ================= 16-bit =================
        if data_type == "uint16":
            val = registers[0]
            if val is None:
                return None
            return val & 0xFFFF
        if data_type == "sint16":
            val = registers[0]
            if val is None:
                return None
            v = val & 0xFFFF
            if v & 0x8000:
                v -= 0x10000
            return v
        # ================= 32-bit =================
        # Sungrow SG110CX:
        # low address = low word
        # registers = [low, high]
        if data_type == "uint32":
            if len(registers) < 2:
                return None

            low = registers[0]
            high = registers[1]

            if low is None or high is None:
                return None

            return ((high & 0xFFFF) << 16) | (low & 0xFFFF)
        if data_type == "sint32":
            if len(registers) < 2:
                return None
            low = registers[0]
            high = registers[1]
            if low is None or high is None:
                return None
            v = ((high & 0xFFFF) << 16) | (low & 0xFFFF)
            if v & 0x80000000:
                v -= 0x100000000
            return v
        # ================= STRING =================
        if data_type == "string":
            raw_bytes = bytearray()
            for reg in registers:
                high = (reg >> 8) & 0xFF
                low = reg & 0xFF
                raw_bytes.append(high)
                raw_bytes.append(low)
            return raw_bytes.decode("utf-8", errors="ignore").rstrip("\x00").strip()
        
        if scale is not None and value is not None:
            value *= scale
            return value
        return None

    def parse(self, raw_block, reg_list):

        result = {}
        offset = 0

        for reg in reg_list:
            length = reg["length"]
            raw = raw_block[offset: offset + length]
            value = self._convert(raw, reg["type"])

            if reg["scale"] is not None:
                value = value * reg["scale"]

            result[reg["name"]] = value
            offset += length

        return result

    # =========================================================
    # ================= READ GROUPS ===========================
    # =========================================================

    def read_ac(self):
        regs = self.register_map()["ac"]
        start = min(r["address"] for r in regs)
        end = max(r["address"] + r["length"] - 1 for r in regs)

        raw = self._read_block(start, end - start + 1)

        # cắt lại đúng thứ tự
        ordered = []
        for r in regs:
            idx = r["address"] - start
            ordered.extend(raw[idx: idx + r["length"]])

        return self.parse(ordered, regs)

    def read_dc(self):
        regs = self.register_map()["dc"]
        start = min(r["address"] for r in regs)
        end = max(r["address"] + r["length"] - 1 for r in regs)

        raw = self._read_block(start, end - start + 1)

        ordered = []
        for r in regs:
            idx = r["address"] - start
            ordered.extend(raw[idx: idx + r["length"]])

        return self.parse(ordered, regs)

    def read_info(self):
        regs = self.register_map()["info"]
        start = min(r["address"] for r in regs)
        end = max(r["address"] + r["length"] - 1 for r in regs)

        raw = self._read_block(start, end - start + 1)

        ordered = []
        for r in regs:
            idx = r["address"] - start
            ordered.extend(raw[idx: idx + r["length"]])

        return self.parse(ordered, regs)

    def read_string(self):
        result = {}
        regs = self.register_map()["string"]

        for r in regs:
            raw = self._read_block(r["address"], 1)
            val = self._convert(raw, r["type"])
            result[r["name"]] = val * r["scale"]

        return result

    def read_all(self):

        import json

        data = {}
        data.update(self.read_info())
        data.update(self.read_ac())
        data.update(self.read_dc())
        data.update(self.read_string())
        data.update(self.read_states_and_faults())
        # Include states and faults
        try:
            states_and_faults = self.read_states_and_faults()
            data.update(json.loads(states_and_faults))
        except Exception as e:
            pass

        return data

    # =========================================================
    # ================= CONTROL ===============================
    # =========================================================

    def enable_power_limit(self, enable: bool) -> bool:
        # ví dụ địa chỉ giả định
        addr = 6000
        value = 1 if enable else 0

        self.transport.write_register(
            address=addr,
            value=value,
            slave=self.slave_id
        )
        return True

    def write_power_limit_kw(self, kw: float) -> bool:
        addr = 6001
        value = int(kw * 10)  # scale 0.1

        self.transport.write_register(
            address=addr,
            value=value,
            slave=self.slave_id
        )
        return True

    # =========================================================
    # ================= FAULTS & STATES =======================
    # =========================================================

    def read_states_and_faults(self) -> str:
        """
        Đọc trạng thái inverter (register 5038 -> address 5037) và fault (5039 -> address 5038).
        Trả về JSON được tạo từ hàm create_unified_fault_payload.
        """
        import json
        from services.fault_state_service import (
            SUNGROW_STATE_MAP, 
            SUNGROW_FAULT_MAP, 
            UNIFIED_STATES, 
            UNIFIED_FAULTS, 
            create_unified_fault_payload
        )

        # 1. Đọc device status tại 5038 (address 5037)
        res_state = self.transport.read_holding_registers(
            address=5037,
            count=1,
            slave=self.slave_id
        )

        if res_state.isError():
            err_payload = create_unified_fault_payload(
                fault_code=None,
                fault_description="Modbus error: cannot read state register 5037",
                repair_instruction="Kiểm tra kết nối cáp RS485/TCP tới inverter",
                severity="ERROR"
            )
            return json.dumps(err_payload, ensure_ascii=False)

        status_code = res_state.registers[0]
        sg_state = SUNGROW_STATE_MAP.get(status_code)

        unified_status_id = None
        unified_status_name = None
        
        if sg_state:
            unified_status_id = sg_state["id_unified"]
            unified_status_name = UNIFIED_STATES.get(unified_status_id, "Unknown State")

        # 2. Đọc fault code tại 5039 (address 5038)
        res_fault = self.transport.read_holding_registers(
            address=5038,
            count=1,
            slave=self.slave_id
        )

        if res_fault.isError():
            err_payload = create_unified_fault_payload(
                fault_code=None,
                fault_description="Modbus error: cannot read fault register 5038",
                repair_instruction="Kiểm tra kết nối cáp RS485/TCP tới inverter",
                severity="ERROR"
            )
            return json.dumps(err_payload, ensure_ascii=False)

        fault_code = res_fault.registers[0]

        # 3. Form payload
        if fault_code != 0:
            sg_fault = SUNGROW_FAULT_MAP.get(fault_code)

            if sg_fault:
                unified_fault_id = sg_fault["id_unified"]
                payload = create_unified_fault_payload(
                    fault_code=unified_fault_id,
                    fault_description=UNIFIED_FAULTS.get(unified_fault_id, sg_fault["name"]),
                    repair_instruction=sg_fault["repair_instruction"],
                    severity=sg_fault["severity"],
                    state_id=unified_status_id,
                    state_name=unified_status_name
                )
            else:
                payload = create_unified_fault_payload(
                    fault_code=fault_code,
                    fault_description=f"Unknown Sungrow Fault: {fault_code}",
                    repair_instruction="Tra cứu tài liệu hướng dẫn sử dụng của Sungrow",
                    severity="ERROR",
                    state_id=unified_status_id,
                    state_name=unified_status_name
                )
        else:
            # Không có lỗi
            payload = create_unified_fault_payload(
                fault_code=0,
                severity=sg_state["severity"] if sg_state else "STABLE",
                state_id=unified_status_id,
                state_name=unified_status_name
            )

        return json.dumps(payload, ensure_ascii=False)