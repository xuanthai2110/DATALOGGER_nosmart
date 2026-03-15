# test/test_driverhuawei.py
import time
from datetime import datetime
from communication.modbus_tcp import ModbusTCP
from drivers.huawei_sun2000110KTL import HuaweiSUN2000
from services.normalization_service import NormalizationService
import json

def _now() -> str:
    """Trả về timestamp giờ địa phương của Raspberry Pi (có timezone offset)."""
    return datetime.now().astimezone().isoformat(timespec='seconds')


def test_read_states():
    # Thay đổi IP và Port cho đúng với thực tế
    HOST = "192.168.1.8"  
    PORT = 502
    SLAVE_ID = [1, 3, 4, 5, 6, 7, 8, 9]
    
    # Khởi tạo kết nối Modbus TCP
    transport = ModbusTCP(host=HOST, port=PORT, timeout=3.0, retries=3)
    if not transport.connect():
        print("❌ Không thể kết nối tới Inverter")
        return
        
    
    try:
        norm = NormalizationService()
        print("Đang đọc trạng thái và mã lỗi từ Inverter Huawei...")
        for sid in SLAVE_ID:
            print(f"\n--- Inverter Slave ID: {sid} ---")
            driver = HuaweiSUN2000(transport, slave_id=sid)
            
            
            try:
                # Đọc toàn bộ dữ liệu từ Inverter
                raw = driver.read_all()

                # Chuẩn hoá dữ liệu
                data = norm.normalize(raw)
                warnings = norm.validate_snapshot(raw)
                if warnings:
                    print(f"  ⚠️  Cảnh báo dữ liệu: {warnings}")

                # --- Chuẩn bị block Inverter cho Telemetry ---
                # AC Data
                ac_data = {
                    "V_a": data.get("v_a", 0),
                    "V_b": data.get("v_b", 0),
                    "V_c": data.get("v_c", 0),
                    "I_a": data.get("i_a", 0),
                    "I_b": data.get("i_b", 0),
                    "I_c": data.get("i_c", 0),
                    "P_ac": data.get("p_inv_w", 0),
                    "Q_ac": data.get("q_inv_var", 0),
                    "PF": data.get("pf", 0),
                    "H": data.get("grid_hz", 0),
                    # Các thông số phụ khác từ Huawei có thể điền 0 nếu chưa map
                    "IR":     data.get("ir", 0),
                    "Temp_C": data.get("temp_c", 0),
                    "E_daily": data.get("e_daily", 0),
                    "E_monthly": data.get("e_daily", 0),
                    "E_total": data.get("e_total", 0),
                    "created_at": _now()
                }

                # MPPT Data
                mppts = []
                for i in range(1, 11):
                    v_mppt = data.get(f"mppt_{i}_voltage", 0)
                    i_mppt = data.get(f"mppt_{i}_current", 0)
                    
                    if v_mppt > 0 or i_mppt > 0:  # Chỉ lấy mppt có data
                        # Huawei strings (2 string per MPPT)
                        s1 = {"string_index": 2*i - 1, "I_mppt": data.get(f"string_{2*i-1}_current", 0), "Max_I": 0}
                        s2 = {"string_index": 2*i, "I_mppt": data.get(f"string_{2*i}_current", 0), "Max_I": 0}
                        
                        mppts.append({
                            "mppt_index": i,
                            "string_on_mppt": 2,
                            "V_mppt": v_mppt,
                            "I_mppt": i_mppt,
                            "P_mppt": round(v_mppt * i_mppt, 2),
                            "Max_I": 0, "Max_V": 0, "Max_P": 0,
                            "strings": [s1, s2],
                            "created_at": _now()
                        })

                # Error Data (nếu có lỗi khác STABLE)
                errors = []
                severity = data.get("severity", "STABLE")
                if severity != "STABLE" or data.get("fault_code", 0) != 0:
                    errors.append({
                        "fault_code": data.get("fault_code", 0),
                        "fault_description": data.get("fault_description", ""),
                        "repair_instruction": data.get("repair_instruction", ""),
                        "severity": severity,
                        "created_at": data.get("created_at", _now())
                    })

                # Build Telemetry Inverter Node
                inverter_telemetry = {
                    "serial_number": data.get("serial_number", f"UNKNOWN-{sid}"),
                    "ac": ac_data,
                    "mppts": mppts,
                    "errors": errors
                }
                
                print(json.dumps(inverter_telemetry, indent=4, ensure_ascii=False))
                
            except Exception as read_ex:
                print(f"❌ Lỗi khi đọc dữ liệu Inverter ID {sid}: {read_ex}")
            
    except Exception as e:
        print(f"❌ Lỗi tổng quát trong quá trình test: {e}")
        
    finally:
        transport.close()
        print("\nĐóng kết nối.")

if __name__ == "__main__":
    test_read_states()
