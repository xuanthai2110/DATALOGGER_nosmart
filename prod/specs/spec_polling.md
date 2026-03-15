# Spec: Polling & Thu Thập Dữ Liệu

## 1. Mục Tiêu

Thu thập dữ liệu liên tục từ tất cả các inverter đang hoạt động, đảm bảo:
- Dữ liệu được đọc thường xuyên (30 giây/lần) để phát hiện biến động nhanh.
- Dữ liệu được lưu vào database theo chu kỳ 5 phút để tối ưu I/O.
- Không mất dữ liệu khi một lần đọc thất bại.

---

## 2. Các Thành Phần Liên Quan

| Thành phần | File |
|---|---|
| `PollingService` | `services/polling_service.py` |
| `TrackingService` | `services/tracking_service.py` |
| `NormalizationService` | `services/normalization_service.py` |
| Driver (Huawei/Sungrow) | `drivers/` |
| Database Manager | `database/sqlite_manager.py` |
| Entry Point | `scripts/run_polling.py` |

---

## 3. Chu Kỳ Hoạt Động

```
             ┌─────────────────────────────────┐
             │         run_forever()            │
             └──────────────┬──────────────────┘
                            │ loop
              ┌─────────────▼─────────────────┐
              │     poll_all_inverters()       │ ◄── mỗi 30 giây
              │  - Kết nối Modbus             │
              │  - Đọc dữ liệu từ driver      │
              │  - Kiểm tra serial number      │
              │  - Tính E_monthly              │
              │  - Cập nhật Max I/V            │
              │  - Buffer kết quả              │
              └─────────────────────────────────┘
                            │ mỗi 10 lần (5 phút)
              ┌─────────────▼─────────────────┐
              │       save_to_database()       │
              │  - Chuẩn hoá dữ liệu          │
              │  - Lưu Inverter AC batch       │
              │  - Lưu MPPT batch              │
              │  - Lưu String batch            │
              │  - Lưu Project summary         │
              └─────────────────────────────────┘
```

---

## 4. Buffer & Xử Lý Lỗi

- **Buffer**: Dictionary `{inverter_id: last_valid_data}` lưu bản đọc cuối cùng thành công.
- Nếu một lần đọc 30s **thất bại** → buffer giữ nguyên dữ liệu cũ.
- Khi đến chu kỳ 5 phút → dùng dữ liệu từ buffer (dữ liệu cuối gần nhất).
- Nếu buffer rỗng (chưa đọc được lần nào) → inverter đó bị bỏ qua trong lần lưu đó.

---

## 5. Dữ Liệu Được Lưu Theo Chu Kỳ 5 Phút

### Bảng `inverter_ac_realtime`
| Trường | Đơn vị | Mô tả |
|---|---|---|
| `V_a`, `V_b`, `V_c` | V | Điện áp pha A, B, C |
| `I_a`, `I_b`, `I_c` | A | Dòng điện pha A, B, C |
| `P_ac` | kW | Công suất tác dụng AC |
| `Q_ac` | kVAr | Công suất phản kháng AC |
| `PF` | — | Hệ số công suất (-1 đến 1) |
| `H` | Hz | Tần số lưới |
| `Temp_C` | °C | Nhiệt độ inverter |
| `IR` | kΩ | Điện trở cách điện |
| `E_daily` | kWh | Sản lượng trong ngày |
| `E_monthly` | kWh | Sản lượng trong tháng (tính theo delta) |
| `E_total` | kWh | Tổng sản lượng tích luỹ |

### Bảng `mppt_realtime`
| Trường | Mô tả |
|---|---|
| `V_mppt`, `I_mppt`, `P_mppt` | Điện áp/Dòng/Công suất tức thời |
| `Max_V`, `Max_I`, `Max_P` | Giá trị cực đại trong ngày |

### Bảng `string_realtime`
| Trường | Mô tả |
|---|---|
| `I_string` | Dòng điện tức thời |
| `max_I` | Dòng điện cực đại trong ngày |

### Bảng `project_realtime`
Tổng hợp từ tất cả inverter: `P_ac`, `P_dc`, `E_daily`, `E_monthly`, `E_total`, `Temp_C` max.

---

## 6. Kiểm Tra Serial Number & Thay Thế Inverter

Mỗi chu kỳ 30 giây:
1. Đọc `serial_number` từ inverter thực tế.
2. So sánh với `serial_number` trong `metadata.db`.
3. Nếu **không khớp** → Inverter đã được thay thế:
   - Tạo inverter mới trong DB với serial mới.
   - Mark inverter cũ là `is_active = False`, ghi `replaced_by_id`.
   - Hệ thống sẽ cần sync lên Server ở lần tiếp theo.

---

## 7. Cấu Hình

| Tham số | Giá trị | File |
|---|---|---|
| `POLL_INTERVAL` | 30 (giây) | `config.py` |
| Chu kỳ lưu DB | 10 × POLL_INTERVAL = 5 phút | `polling_service.py` |
| `MODBUS_TCP_HOST` | IP inverter | `config.py` |
| `MODBUS_PORT` | Cổng RTU | `config.py` |
