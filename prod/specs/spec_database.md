# Spec: Cơ Sở Dữ Liệu (Database)

## 1. Tổng Quan

Hệ thống sử dụng **2 file SQLite** tách biệt:

| File | Vai trò |
|---|---|
| `metadata.db` | Dữ liệu cấu hình tĩnh (Project, Inverter) |
| `realtime.db` | Dữ liệu vận hành thời gian thực |

Tách biệt để tránh xung đột write giữa 2 luồng: **Polling** (ghi realtime.db thường xuyên) và **Setup/Sync** (đọc/ghi metadata.db rải rác).

---

## 2. metadata.db

### Bảng `projects`

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | INT PK | ID nội bộ |
| `server_id` | INT | ID từ Cloud Server (sau khi approve) |
| `server_request_id` | INT | ID Request trên Server |
| `sync_status` | TEXT | `local_only`, `pending`, `synced`, `needs_update` |
| `name` | TEXT | Tên dự án |
| `location` | TEXT | Vị trí |
| `capacity_kwp` | REAL | Công suất DC (kWp) |
| `ac_capacity_kw` | REAL | Công suất AC (kW) |
| `inverter_count` | INT | Số lượng inverter |
| `lat`, `lon` | REAL | Tọa độ GPS |

### Bảng `inverters`

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | INT PK | ID nội bộ |
| `project_id` | INT FK | Thuộc dự án nào |
| `server_id` | INT | ID từ Server |
| `server_request_id` | INT | ID Request inverter trên Server |
| `slave_id` | INT | Modbus Slave ID (1-30) |
| `inverter_index` | INT | Thứ tự inverter trong dự án |
| `brand` | TEXT | Hãng (Huawei, Sungrow...) |
| `model` | TEXT | Model cụ thể |
| `serial_number` | TEXT | Số serial |
| `mppt_count` | INT | Số MPPT |
| `string_count` | INT | Số String |
| `rate_dc_kwp` | REAL | Công suất DC định mức |
| `rate_ac_kw` | REAL | Công suất AC định mức |
| `is_active` | BOOL | Đang hoạt động |
| `replaced_by_id` | INT | ID inverter thay thế nếu bị swap |
| `usage_start_at` | TEXT | Ngày bắt đầu sử dụng |
| `usage_end_at` | TEXT | Ngày ngưng sử dụng |

---

## 3. realtime.db

### Bảng `project_realtime`

Tổng hợp dữ liệu toàn dự án mỗi 5 phút.

| Cột | Đơn vị | Mô tả |
|---|---|---|
| `project_id` | — | FK |
| `P_ac` | kW | Tổng công suất AC của tất cả inverter |
| `P_dc` | kW | Tổng công suất DC |
| `E_daily` | kWh | Sản lượng ngày (cộng dồn từ inverter) |
| `E_monthly` | kWh | Sản lượng tháng |
| `E_total` | kWh | Tổng sản lượng tích luỹ |
| `Temp_C` | °C | Nhiệt độ cao nhất trong các inverter |
| `severity` | TEXT | Trạng thái tổng (`NORMAL`, `FAULT`...) |
| `created_at` | TEXT | Timestamp |

### Bảng `inverter_ac_realtime`

| Cột | Đơn vị | Mô tả |
|---|---|---|
| `inverter_id` | — | FK |
| `V_a`, `V_b`, `V_c` | V | Điện áp pha |
| `I_a`, `I_b`, `I_c` | A | Dòng điện pha |
| `P_ac` | kW | Công suất tác dụng |
| `Q_ac` | kVAr | Công suất phản kháng |
| `PF` | — | Hệ số công suất |
| `H` | Hz | Tần số lưới |
| `Temp_C` | °C | Nhiệt độ |
| `IR` | kΩ | Điện trở cách điện |
| `E_daily` | kWh | Sản lượng ngày |
| `E_monthly` | kWh | Sản lượng tháng (delta-sum) |
| `E_total` | kWh | Tổng sản lượng |

### Bảng `mppt_realtime`

| Cột | Mô tả |
|---|---|
| `mppt_index` | Số thứ tự MPPT (1-based) |
| `V_mppt` | Điện áp tức thời (V) |
| `I_mppt` | Dòng điện tức thời (A) |
| `P_mppt` | Công suất tức thời (kW) |
| `Max_V` | Điện áp cực đại hôm nay (V) |
| `Max_I` | Dòng điện cực đại hôm nay (A) |
| `Max_P` | Công suất cực đại hôm nay (kW) |

### Bảng `string_realtime`

| Cột | Mô tả |
|---|---|
| `mppt_id` | MPPT mà String này thuộc về |
| `string_id` | Số thứ tự String |
| `I_string` | Dòng điện tức thời (A) |
| `max_I` | Dòng điện cực đại hôm nay (A) |

### Bảng `inverter_errors`

| Cột | Mô tả |
|---|---|
| `project_id` | FK |
| `inverter_id` | FK |
| `fault_code` | Mã lỗi (unified hoặc custom như 9999) |
| `fault_description` | Tên lỗi |
| `repair_instruction` | Hướng dẫn xử lý |
| `severity` | ERROR / WARNING / DISCONNECT |
| `created_at` | Thời điểm phát hiện |

---

## 4. Mô Hình Truy Cập

- **Class `MetadataDB`**: Quản lý `metadata.db` — Dùng cho Setup, Polling.
- **Class `RealtimeDB`**: Quản lý `realtime.db` — Dùng riêng cho Polling, batch insert.
- **WAL Mode**: Bật `PRAGMA journal_mode=WAL` để cho phép đọc song song trong khi ghi.

---

## 5. Chiến Lược Lưu Trữ

- **Batch Insert**: `post_inverter_ac_batch()`, `post_mppt_batch()`, `post_string_batch()` — Gom nhiều records thành một lần ghi cho hiệu suất cao.
- **No Delete**: Dữ liệu realtime **không bao giờ bị xóa** từ datalogger (xóa theo chính sách retention nếu muốn).
- **Timestamps**: Dùng ISO format `YYYY-MM-DDTHH:MM:SS`.
