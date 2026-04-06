# drivers/huawei_smartlogger.py

from typing import Dict, Any
from backend.drivers.base import BaseDriver


class SmartLoggerHuawei(BaseDriver):

    def __init__(self, transport, slave_id=0):
        self.transport = transport
        self.slave_id = slave_id

    # =========================================================
    # ================= LOW LEVEL =============================
    # =========================================================
    def register_map(cls, subclass):
        return {
            "control": {
                "p_set_kw": {"addr": 40420, "type": "u32", "gain": 10},
                "percent": {"addr": 40428, "type": "u16", "gain": 10},
                
            },
            "status": {
                "plant_status": {"addr": 40543, "type": "u16"},
                "control_mode": {"addr": 40737, "type": "u16"},
                "setpoint_kw": {"addr": 40738, "type": "u32", "gain": 10},
                "percent": {"addr": 40802, "type": "u32"},
            },
            "actuals": {
                "actual_power_kw": {"addr": 40525, "type": "s32", "gain": 1000},
            }
        }
    def _read_u16(self, addr):
        res = self.transport.read_holding_registers(
            address=addr,
            count=1,
            slave=self.slave_id
        )
        if res.isError():
            raise Exception(f"Read error at {addr}")
        return res.registers[0]

    def _read_u32(self, addr):
        res = self.transport.read_holding_registers(
            address=addr,
            count=2,
            slave=self.slave_id
        )
        if res.isError():
            raise Exception(f"Read error at {addr}")
        return (res.registers[0] << 16) + res.registers[1]

    def _write_u16(self, addr, value):
        res = self.transport.write_register(
            address=addr,
            value=value,
            slave=self.slave_id
        )
        if res.isError():
            raise Exception(f"Write error at {addr}")
        return True

    def _write_u32(self, addr, value):
        high = (value >> 16) & 0xFFFF
        low = value & 0xFFFF

        res = self.transport.write_multiple_registers(
            address=addr,
            values=[high, low],
            slave=self.slave_id
        )
        if res.isError():
            raise Exception(f"Write error at {addr}")
        return True

    # =========================================================
    # ================= CONTROL STATUS ========================
    # =========================================================

    def control_status(self) -> Dict[str, Any]:
        """
        Detect trạng thái điều khiển công suất
        """

        try:
            plant_status = self._read_u16(40543)
            control_mode = self._read_u16(40737)
            setpoint_kw = self._read_u32(40738) / 10
            percent = self._read_u32(40802)

            is_limited = (
                plant_status == 2 or
                control_mode != 0 or
                percent < 100
            )

            return {
                "plant_status": plant_status,
                "control_mode": control_mode,
                "setpoint_kw": setpoint_kw,
                "percent": percent,
                "is_limited": is_limited
            }

        except Exception as e:
            return {"error": str(e)}

    # =========================================================
    # ================= CONTROL P =============================
    # =========================================================

    def control_P(self, kw: float) -> bool:
        value = int(kw * 10)

        return self._write_u32(40420, value)

    # =========================================================
    # ================= CONTROL % =============================
    # =========================================================

    def control_percent(self, percent: float) -> bool:
        value = int(percent * 10)

        return self._write_u16(40428, value)

    # =========================================================
    # ================= READ ACTUAL ===========================
    # =========================================================

    def read_actual_power(self) -> float:
        """
        Công suất thực tế toàn plant (kW)
        -> 40525
        """

        value = self._read_u32(40525)

        # signed
        if value > 0x7FFFFFFF:
            value -= 0x100000000

        return value / 1000

    def register_map(self) -> Dict[str, Any]: #Trả về một dict chứa thông tin về các register của inverter, bao gồm địa chỉ, kiểu dữ liệu, v.v.
        pass

    #================ hàm parse dữ liệu từ raw register sang engineering value =========================

    def parse(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        pass
    # =============Các hàm đọc dữ liệu từ inverter =========================
    def read_ac(self) -> Dict[str, Any]: #Đọc toàn bộ AC data:
        pass


    def read_dc(self) -> Dict[str, Any]: #Đọc toàn bộ DC data:
        pass


    def read_info(self) -> Dict[str, Any]: #Đọc thông tin inverter như model, firmware version, serial number, v.v.
        pass


    def read_string(self) -> Dict[str, Any]: #Đọc dữ liệu từng string :
        pass


    def read_all(self) -> Dict[str, Any]: #Đọc tất cả dữ liệu (AC, DC, info, string) trong một lần gọi.
        pass

    #================ Điều khiển inverter =========================


    def enable_power_limit(self, enable: bool) -> bool: #Bật / tắt chế độ power limit.
        pass


    def write_power_limit_kw(self, kw: float) -> bool: #Ghi giá trị giới hạn công suất (kW).
        pass
    def read_states_and_faults(self) -> Dict[str, Any]: #Đọc trạng thái và lỗi của inverter.
        pass
    def write_power_limit_percent(self, percent: float) -> bool: #Ghi giá trị giới hạn công suất (%).
        pass
        