# Solar Datalogger — Tổng Quan Dự Án

## 1. Bối Cảnh & Vấn Đề

Một trạm điện năng lượng mặt trời (Solar PV) thường có nhiều inverter (biến tần), mỗi inverter canh tác dòng điện DC từ hàng chục chuỗi pin mặt trời (PV String) và chuyển đổi thành AC để đấu nối lưới điện. Việc theo dõi hiệu suất và phát hiện sự cố của từng inverter theo thời gian thực là tối quan trọng để:

- Tối đa hóa sản lượng điện.
- Phát hiện sớm các lỗi phần cứng (cắm ngược cực, đứt string...).
- Cung cấp dữ liệu cho báo cáo vận hành và thanh toán.

Các giải pháp thương mại hiện có thường **độc quyền**, **chi phí cao**, và **không tích hợp được** với hệ thống quản lý nội bộ. Dự án này xây dựng một nền tảng datalogger **mở, linh hoạt và có khả năng mở rộng** chạy trực tiếp trên phần cứng nhúng (Raspberry Pi).

---

## 2. Mục Tiêu Dự Án

| Mục tiêu | Mô tả |
|---|---|
| **Thu thập dữ liệu thời gian thực** | Đọc dữ liệu từ inverter qua Modbus TCP/RTU mỗi 30 giây |
| **Lưu trữ tại chỗ (Local-first)** | Dữ liệu được lưu vào SQLite ngay trên thiết bị, đảm bảo hoạt động khi mất internet |
| **Đồng bộ lên Cloud** | Đẩy dữ liệu và trạng thái lên hệ thống quản lý tập trung (Cloud CMS) |
| **Phát hiện sự cố** | Tự động phát hiện và phân loại lỗi inverter, cảnh báo ngược cực |
| **Quản lý vòng đời thiết bị** | Theo dõi thay thế inverter, đảm bảo tính liên tục lịch sử dữ liệu |
| **Mở rộng đa hãng** | Hỗ trợ Huawei, Sungrow và có thể thêm các hãng khác qua Driver pattern |

---

## 3. Phạm Vi Hệ Thống

```
┌────────────────────────────────────────────────────────────┐
│                     Raspberry Pi (Datalogger)               │
│                                                             │
│  ┌────────────┐     ┌──────────────┐     ┌──────────────┐  │
│  │  Drivers   │────▶│  Services    │────▶│  SQLite DB   │  │
│  │ (Modbus)   │     │ (Logic)      │     │ metadata.db  │  │
│  └────────────┘     └──────────────┘     │ realtime.db  │  │
│         │                  │             └──────────────┘  │
│    [Inverters]       [Polling, Tracking,                    │
│    Huawei / SG       Normalization...]                      │
└────────────────────────────────────────────────────────────┘
                             │
                    [Internet / LAN]
                             │
                    ┌────────────────┐
                    │  Cloud Server   │
                    │  REST API + CMS │
                    └────────────────┘
```

---

## 4. Kiến Trúc Tổng Thể

### Lớp Giao Tiếp (Communication)
- `ModbusTCP` — Kết nối Inverter qua Ethernet (Huawei SUN2000)
- `ModbusRTU` — Kết nối Inverter qua RS485 (Sungrow)

### Lớp Driver
- `BaseDriver` — Abstract interface chung
- `HuaweiSUN2000Driver` — Map thanh ghi, đọc `read_info`, `read_ac`, `read_dc`, `read_fault_state`
- `SungrowSG110CXDriver` — Tương tự cho Sungrow

### Lớp Service
- `PollingService` — Điều phối chu kỳ đọc 30s và lưu 5 phút
- `TrackingService` — Theo dõi E_monthly, Max I/V của MPPT/String
- `NormalizationService` — Lọc nhiễu, chuẩn hoá đơn vị, phát hiện giá trị bất thường
- `SetupService` — Scan thiết bị, đăng ký lên server
- `AuthService` — Quản lý JWT token, refresh tự động
- `FaultStateService` — Bản đồ mã lỗi thống nhất giữa các hãng

### Lớp Database (SQLite)
- `metadata.db` — Cấu hình dự án, thông tin inverter, trạng thái đồng bộ
- `realtime.db` — Dữ liệu vận hành: AC, DC, MPPT, String, Project tổng hợp, Lỗi

### Lớp Schema
- Python `dataclasses` — Định nghĩa kiểu dữ liệu chặt chẽ cho Project, Inverter, Realtime data

---

## 5. Công Nghệ Sử Dụng

| Thành phần | Công nghệ |
|---|---|
| Ngôn ngữ | Python 3.10+ |
| Giao thức thiết bị | Modbus TCP / RTU (pymodbus) |
| Cơ sở dữ liệu | SQLite3 (WAL mode) |
| API Client | requests (REST API) |
| Serialization | Python Dataclasses + JSON |
| Phần cứng | Raspberry Pi (Linux ARM) |

---

## 6. Các Luồng Công Việc Chính

### 6.1 Khởi động & Cấu hình lần đầu
1. Chạy `scripts/setup_project_local.py` — Tạo DB, scan inverter.
2. Chạy `scripts/sync_inverters.py` — Đẩy thông tin lên Cloud Server.
3. Admin duyệt trên CMS.
4. Script cập nhật `server_id` từ Cloud về Local DB.

### 6.2 Vận hành thường ngày
1. `PollingService.run_forever()` — Vòng lặp 30s mỗi chu kỳ.
2. Đọc dữ liệu → Chuẩn hoá → Tracking → Buffer.
3. Mỗi 5 phút → Lưu batch vào `realtime.db` và gửi lên Cloud.

### 6.3 Phát hiện thay thế Inverter
- Mỗi lần đọc, so sánh `serial_number` với DB.
- Nếu khác → Mark inverter cũ là inactive → Tạo inverter mới.

---

## 7. Cấu Trúc Thư Mục

```
code/
├── communication/     # Modbus TCP/RTU
├── database/          # SQLite Manager
├── drivers/           # Huawei, Sungrow drivers
├── schemas/           # Dataclass models
├── services/          # Business logic
├── scripts/           # Entrypoints
├── tests/             # Unit tests
├── config.py          # Cấu hình hệ thống
└── main.py

prod/
├── Project.md         # Tổng quan dự án (file này)
├── SETUP_GUIDE.md     # Hướng dẫn setup
├── REQUEST_APPROVAL_FLOW.md  # Luồng đăng ký & duyệt
└── specs/
    ├── spec_polling.md
    ├── spec_normalization.md
    ├── spec_tracking.md
    ├── spec_fault_detection.md
    └── spec_setup_sync.md
```

---

## 8. Trạng Thái Phát Triển

| Chức năng | Trạng thái |
|---|---|
| Driver Huawei SUN2000 | ✅ Hoàn thiện |
| Driver Sungrow SG110CX | ✅ Hoàn thiện |
| Modbus TCP | ✅ Hoàn thiện |
| Modbus RTU | ✅ Hoàn thiện |
| Setup & Scan | ✅ Hoàn thiện |
| Sync lên Server | ✅ Hoàn thiện |
| Polling 30s / 5m | ✅ Hoàn thiện |
| Normalization & Validation | ✅ Hoàn thiện |
| Tracking (E_monthly, Max) | ✅ Hoàn thiện |
| Fault Detection | ✅ Hoàn thiện |
| Reverse Polarity Detection | ✅ Hoàn thiện |
| Inverter Replacement Logic | ✅ Hoàn thiện |
| Web Dashboard | 🚧 Đang phát triển |
| MQTT Power Control | ❌ Chưa triển khai |

---
*Cập nhật: 2026-03-12*
