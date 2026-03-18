"""
TEST: Nhập mã lỗi thô từ driver → FaultStateService → In JSON kết quả

Chạy: python backend/tests/test_fault_mapping.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.fault_state_service import FaultStateService

service = FaultStateService()

BRANDS = ["HUAWEI", "SUNGROW"]


def test_map(brand: str, state_raw: int, fault_code: int):
    result = {
        "input": {
            "brand": brand,
            "state_raw": state_raw,
            "state_hex": hex(state_raw),
            "fault_code": fault_code
        },
        "output": {}
    }

    # Map state
    state_info = service.map_state(brand, state_raw)
    result["output"]["state"] = state_info

    # Map fault
    if fault_code and fault_code != 0:
        fault_info = service.map_fault(brand, fault_code)
        result["output"]["fault"] = fault_info
    else:
        result["output"]["fault"] = None

    return result


def interactive_mode():
    print("\n" + "="*55)
    print("  FaultStateService — Test Mapping Tool")
    print("="*55)
    print("  Nhập 'q' để thoát\n")

    while True:
        print("-"*55)

        # Chọn brand
        print(f"Brand ({'/'.join(BRANDS)}): ", end="")
        brand = input().strip().upper()
        if brand == "Q":
            break
        if brand not in BRANDS:
            print(f"  [!] Brand không hợp lệ. Dùng: {', '.join(BRANDS)}")
            continue

        # Nhập state raw (hex hoặc decimal)
        print("State raw (reg 32089, decimal hoặc 0xHEX): ", end="")
        state_str = input().strip()
        if state_str.lower() == "q":
            break
        try:
            state_raw = int(state_str, 0)  # Hỗ trợ cả 0x... và decimal
        except ValueError:
            print("  [!] Giá trị không hợp lệ.")
            continue

        # Nhập fault code
        print("Fault code (reg 32090, decimal, 0 = không lỗi): ", end="")
        fault_str = input().strip()
        if fault_str.lower() == "q":
            break
        try:
            fault_code = int(fault_str, 0)
        except ValueError:
            print("  [!] Giá trị không hợp lệ.")
            continue

        # Chạy mapping và in JSON
        result = test_map(brand, state_raw, fault_code)
        print("\n" + json.dumps(result, indent=2, ensure_ascii=False))


def quick_test():
    """Chạy một số test mẫu nhanh để kiểm tra"""
    samples = [
        ("HUAWEI", 0x0200, 0),       # Running, no fault
        ("HUAWEI", 0x0201, 0),       # Derating, no fault
        ("HUAWEI", 0x0300, 2021),    # Fault, OVER_TEMPERATURE
        ("HUAWEI", 0x0200, 2001),    # Running + GRID_OVERVOLTAGE
        ("SUNGROW", 2, 0),           # Running, no fault
        ("SUNGROW", 7, 20),          # Fault, OVER_TEMPERATURE
        ("SUNGROW", 2, 14),          # Running + STRING_FAULT
    ]

    print("\n" + "="*55)
    print("  Quick Test — Các mẫu mặc định")
    print("="*55)

    for brand, state, fault in samples:
        result = test_map(brand, state, fault)
        print(f"\n[{brand}] state={hex(state)}, fault={fault}")
        print(json.dumps(result["output"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    if "--quick" in sys.argv:
        quick_test()
    else:
        interactive_mode()
