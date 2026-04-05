from pymodbus.client import ModbusTcpClient
import time
import threading
import sys

IP = "192.168.1.8"
PORT = 502
SLAVE_ID = 1

SET_PERCENT = 5 # công suất bạn muốn giữ

client = ModbusTcpClient(IP, port=PORT)
running = True


# =========================
# WRITE
# =========================
def set_power_percent(percent):
    value = int(percent * 10)
    res = client.write_register(40125, value, slave=SLAVE_ID)

    if res.isError():
        print("❌ Write lỗi")
    else:
        print(f"→ Set {percent}%")
    return res.isError()


# =========================
# READ
# =========================
def read_power():
    res = client.read_holding_registers(32080, 2, slave=SLAVE_ID)

    if res.isError():
        print("❌ Read lỗi")
        return None

    regs = res.registers
    value = (regs[0] << 16) + regs[1]

    # signed
    if value > 0x7FFFFFFF:
        value -= 0x100000000

    return value  # W


# =========================
# KEYBOARD LISTENER
# =========================
def keyboard_listener():
    global running
    print("👉 Nhấn 'q' + Enter để dừng")

    while True:
        key = sys.stdin.readline().strip()
        if key.lower() == "q":
            running = False
            break


# =========================
# MAIN
# =========================
def main():
    global running

    if not client.connect():
        print("❌ Không kết nối được")
        return

    print("✅ Connected")

    # chạy thread đọc phím
    t = threading.Thread(target=keyboard_listener, daemon=True)
    t.start()
    # gửi lệnh giữ công suất
    r = set_power_percent(SET_PERCENT)
    print(r)
    try:
        while running:

            # gửi lệnh giữ công suất
            set_power_percent(SET_PERCENT)

            # đọc công suất
            p = read_power()
            if p is not None:
                print(f"Power: {p/1000:.2f} kW")

            time.sleep(1)

    finally:
        print("\n⚠️ Dừng control → set về 100%")

        # gửi nhiều lần để đảm bảo ăn lệnh
        for _ in range(5):
            set_power_percent(100)
            time.sleep(1)

        client.close()
        print("Disconnected")


if __name__ == "__main__":
    main()