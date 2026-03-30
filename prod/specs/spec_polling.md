# Tài liệu Kỹ thuật: Luồng Polling & Thu thập Dữ liệu (Cập nhật 2026)

Tài liệu này mô tả chi tiết kiến trúc và luồng thực hiện của hệ thống Polling trong Datalogger, được tối ưu hóa cho hiệu suất cao và giảm tải Database.

---

## 1. Kiến trúc Tổng quan
Hệ thống Polling hoạt động theo mô hình **Producer-Cache**, trong đó Polling Service liên tục thu thập dữ liệu và đẩy vào bộ nhớ RAM (SQLite Cache) để các dịch vụ khác tiêu thụ.

| Thành phần | Vai trò | Tệp tin |
|---|---|---|
| **Runner** | Điều phối vòng lặp chính, quản lý nhịp độ (pacing) và in log snapshot. | `run_polling.py` |
| **Polling Service** | Thực hiện kết nối Modbus, nạp Driver, và ghi dữ liệu vào Cache. | `polling_service.py` |
| **Cache DB** | Database SQLite nằm trên RAM (`/dev/shm`) lưu trạng thái realtime 10s. | `sqlite_manager.py` |
| **Drivers** | Thư viện giao tiếp riêng cho từng hãng (Huawei, Sungrow...). | `drivers/` |

---

## 2. Luồng Thực hiện Chi tiết (Step-by-Step)

### Bước 1: Khởi tạo (Initialization)
- Nạp cấu hình từ `backend/config.py`.
- Kết nối `MetadataDB` (chứa thông tin thiết bị) và `CacheDB` (RAM).
- Khởi tạo `PollingService`.

### Bước 2: Quản lý Cấu hình (Config Caching) - *Mới*
Để tránh việc truy vấn SQL liên tục vào ổ cứng, hệ thống sử dụng cơ chế Cache cấu hình:
- Gọi `service.get_polling_config()`.
- **Logic Refresh**: Cấu hình (danh sách Project/Inverter) được lưu trong RAM. Chỉ sau mỗi **5 phút** (`CONFIG_REFRESH_INTERVAL`), hệ thống mới truy vấn Database một lần để cập nhật thay đổi (nếu có).
- Nếu cache còn hiệu lực, hệ thống sử dụng danh sách Inverter từ RAM.

### Bước 3: Thu thập Dữ liệu (Data Acquisition)
- Duyệt qua danh sách Inverter của từng Project.
- **Xác định Transport**: Tự động chọn Modbus TCP (Cổng 502) hoặc Modbus RTU (RS485) dựa trên Brand.
- **Đọc dữ liệu thô**: Gọi `driver.read_all()` để quét toàn bộ các register (Input/Holding).

### Bước 4: Chuẩn hóa & Xử lý (Normalization)
- Gọi `NormalizationService.normalize()`:
    - Áp dụng các hệ số scale (ví dụ: nhân 0.1, 0.01).
    - Làm tròn số thập phân.
    - Xử lý các giá trị đặc biệt (Invalid/NaN).

### Bước 5: Lưu trữ vào RAM Cache (Persistence)
Dữ liệu được đẩy vào `CacheDB` qua 4 nhóm bảng chính:
1. **AC Cache**: Công suất tổng, sản lượng ngày, điện áp pha.
2. **MPPT Cache**: Điện áp/Dòng điện từng kênh MPPT.
3. **String Cache**: Dòng điện từng chuỗi PV String.
4. **Error Cache**: Mã Status thô và mã Fault từ thiết bị.

### Bước 6: Hiển thị & Giám sát (Reporting)
- Sau khi kết thúc một vòng quét của Project, Runner gọi hàm `print_full_cache_snapshot()`.
- Hàm này truy vấn ngược lại từ `CacheDB` và in bảng tổng hợp ra Terminal:
    - Bảng AC Summary (P_ac, E_daily, V_a, Temp, Status:Fault).
    - Chi tiết MPPT (Watt).
    - Chi tiết Strings (Ampere).

---

## 3. Các tham số điều khiển (`config.py`)

- `POLL_INTERVAL`: Thời gian nghỉ giữa các vòng quét (Mặc định 10-30s).
- `CONFIG_REFRESH_INTERVAL`: Thời gian giữ cache cấu hình thiết bị trong RAM (Mặc định 300s/5 phút).
- `CACHE_DB`: Đường dẫn file DB trên RAM (Thường là `/dev/shm/hirubic_cache.db`).

---

## 4. Ưu điểm của Luồng Hiện tại
1. **Zero Database I/O Overhead**: Gần như không ghi xuống ổ cứng trong quá trình quét, bảo vệ thẻ nhớ SD.
2. **High Visibility**: Snapshot hiển thị đầy đủ mã code Status:Fault thô để kỹ thuật dễ đối soát.
3. **Dynamic Refresh**: Tự động nhận diện thiết bị mới sau 5 phút mà không cần restart service.
