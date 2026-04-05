from pymodbus.client import ModbusTcpClient
import time

IP = "192.168.1.8"
PORT = 502
SLAVE_ID = 1   # inverter = 1, smartlogger = 0


# =========================
# CONNECT
# =========================
client = ModbusTcpClient(IP, port=PORT)

if not client.connect():
    print("❌ Không kết nối được")
    exit()

print("✅ Connected")


# =========================
# WRITE HELPERS
# =========================
def write_u16(addr, value):
    res = client.write_register(address=addr, value=int(value), slave=SLAVE_ID)
    if res.isError():
        print(f"❌ Write error at {addr}")
    else:
        print(f"✔ Write {addr} = {value}")


def write_u32(addr, value):
    high = (int(value) >> 16) & 0xFFFF
    low = int(value) & 0xFFFF

    res = client.write_registers(address=addr, values=[high, low], slave=SLAVE_ID)
    if res.isError():
        print(f"❌ Write error at {addr}")
    else:
        print(f"✔ Write {addr} = {value} (U32)")


# =========================
# TEST CONTROL
# =========================
try:

    print("\n=== TEST PERCENT ===")
    for i in range(5):
        write_u16(40125, int(50 * 10))   # 50%
        time.sleep(1)

    print("\n=== TEST KW ===")
    for i in range(5):
        write_u16(40120, int(10 * 10))   # 50 kW
        time.sleep(1)

    print("\n=== TEST W ===")
    for i in range(5):
        write_u32(40126, 10000)          # 50,000 W
        time.sleep(1)
    print("\n=== DISABLE CONTROL ===")
    for i in range(3):
        write_u16(40125, int(100 * 10))  # 100%
        time.sleep(1)

finally:
    client.close()
    print("Disconnected")