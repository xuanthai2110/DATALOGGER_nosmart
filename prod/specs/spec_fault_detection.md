# Spec: Phát Hiện Lỗi & Trạng Thái Inverter

## 1. Mục Tiêu

Cung cấp một hệ thống mã lỗi **thống nhất** giữa các hãng inverter khác nhau (Huawei, Sungrow...) và lưu trữ lỗi có cấu trúc vào database để phục vụ cảnh báo và báo cáo.

---

## 2. Thành Phần

| Thành phần | File |
|---|---|
| Bản đồ mã lỗi | `services/fault_state_service.py` |
| Ghi lỗi vào DB | `services/tracking_service.py` |
| Lưu trữ | `realtime.db` → bảng `inverter_errors` |

---

## 3. Mô Hình Dữ Liệu Lỗi Thống Nhất

`fault_state_service.py` định nghĩa 3 loại bản đồ:

### `UNIFIED_STATES` — Trạng thái vận hành chung

| ID | Tên | Mô tả |
|---|---|---|
| 1 | RUNNING | Đang chạy bình thường |
| 2 | STANDBY | Chờ |
| 3 | STARTING | Đang khởi động |
| 4 | STOPPED | Đã dừng |
| 5 | FAULT | Lỗi |
| 6 | ALARM_RUNNING | Đang chạy với cảnh báo |
| 7 | DERATING | Giảm công suất |
| ... | | |

### `HUAWEI_FAULT_MAP` — Mã lỗi Huawei → Unified

```
Huawei Code 2001 → UNIFIED.GRID_OVERVOLTAGE (severity: ERROR)
Huawei Code 2022 → UNIFIED.FAN_FAULT (severity: WARNING)
...
```

### `SUNGROW_FAULT_MAP` — Mã lỗi Sungrow → Unified

```
Sungrow Code 1 → UNIFIED.GRID_OVERVOLTAGE (severity: ERROR)
Sungrow Code 14 → UNIFIED.STRING_FAULT (severity: WARNING)
...
```

---

## 4. Phân Loại Mức Độ Nghiêm Trọng (Severity)

| Severity | Ý nghĩa | Hành động |
|---|---|---|
| `STABLE` | Bình thường (RUNNING) | Không ghi lỗi |
| `WARNING` | Cần chú ý nhưng vẫn chạy | Ghi log, không ghi DB |
| `ERROR` | Lỗi nghiêm trọng, có thể dừng máy | **Ghi vào `inverter_errors`** |
| `DISCONNECT` | Mất kết nối/giao tiếp | **Ghi vào `inverter_errors`** |

---

## 5. Cấu Trúc Bảng `inverter_errors`

| Cột | Kiểu | Mô tả |
|---|---|---|
| `project_id` | INT | Project chứa inverter |
| `inverter_id` | INT | Inverter bị lỗi |
| `fault_code` | INT | Mã lỗi (unified hoặc custom) |
| `fault_description` | TEXT | Mô tả lỗi (tiếng Anh) |
| `repair_instruction` | TEXT | Hướng dẫn xử lý |
| `severity` | TEXT | ERROR / WARNING / DISCONNECT |
| `created_at` | TEXT | Thời điểm phát hiện |

---

## 6. Lỗi Tùy Chỉnh (Custom Faults)

Ngoài các mã từ hãng, hệ thống tự định nghĩa thêm:

| Fault Code | Tên | Mô tả |
|---|---|---|
| `9999` | REVERSE_POLARITY | Phát hiện giá trị dòng/áp âm lớn hơn -1.0 trên MPPT hoặc String |

---

## 7. Luồng Phát Hiện Lỗi

```
Driver.read_all()
    │
    ├── Trả về fault_code + severity
    │
    ▼
TrackingService.log_inverter_error(inv, data)
    │
    ├── fault_code != 0 AND severity == "ERROR"?
    │       ├── YES → Ghi vào inverter_errors ngay lập tức (30s cycle)
    │       └── NO  → Bỏ qua
    │
NormalizationService.normalize(data)
    │
TrackingService.update_max_values(project_id, inv_id, data, ...)
    │
    ├── Phát hiện mppt_i_current < -1.0 hoặc string_i_current < -1.0?
    │       └── YES → Ghi REVERSE_POLARITY vào inverter_errors
```

---

## 8. Các Nhóm Lỗi Chính

| Nhóm | Ví dụ |
|---|---|
| Lưới điện | GRID_OVERVOLTAGE, GRID_LOSS, GRID_OVERCURRENT |
| DC/PV | PV_REVERSE_CONNECTION, PV_OVERVOLTAGE, STRING_FAULT |
| Điện tử | LEAKAGE_CURRENT, GROUND_FAULT, DC_OVER_CURRENT |
| Nhiệt độ | DEVICE_OVER_TEMPERATURE, FAN_FAULT |
| Phần cứng | RELAY_FAULT, POWER_MODULE_FAULT, SENSOR_FAULT |
| Giao tiếp | RS485_FAULT, MODBUS_FAULT, METER_COMM_FAULT |
| Bảo vệ | ARC_FAULT, RAPID_SHUTDOWN_TRIGGERED |
| Tùy chỉnh | REVERSE_POLARITY (code 9999) |
