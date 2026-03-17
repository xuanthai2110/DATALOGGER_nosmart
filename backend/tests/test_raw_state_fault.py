"""
TEST: Đọc mã trạng thái và lỗi THÔ (RAW) từ inverter Huawei
Chạy từ thư mục gốc: python backend/tests/test_raw_state_fault.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pymodbus.client import ModbusTcpClient

# ========================
# CẤU HÌNH — CHỈNH Ở ĐÂY
# ========================
HOST       = "192.168.1.8"   # IP inverter hoặc gateway
PORT       = 502              # Cổng Modbus TCP
TIMEOUT    = 3

# Danh sách Slave ID cần kiểm tra (để trống = quét 1-30)
SLAVE_IDS  = []   # ví dụ: [1, 2, 3] hoặc [] để quét tất cả

# ==============================
# Giải thích mã trạng thái thô theo tài liệu Huawei SUN2000
# ==============================
HUAWEI_STATUS_DESC = {
    0x0000: "INITIAL_STANDBY",
    0x0001: "DETECTING (Insulation check)",
    0x0002: "DETECTING (Grid prep)",
    0x0003: "DETECTING (Grid prep wait)",
    0x0100: "STARTING",
    0x0200: "RUNNING (On-grid, normal)",
    0x0201: "RUNNING (Derating, power ref)",
    0x0202: "RUNNING (Derating, comms req)",
    0x0203: "RUNNING (Off-grid)",
    0x0300: "SHUTDOWN (Fault)",
    0x0301: "SHUTDOWN (Power limit)",
    0x0302: "SHUTDOWN (Manual off, OVGR)",
    0x0303: "SHUTDOWN (Manual off, remote cmd)",
    0x0304: "SHUTDOWN (Spot check)",
    0x0305: "SHUTDOWN (Startup req)",
    0x0306: "SHUTDOWN (DC disconnect)",
    0x0307: "SHUTDOWN (Rapid shutdown)",
    0x0308: "SHUTDOWN (Input underpower)",
    0x0401: "GRID_SCHEDULING (Cos Phi P)",
    0x0402: "GRID_SCHEDULING (Q U)",
    0x0403: "GRID_SCHEDULING (Q P)",
    0x0501: "SPOT_CHECK",
    0x0600: "SLEEPING",
}


def read_inverter(client, slave_id):
    """Đọc state (32089) và fault (32090) từ một slave ID."""
    print(f"\n{'='*50}")
    print(f"  Slave ID: {slave_id}")
    print(f"{'='*50}")

    # Đọc 2 thanh ghi liên tiếp từ 32089
    result = client.read_holding_registers(address=32089, count=2, slave=slave_id)

    if result.isError():
        print(f"  [ERROR] Không đọc được: {result}")
        return

    raw_state = result.registers[0]
    raw_fault = result.registers[1]

    # --- STATE ---
    state_desc = HUAWEI_STATUS_DESC.get(raw_state, "UNKNOWN / NOT DEFINED")
    print(f"\n  [REGISTER 32089] State")
    print(f"    Decimal : {raw_state}")
    print(f"    Hex     : 0x{raw_state:04X}")
    print(f"    Meaning : {state_desc}")

    # --- FAULT ---
    print(f"\n  [REGISTER 32090] Fault Code")
    print(f"    Decimal : {raw_fault}")
    print(f"    Hex     : 0x{raw_fault:04X}")
    print(f"    Binary  : {raw_fault:016b}")

    if raw_fault == 0:
        print(f"    Meaning : NO FAULT (bình thường)")
    else:
        print(f"    Meaning : ⚠️  CÓ LỖI — cần tra cứu tài liệu Huawei SUN2000")
        # Phân tích bitmask nếu thanh phần là bitmask (bit nào bật)
        active_bits = [i for i in range(16) if (raw_fault >> i) & 1]
        if active_bits:
            print(f"    Active bits (0-indexed): {active_bits}")


def main():
    print(f"\nKết nối tới {HOST}:{PORT} ...")
    client = ModbusTcpClient(host=HOST, port=PORT, timeout=TIMEOUT)

    if not client.connect():
        print(f"[FAIL] Không kết nối được tới {HOST}:{PORT}")
        return

    print(f"[OK] Đã kết nối.\n")

    slaves_to_check = SLAVE_IDS if SLAVE_IDS else range(1, 31)

    for sid in slaves_to_check:
        read_inverter(client, sid)

    client.close()
    print(f"\n\nHoàn tất.")


if __name__ == "__main__":
    main()
