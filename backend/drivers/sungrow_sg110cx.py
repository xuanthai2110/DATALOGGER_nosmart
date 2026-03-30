# drivers/sungrow_sg110cx.py

from typing import Dict, Any
from backend.drivers.base import BaseDriver

class SungrowSG110CXDriver(BaseDriver):

    def __init__(self, transport, slave_id: int):
        self.transport = transport
        self.slave_id = slave_id

    # =========================================================
    # ================= REGISTER MAP ==========================
    # =========================================================
    # Chú ý địa chỉ trong tài liệu Sungrow:
    #   - Input Register  (3X, read-only)  -> đọc bằng read_input_registers
    #   - Holding Register (4X, read/write) -> đọc/ghi bằng read/write_holding_registers
    # Địa chỉ trong register_map là địa chỉ thực (0-indexed, tức là số trong tài liệu trừ 1)

    def register_map(self):

        return {
            # ---- Input Registers (3X) ---- serial, thông số điện, MPPT
            "info": [
                {"name": "serial_number",  "address": 4989, "length": 10, "type": "string",  "scale": None},
                {"name": "type_code",      "address": 4999, "length": 1,  "type": "uint16",  "scale": None},
                {"name": "rated_power",    "address": 5000, "length": 1,  "type": "uint16",  "scale": 0.1},
            ],

            "ac": [
                {"name": "v_a",      "address": 5018, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "v_b",      "address": 5019, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "v_c",      "address": 5020, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "i_a",      "address": 5021, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "i_b",      "address": 5022, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "i_c",      "address": 5023, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "p_inv_w",  "address": 5030, "length": 2, "type": "uint32", "scale": 1},
                {"name": "q_inv_var","address": 5032, "length": 2, "type": "sint32", "scale": 1},
                {"name": "pf",       "address": 5034, "length": 1, "type": "sint16", "scale": 0.001},
                {"name": "grid_hz",  "address": 5147, "length": 1, "type": "uint16", "scale": 0.01},
            ],

            "dc": [
                {"name": "p_dc_w",         "address": 5016, "length": 2, "type": "uint32", "scale": 1},
                {"name": "mppt_1_voltage", "address": 5010, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_1_current", "address": 5011, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_2_voltage", "address": 5012, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_2_current", "address": 5013, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_3_voltage", "address": 5014, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_3_current", "address": 5015, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_4_voltage", "address": 5114, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_4_current", "address": 5115, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_5_voltage", "address": 5116, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_5_current", "address": 5117, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_6_voltage", "address": 5118, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_6_current", "address": 5119, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_7_voltage", "address": 5120, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_7_current", "address": 5121, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_8_voltage", "address": 5122, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_8_current", "address": 5123, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_9_voltage", "address": 5129, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "mppt_9_current", "address": 5130, "length": 1, "type": "uint16", "scale": 0.1},
            ],

            # String current - Input Registers (3X), địa chỉ 7013..7030 -> 0-indexed 7012..7029
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

    def _read_input(self, start: int, length: int):
        """Đọc Input Register (3X) - dùng cho dữ liệu đo lường, read-only."""
        response = self.transport.read_input_registers(
            address=start,
            count=length,
            slave=self.slave_id
        )
        if response.isError():
            raise Exception(f"Modbus read_input_registers error at {start}")
        return response.registers

    def _read_holding(self, start: int, length: int):
        """Đọc Holding Register (4X) - dùng cho tham số cấu hình, read/write."""
        response = self.transport.read_holding_registers(
            address=start,
            count=length,
            slave=self.slave_id
        )
        if response.isError():
            raise Exception(f"Modbus read_holding_registers error at {start}")
        return response.registers

    # giữ nguyên tên _read_block để tương thích, định tuyến vào _read_input
    def _read_block(self, start: int, length: int):
        return self._read_input(start, length)

    # =========================================================
    # ================= PARSER ================================
    # =========================================================

    def _convert(self, registers: list, data_type: str):

        if not registers:
            return None

        # -------- 16-bit --------
        if data_type == "uint16":
            return registers[0] & 0xFFFF

        if data_type == "sint16":
            v = registers[0] & 0xFFFF
            if v & 0x8000:
                v -= 0x10000
            return v

        # -------- 32-bit (Sungrow: low word first) --------
        if data_type == "uint32":
            if len(registers) < 2:
                return None
            low  = registers[0] & 0xFFFF
            high = registers[1] & 0xFFFF
            return (high << 16) | low

        if data_type == "sint32":
            if len(registers) < 2:
                return None
            low  = registers[0] & 0xFFFF
            high = registers[1] & 0xFFFF
            v = (high << 16) | low
            if v & 0x80000000:
                v -= 0x100000000
            return v

        # -------- STRING --------
        if data_type == "string":
            raw_bytes = bytearray()
            for reg in registers:
                raw_bytes.append((reg >> 8) & 0xFF)
                raw_bytes.append(reg & 0xFF)
            return raw_bytes.decode("utf-8", errors="ignore").rstrip("\x00").strip()

        return None

    def parse(self, raw_block, reg_list):
        result = {}
        offset = 0
        for reg in reg_list:
            length = reg["length"]
            raw    = raw_block[offset: offset + length]
            value  = self._convert(raw, reg["type"])
            if value is not None and reg["scale"] is not None:
                value *= reg["scale"]
            result[reg["name"]] = value
            offset += length
        return result

    # =========================================================
    # ================= READ GROUPS (Input Registers - 3X) ====
    # =========================================================

    def read_info(self) -> Dict[str, Any]:
        from datetime import datetime
        try:
            regs  = self.register_map()["info"]
            start = min(r["address"] for r in regs)
            end   = max(r["address"] + r["length"] - 1 for r in regs)
            raw   = self._read_input(start, end - start + 1)

            ordered = []
            for r in regs:
                idx = r["address"] - start
                ordered.extend(raw[idx: idx + r["length"]])

            parsed = self.parse(ordered, regs)
            rated_kw = parsed.get("rated_power", 110.0) or 110.0

            return {
                "brand":           "Sungrow",
                "model":           "SG110CX",
                "serial_number":   parsed.get("serial_number", ""),
                "capacity_kw":     rated_kw,
                "mppt_count":      9,
                "firmware_version":"1.0",
                "phase_count":     3,
                "string_count":    18,
                "rate_dc_kwp":     rated_kw,
                "rate_ac_kw":      rated_kw,
                "is_active":       True,
                "slave_id":        self.slave_id,
                "usage_start_at":  datetime.now().isoformat(),
                "usage_end_at":    None,
                "replaced_by_id":  None
            }
        except Exception:
            from datetime import datetime
            return {
                "brand":           "Sungrow",
                "model":           "SG110CX",
                "serial_number":   "",
                "capacity_kw":     110.0,
                "mppt_count":      9,
                "firmware_version":"1.0",
                "phase_count":     3,
                "string_count":    18,
                "rate_dc_kwp":     110.0,
                "rate_ac_kw":      110.0,
                "is_active":       False,
                "slave_id":        self.slave_id,
                "usage_start_at":  datetime.now().isoformat(),
                "usage_end_at":    None,
                "replaced_by_id":  None
            }

    def read_ac(self) -> Dict[str, Any]:
        regs  = self.register_map()["ac"]
        start = min(r["address"] for r in regs)
        end   = max(r["address"] + r["length"] - 1 for r in regs)
        raw   = self._read_input(start, end - start + 1)
        ordered = []
        for r in regs:
            idx = r["address"] - start
            ordered.extend(raw[idx: idx + r["length"]])
        return self.parse(ordered, regs)

    def read_dc(self) -> Dict[str, Any]:
        regs  = self.register_map()["dc"]
        start = min(r["address"] for r in regs)
        end   = max(r["address"] + r["length"] - 1 for r in regs)
        raw   = self._read_input(start, end - start + 1)
        ordered = []
        for r in regs:
            idx = r["address"] - start
            ordered.extend(raw[idx: idx + r["length"]])
        return self.parse(ordered, regs)

    def read_string(self) -> Dict[str, Any]:
        result = {}
        regs   = self.register_map()["string"]
        start  = regs[0]["address"]
        end    = regs[-1]["address"]
        raw    = self._read_input(start, end - start + 1)
        for r in regs:
            idx = r["address"] - start
            val = self._convert([raw[idx]], r["type"])
            if val is not None and r["scale"] is not None:
                val *= r["scale"]
            result[r["name"]] = val
        return result

    def read_all(self) -> Dict[str, Any]:
        import json
        data = {}
        data.update(self.read_info())
        data.update(self.read_ac())
        data.update(self.read_dc())
        data.update(self.read_string())
        try:
            states_and_faults = self.read_states_and_faults()
            data.update(json.loads(states_and_faults))
        except Exception:
            pass
        return data

    # =========================================================
    # ================= CONTROL (Holding Registers - 4X) ======
    # =========================================================

    def enable_power_limit(self, enable: bool) -> bool:
        """Bật/tắt chế độ giới hạn công suất - Holding Register 4X."""
        self.transport.write_register(address=6000, value=1 if enable else 0, slave=self.slave_id)
        return True

    def write_power_limit_kw(self, kw: float) -> bool:
        """Ghi giới hạn công suất theo kW - Holding Register 4X, scale 0.1."""
        self.transport.write_register(address=6001, value=int(kw * 10), slave=self.slave_id)
        return True

    def write_power_limit_percent(self, percent: float) -> bool:
        """Ghi giới hạn công suất theo % - Holding Register 4X, scale 0.1."""
        self.transport.write_register(address=6002, value=int(percent * 10), slave=self.slave_id)
        return True

    # =========================================================
    # ================= FAULTS & STATES (Input Registers - 3X)
    # =========================================================

    def read_states_and_faults(self) -> str:
        """
        Đọc trạng thái và lỗi từ Sungrow SG110CX:
          - Register 5038 (0-indexed: 5037) -> Device Status   (Input Register 3X)
          - Register 5039 (0-indexed: 5038) -> Fault Code      (Input Register 3X)
        """
        import json
        from backend.services.fault_state_service import (
            SUNGROW_STATE_MAP,
            SUNGROW_FAULT_MAP,
            UNIFIED_STATES,
            UNIFIED_FAULTS,
            create_unified_fault_payload
        )

        # 1. Đọc Device Status (Input Register)
        res_state = self.transport.read_input_registers(
            address=5037,
            count=1,
            slave=self.slave_id
        )
        if res_state.isError():
            return json.dumps(create_unified_fault_payload(
                fault_code=None,
                fault_description="Modbus error: cannot read state register 5038",
                repair_instruction="Kiểm tra kết nối cáp RS485/TCP tới inverter",
                severity="ERROR"
            ), ensure_ascii=False)

        status_code = res_state.registers[0]
        sg_state    = SUNGROW_STATE_MAP.get(status_code)

        unified_status_id   = sg_state["id_unified"] if sg_state else None
        unified_status_name = UNIFIED_STATES.get(unified_status_id, "Unknown State") if unified_status_id else None

        # 2. Đọc Fault Code (Input Register)
        res_fault = self.transport.read_input_registers(
            address=5038,
            count=1,
            slave=self.slave_id
        )
        if res_fault.isError():
            return json.dumps(create_unified_fault_payload(
                fault_code=None,
                fault_description="Modbus error: cannot read fault register 5039",
                repair_instruction="Kiểm tra kết nối cáp RS485/TCP tới inverter",
                severity="ERROR"
            ), ensure_ascii=False)

        fault_code = res_fault.registers[0]

        # 3. Tạo payload
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
            payload = create_unified_fault_payload(
                fault_code=0,
                severity=sg_state["severity"] if sg_state else "STABLE",
                state_id=unified_status_id,
                state_name=unified_status_name
            )

        return json.dumps(payload, ensure_ascii=False)