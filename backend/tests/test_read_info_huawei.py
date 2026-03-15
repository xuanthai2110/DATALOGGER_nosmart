import sys
import os
import json

# Thêm root directory vào sys.path để import các module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from communication.modbus_tcp import ModbusTCP
from drivers.huawei_sun2000110KTL import HuaweiSUN2000

def test_read_info():
    HOST = "192.168.1.8"  # Sửa IP này theo IP thực tế của inverter
    PORT = 502
    SLAVE_ID = 1
    
    print(f"Đang kết nối tới Inverter Huawei tại {HOST}:{PORT} (Slave ID: {SLAVE_ID})...")
    transport = ModbusTCP(host=HOST, port=PORT, timeout=3.0, retries=1)
    
    # Kể cả không kết nối được, nếu muốn test exception fallback thì ta vẫn có thể gọi hàm (nếu comment đoạn return)
    if not transport.connect():
        print("⚠️ Không thể kết nối tới Inverter (IP có thể không đúng hoặc Inverter đang offline).")
        print("Sẽ thử gọi hàm read_info() để kiểm tra cơ chế fallback/exception...")
    else:
        print("✅ Đã kết nối Modbus TCP thành công!")

    try:
        driver = HuaweiSUN2000(transport, slave_id=SLAVE_ID)
        
        print("\nĐang gọi hàm driver.read_info()...")
        info = driver.read_info()
        
        print("\n--- KẾT QUẢ READ_INFO ---")
        print(json.dumps(info, indent=4, ensure_ascii=False))
        
    except Exception as e:
        print(f"\n❌ Lỗi văng ra trong main block: {e}")
    finally:
        transport.close()
        print("\nĐóng kết nối.")

if __name__ == "__main__":
    test_read_info()
