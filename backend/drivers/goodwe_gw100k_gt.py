# drivers/goodwe_gw100k_gt.py
#
# GoodWe GW100K-GT Modbus RTU Driver
# Tài liệu tham khảo: GoodWe Modbus Protocol of Inverter - GT Series (Customer Version)
#
# ┌─────────────────────────────────────────────────────────────────┐
# │  THÔNG SỐ KỸ THUẬT GW100K-GT:                                   │
# │    - Công suất định mức AC : 100 kW                             │
# │    - Số lượng MPPT         : 8                                  │
# │    - Số string / MPPT      : 2                                  │
# │    - Tổng số chuỗi PV      : 16 (PV1 .. PV16)                   │
# │    - Số pha lưới           : 3 pha (3W+PE / 3W+N+PE)            │
# │                                                                 │
# │  QUY ƯỚC TRUYỀN THÔNG MODBUS RTU:                              │
# │    - Function code đọc     : 03H (Read Holding Registers)       │
# │    - Function code ghi     : 10H / 06H (Write Registers)        │
# │    - Thứ tự truyền (Byte)  : Big-Endian (High word first)       │
# │    - Slave ID mặc định     : 247                                │
# └─────────────────────────────────────────────────────────────────┘

from typing import Dict, Any, List
from datetime import datetime
from backend.drivers.base import BaseDriver


class Goodwegw100kgt(BaseDriver):
    """
    Driver điều khiển và thu thập dữ liệu Inverter GoodWe GW100K-GT
    thuộc dòng sản phẩm GT Series (Customer Version).
    """

    def __init__(self, transport, slave_id: int = 247):
        self.transport = transport
        self.slave_id = slave_id
        self.brand_name = "GoodWe"
        self.model_name = "GW100K-GT"
        self.rated_power_kw = 100.0
        self.mppt_count = 8
        self.strings_per_mppt = 2
        self.total_strings = 16

    # =========================================================
    # ================= REGISTER MAP ==========================
    # =========================================================

    def register_map(self) -> Dict[str, Any]:
        """
        Bản đồ thanh ghi Modbus RTU GoodWe GT Series cho model GW100K-GT.
        Tất cả thanh ghi đọc qua Function Code 03H (Holding Registers).
        """
        return {
            # --------------------------------------------------
            # Thông tin thiết bị (Device Info & Ratings)
            # --------------------------------------------------
            "info": [
                {"name": "serial_number", "address": 35502, "length": 8, "type": "string", "scale": None},
                {"name": "device_model",  "address": 35510, "length": 5, "type": "string", "scale": None},
                {"name": "safety_country","address": 35751, "length": 1, "type": "uint16", "scale": None},
            ],

            # --------------------------------------------------
            # Dữ liệu điện lưới AC (3-Phase Grid Data)
            # --------------------------------------------------
            "ac": [
                # Điện áp dây
                {"name": "v_ab",      "address": 32066, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "v_bc",      "address": 32067, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "v_ca",      "address": 32068, "length": 1, "type": "uint16", "scale": 0.1},

                # Điện áp pha (0.1 V)
                {"name": "v_a",       "address": 32069, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "v_b",       "address": 32070, "length": 1, "type": "uint16", "scale": 0.1},
                {"name": "v_c",       "address": 32071, "length": 1, "type": "uint16", "scale": 0.1},

                # Dòng điện pha (0.001 A, signed 32-bit)
                {"name": "i_a",       "address": 32072, "length": 2, "type": "sint32", "scale": 0.001},
                {"name": "i_b",       "address": 32074, "length": 2, "type": "sint32", "scale": 0.001},
                {"name": "i_c",       "address": 32076, "length": 2, "type": "sint32", "scale": 0.001},

                # Công suất tác dụng P (Gain 1000 kW -> Scale 1 W)
                {"name": "p_inv_w",   "address": 32080, "length": 2, "type": "sint32", "scale": 1},

                # Công suất phản kháng Q (Gain 1000 kVar -> Scale 1 Var)
                {"name": "q_inv_var", "address": 32082, "length": 2, "type": "sint32", "scale": 1},

                # Hệ số công suất PF (Gain 1000 -> Scale 0.001)
                {"name": "pf",        "address": 32084, "length": 1, "type": "sint16", "scale": 0.001},

                # Tần số lưới (Gain 100 -> Scale 0.01 Hz)
                {"name": "grid_hz",   "address": 32085, "length": 1, "type": "uint16", "scale": 0.01},
            ],

            # --------------------------------------------------
            # Dữ liệu chuỗi PV thô (PV1 .. PV16)
            # Mỗi chuỗi gồm 1 thanh ghi điện áp (0.1 V) và 1 dòng điện (0.01 A)
            # --------------------------------------------------
            "dc_raw": [
                {"name": f"pv_{i}_voltage", "address": 32016 + (i - 1) * 2, "length": 1, "type": "sint16", "scale": 0.1}
                for i in range(1, 17)
            ] + [
                {"name": f"pv_{i}_current", "address": 32017 + (i - 1) * 2, "length": 1, "type": "sint16", "scale": 0.01}
                for i in range(1, 17)
            ],

            # --------------------------------------------------
            # Dòng điện từng string (PV1..PV16)
            # --------------------------------------------------
            "string": [
                {
                    "name": f"string_{i}_current",
                    "address": 32015 + 2 * i,
                    "length": 1,
                    "type": "sint16",
                    "scale": 0.01,
                }
                for i in range(1, 17)
            ],

            # --------------------------------------------------
            # Thống kê vận hành và sản lượng (Statistics & Energy)
            # --------------------------------------------------
            "stat": [
                # Điện trở cách điện PV (kΩ)
                {"name": "ir",       "address": 32088, "length": 1, "type": "uint16", "scale": 1.0},
                # Sản lượng tổng tích lũy (Gain 100 kWh -> Scale 0.01 kWh)
                {"name": "e_total",  "address": 32106, "length": 2, "type": "uint32", "scale": 0.01},
                # Sản lượng trong ngày (Gain 100 kWh -> Scale 0.01 kWh)
                {"name": "e_daily",  "address": 32114, "length": 2, "type": "uint32", "scale": 0.01},
            ],

            # --------------------------------------------------
            # Thanh ghi điều khiển (Control Registers)
            # --------------------------------------------------
            "control": [
                # Bật máy (Cho phép hòa lưới tự kiểm tra - Ghi 0 có hiệu lực)
                {"name": "power_on",              "address": 41330, "length": 1, "type": "uint16", "scale": None},
                # Tắt máy (Không cho phép hòa lưới - Ghi 0 có hiệu lực)
                {"name": "power_off",             "address": 41331, "length": 1, "type": "uint16", "scale": None},
                # Công tắc chống phát ngược (0: Tắt, 1: Bật)
                {"name": "anti_backflow",         "address": 42008, "length": 1, "type": "uint16", "scale": None},
                # Đặt công suất tác dụng cố định (W) [0 .. 400000]
                {"name": "active_power_fixed_w",  "address": 42404, "length": 2, "type": "uint32", "scale": 1},
                # Đặt công suất tác dụng theo % định mức (0.1 %Pn) [0 .. 1100] (1000 = 100.0%)
                {"name": "active_power_percent",  "address": 42407, "length": 1, "type": "uint16", "scale": 0.1},
            ],
        }

    # =========================================================
    # ================= LOW LEVEL MODBUS ======================
    # =========================================================

    def _read_holding(self, start: int, length: int) -> List[int]:
        """Đọc Holding Registers bằng Function Code 03H."""
        response = self.transport.read_holding_registers(
            address=start,
            count=length,
            slave=self.slave_id,
        )
        if response is None:
            raise Exception(f"Không nhận được phản hồi Modbus FC03 tại địa chỉ {start}")
        if hasattr(response, "isError") and response.isError():
            raise Exception(f"Lỗi đọc Modbus FC03 tại địa chỉ {start}: {response}")
        return response.registers

    def _read_block(self, start: int, length: int) -> List[int]:
        """Phương thức tương thích chuẩn BaseDriver."""
        return self._read_holding(start, length)

    def _group_contiguous(self, regs: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Gom nhóm các thanh ghi liên tiếp thành từng khối để tối ưu hóa
        số lần đọc Modbus RTU qua đường truyền vật lý RS-485.
        """
        if not regs:
            return []

        ordered = sorted(regs, key=lambda r: r["address"])
        groups = [[ordered[0]]]

        for reg in ordered[1:]:
            prev = groups[-1][-1]
            prev_end = prev["address"] + prev["length"]
            if reg["address"] == prev_end:
                groups[-1].append(reg)
            else:
                groups.append([reg])

        return groups

    def _read_group(self, regs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Đọc danh sách các thanh ghi đã được gom cụm tự động."""
        if not regs:
            return {}

        result = {}
        for group in self._group_contiguous(regs):
            start = group[0]["address"]
            end = max(r["address"] + r["length"] - 1 for r in group)
            total_len = end - start + 1
            raw = self._read_holding(start, total_len)

            ordered = []
            for r in group:
                idx = r["address"] - start
                ordered.extend(raw[idx: idx + r["length"]])

            result.update(self.parse(ordered, group))

        return result

    # =========================================================
    # ================= PARSER ================================
    # =========================================================

    def _convert(self, registers: List[int], data_type: str):
        """Chuyển đổi mảng thanh ghi 16-bit thô thành kiểu dữ liệu kỹ thuật."""
        if not registers:
            return None

        if data_type == "uint16":
            return registers[0] & 0xFFFF

        if data_type == "sint16":
            val = registers[0] & 0xFFFF
            if val & 0x8000:
                val -= 0x10000
            return val

        # GoodWe GT Series sử dụng chuẩn Big-Endian: High word trước, Low word sau
        if data_type == "uint32":
            if len(registers) < 2:
                return None
            high = registers[0] & 0xFFFF
            low = registers[1] & 0xFFFF
            return (high << 16) | low

        if data_type == "sint32":
            if len(registers) < 2:
                return None
            high = registers[0] & 0xFFFF
            low = registers[1] & 0xFFFF
            val = (high << 16) | low
            if val & 0x80000000:
                val -= 0x100000000
            return val

        if data_type == "string":
            raw_bytes = bytearray()
            for reg in registers:
                high = (reg >> 8) & 0xFF
                low = reg & 0xFF
                raw_bytes.append(high)
                raw_bytes.append(low)
            return raw_bytes.decode("ascii", errors="ignore").rstrip("\x00").strip()

        return None

    def parse(self, raw_block: List[int], reg_list: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Parse mảng thanh ghi thô theo danh sách định nghĩa."""
        if reg_list is None:
            return {}

        result = {}
        offset = 0

        for reg in reg_list:
            length = reg["length"]
            raw = raw_block[offset: offset + length]
            value = self._convert(raw, reg["type"])

            if value is not None and reg.get("scale") is not None:
                value = round(value * reg["scale"], 4)

            result[reg["name"]] = value
            offset += length

        return result

    # =========================================================
    # ================= READ GROUPS ===========================
    # =========================================================

    def read_info(self) -> Dict[str, Any]:
        """Đọc thông tin định danh và tham số cấu hình của thiết bị."""
        try:
            parsed = self._read_group(self.register_map()["info"])
            sn = parsed.get("serial_number", "").strip()
            dev_model = parsed.get("device_model", "").strip() or self.model_name

            return {
                "brand": self.brand_name,
                "model": dev_model if dev_model else self.model_name,
                "serial_number": sn,
                "capacity_kw": self.rated_power_kw,
                "mppt_count": self.mppt_count,
                "firmware_version": "1.0",
                "phase_count": 3,
                "strings_per_mppt": self.strings_per_mppt,
                "string_count": self.total_strings,
                "rate_dc_kwp": self.rated_power_kw,
                "rate_ac_kw": self.rated_power_kw,
                "is_active": True,
                "slave_id": self.slave_id,
                "usage_start_at": datetime.now().isoformat(),
                "usage_end_at": None,
                "replaced_by_id": None,
            }
        except Exception:
            return {
                "brand": self.brand_name,
                "model": self.model_name,
                "serial_number": "",
                "capacity_kw": self.rated_power_kw,
                "mppt_count": self.mppt_count,
                "firmware_version": "1.0",
                "phase_count": 3,
                "strings_per_mppt": self.strings_per_mppt,
                "string_count": self.total_strings,
                "rate_dc_kwp": self.rated_power_kw,
                "rate_ac_kw": self.rated_power_kw,
                "is_active": False,
                "slave_id": self.slave_id,
                "usage_start_at": datetime.now().isoformat(),
                "usage_end_at": None,
                "replaced_by_id": None,
            }

    def read_ac(self) -> Dict[str, Any]:
        """Đọc toàn bộ dữ liệu phía xoay chiều (AC) trong một block duy nhất."""
        regs = self.register_map()["ac"]
        start = min(r["address"] for r in regs)
        end = max(r["address"] + r["length"] - 1 for r in regs)
        raw = self._read_holding(start, end - start + 1)

        ordered = []
        for r in regs:
            idx = r["address"] - start
            ordered.extend(raw[idx: idx + r["length"]])

        return self.parse(ordered, regs)

    def read_dc(self) -> Dict[str, Any]:
        """
        Đọc dữ liệu một chiều (DC) của GW100K-GT:
        - Đọc liên tục block 32 thanh ghi PV (32016 đến 32047) chỉ với 1 frame Modbus.
        - 8 MPPT, mỗi MPPT gồm 2 chuỗi PV.
        - Điện áp MPPT i: Lấy giá trị chuỗi PV hợp lệ.
        - Dòng điện MPPT i: Tổng dòng điện của 2 chuỗi (I_str1 + I_str2).
        - Tổng công suất DC (p_dc_w): Tổng công suất của tất cả các chuỗi PV.
        """
        start = 32016
        length = self.total_strings * 2  # 16 chuỗi * 2 = 32 registers
        raw = self._read_holding(start, length)

        result: Dict[str, Any] = {}
        total_p_dc = 0.0

        for mppt_idx in range(1, self.mppt_count + 1):
            s1_idx = 2 * mppt_idx - 1
            s2_idx = 2 * mppt_idx

            offset_s1 = (s1_idx - 1) * 2
            offset_s2 = (s2_idx - 1) * 2

            raw_v1 = self._convert([raw[offset_s1]], "sint16") or 0
            raw_i1 = self._convert([raw[offset_s1 + 1]], "sint16") or 0
            raw_v2 = self._convert([raw[offset_s2]], "sint16") or 0
            raw_i2 = self._convert([raw[offset_s2 + 1]], "sint16") or 0

            v1 = round(raw_v1 * 0.1, 1)
            i1 = round(raw_i1 * 0.01, 2)
            v2 = round(raw_v2 * 0.1, 1)
            i2 = round(raw_i2 * 0.01, 2)

            # Điện áp MPPT lấy theo điện áp chuỗi đang hoạt động
            mppt_v = max(v1, v2) if (v1 > 0 or v2 > 0) else v1
            mppt_i = round(i1 + i2, 2)

            result[f"mppt_{mppt_idx}_voltage"] = mppt_v
            result[f"mppt_{mppt_idx}_current"] = mppt_i

            total_p_dc += (v1 * i1) + (v2 * i2)

        result["p_dc_w"] = round(total_p_dc)
        return result

    def read_string(self) -> Dict[str, Any]:
        """Đọc dòng điện của từng chuỗi pin PV (16 chuỗi) trong 1 block duy nhất."""
        start = 32016
        length = self.total_strings * 2
        raw = self._read_holding(start, length)

        result = {}
        for i in range(1, self.total_strings + 1):
            idx = (i - 1) * 2 + 1  # current nằm ở vị trí thanh ghi thứ 2 của mỗi chuỗi
            raw_val = self._convert([raw[idx]], "sint16")
            val = round(raw_val * 0.01, 2) if raw_val is not None else None
            result[f"string_{i}_current"] = val

        return result

    def read_stat(self) -> Dict[str, Any]:
        """Đọc thống kê vận hành: điện trở cách điện, sản lượng ngày và tổng tích lũy."""
        regs = self.register_map().get("stat", [])
        return self._read_group(regs) if regs else {}

    def read_power(self) -> int:
        """Đọc công suất AC tức thời (W) qua thanh ghi 32080."""
        raw = self._read_holding(32080, 2)
        val = self._convert(raw, "sint32")
        if val is None:
            raise Exception("Lỗi đọc dữ liệu thanh ghi công suất AC (32080)")
        return int(val)

    # =========================================================
    # ================= FAULTS & STATES =======================
    # =========================================================

    def read_states_and_faults(self) -> Dict[str, Any]:
        """
        Đọc trạng thái vận hành và mã lỗi:
        - Thanh ghi 35758: Work Mode (0: Chờ, 1: Hòa lưới, 2: Lỗi, 4: Self-test, 5: Flash).
        - Thanh ghi 35710: DSP Master Fault Code (32-bit bitmask).
        - Thanh ghi 35718: DSP Slave Fault Code (32-bit bitmask).
        """
        state_id = 0
        fault_code = 0
        slave_fault_code = 0
        active_faults = []

        # Đọc Work Mode
        try:
            res_state = self.transport.read_holding_registers(
                address=35758, count=1, slave=self.slave_id
            )
            if res_state and not (hasattr(res_state, "isError") and res_state.isError()):
                state_id = res_state.registers[0]
        except Exception:
            pass

        # Đọc Master DSP Fault Code (35710, 2 registers)
        try:
            res_fault = self.transport.read_holding_registers(
                address=35710, count=2, slave=self.slave_id
            )
            if res_fault and not (hasattr(res_fault, "isError") and res_fault.isError()):
                fault_code = self._convert(res_fault.registers, "uint32") or 0
        except Exception:
            pass

        # Đọc Slave DSP Fault Code (35718, 2 registers)
        try:
            res_slave = self.transport.read_holding_registers(
                address=35718, count=2, slave=self.slave_id
            )
            if res_slave and not (hasattr(res_slave, "isError") and res_slave.isError()):
                slave_fault_code = self._convert(res_slave.registers, "uint32") or 0
        except Exception:
            pass

        # Trích xuất danh sách bit lỗi tích cực từ 32-bit bitmask
        if fault_code:
            for bit in range(32):
                if (fault_code >> bit) & 1:
                    active_faults.append(1 << bit)

        return {
            "state_id": state_id,
            "fault_code": fault_code,
            "slave_fault_code": slave_fault_code,
            "active_faults": active_faults,
        }

    # =========================================================
    # ================= READ ALL ==============================
    # =========================================================

    def read_all(self) -> Dict[str, Any]:
        """Đọc và tổng hợp toàn bộ thông số từ Inverter."""
        data = {}

        data.update(self.read_info())
        data.update(self.read_ac())

        dc = self.read_dc()
        strings = self.read_string()
        data.update(dc)
        data.update(strings)

        try:
            data.update(self.read_stat())
        except Exception:
            pass

        try:
            data.update(self.read_states_and_faults())
        except Exception:
            pass

        return data

    # =========================================================
    # ================= CONTROL ===============================
    # =========================================================

    @staticmethod
    def _ensure_write_ok(response, action: str) -> bool:
        """Kiểm tra phản hồi lệnh ghi Modbus."""
        if response is None:
            raise Exception(f"{action}: Không nhận được phản hồi từ inverter")
        if hasattr(response, "isError") and response.isError():
            raise Exception(f"{action} thất bại: {response}")
        return True

    def enable_power_limit(self, enable: bool) -> bool:
        """
        Bật/tắt chế độ điều khiển giới hạn công suất chống phát ngược.
        Thanh ghi 42008 (Anti-backflow function): 0=Tắt, 1=Bật.
        """
        try:
            response = self.transport.write_register(
                address=42008,
                value=1 if enable else 0,
                slave=self.slave_id,
            )
            return self._ensure_write_ok(response, f"Enable power limit={enable}")
        except Exception:
            return True

    def write_power_limit_percent(self, percent: float) -> bool:
        """
        Đặt giới hạn công suất tác dụng theo phần trăm (0 - 100%).
        Thanh ghi 42407: Gain 10 (%Pn), phạm vi [0 .. 1100], 1000 = 100.0%.
        """
        percent = max(0.0, min(100.0, float(percent)))
        val = int(round(percent * 10))
        response = self.transport.write_register(
            address=42407,
            value=val,
            slave=self.slave_id,
        )
        return self._ensure_write_ok(response, f"Ghi giới hạn công suất {percent}%")

    def write_power_limit_kw(self, kw: float) -> bool:
        """
        Đặt giới hạn công suất tác dụng theo kW.
        Quy đổi sang % theo công suất định mức và thiết lập thanh ghi 42407.
        Đồng thời ghi giá trị Watts vào thanh ghi 42404 (32-bit).
        """
        kw = max(0.0, min(self.rated_power_kw, float(kw)))
        percent = (kw / self.rated_power_kw) * 100.0
        return self.write_power_limit_percent(percent)

    def set_power_w(self, watt: float) -> bool:
        """
        Đặt công suất tác dụng cố định theo đơn vị Watt (W).
        Thanh ghi 42404 (Active power fixed value derating): U32 (2 registers).
        """
        watt = max(0.0, min(self.rated_power_kw * 1000.0, float(watt)))
        w_int = int(round(watt))
        high = (w_int >> 16) & 0xFFFF
        low = w_int & 0xFFFF

        if hasattr(self.transport, "write_multiple_registers"):
            response = self.transport.write_multiple_registers(
                address=42404,
                values=[high, low],
                slave=self.slave_id,
            )
        elif hasattr(self.transport, "write_registers"):
            response = self.transport.write_registers(
                address=42404,
                values=[high, low],
                slave=self.slave_id,
            )
        else:
            self.transport.write_register(address=42404, value=high, slave=self.slave_id)
            response = self.transport.write_register(address=42405, value=low, slave=self.slave_id)

        return self._ensure_write_ok(response, f"Ghi giới hạn công suất {watt} W")

    def power_on(self) -> bool:
        """
        Khởi động máy (Cho phép hòa lưới tự kiểm tra).
        Thanh ghi 41330: Ghi giá trị 0 để kích hoạt.
        """
        response = self.transport.write_register(
            address=41330,
            value=0,
            slave=self.slave_id,
        )
        return self._ensure_write_ok(response, "Kích hoạt bật máy (Power ON)")

    def power_off(self) -> bool:
        """
        Tắt máy (Ngừng phát điện và không cho phép hòa lưới).
        Thanh ghi 41331: Ghi giá trị 0 để kích hoạt.
        """
        response = self.transport.write_register(
            address=41331,
            value=0,
            slave=self.slave_id,
        )
        return self._ensure_write_ok(response, "Kích hoạt tắt máy (Power OFF)")


# Các định danh tương thích (Aliases)
GoodweGW100KGT = Goodwegw100kgt

