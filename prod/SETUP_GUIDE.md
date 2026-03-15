# Hướng dẫn Setup và Luồng Dữ liệu (Setup & Data Flow Guide)

Tài liệu này chi tiết cách khởi tạo hệ thống, luồng dữ liệu giữa Datalogger và Server, cấu trúc lưu trữ Local DB và cách truy xuất dữ liệu.

---

## 1. Quy trình Setup Hệ thống

Quy trình thiết lập gồm 2 giai đoạn chính:

### Giai đoạn 0: Tự động hóa Toàn diện
Nếu bạn muốn thực hiện tất cả các bước trên chỉ bằng một lệnh duy nhất, hãy sử dụng script:
`python scripts/setup_project.py`
Script này sẽ tự động chạy cả Giai đoạn 1 (Local) và Giai đoạn 2 (Server Sync).

### Giai đoạn 1: Khởi tạo Local (Offline)
Sử dụng script `scripts/setup_project_local.py`.
1.  **Đọc Cấu hình**: Script đọc thông tin dự án từ `config.py` (Tên dự án, Vị trí, Công suất...).
2.  **Khởi tạo Database**: Tạo file `metadata.db` và bảng `projects` nếu chưa có. Lưu thông tin dự án vào Local DB.
3.  **Quét Thiết bị (Scan Inverters)**:
    - Kết nối Modbus TCP/RTU tới Inverter.
    - Quét Slave ID (mặc định 1-30).
    - Lưu thông tin Inverter (Serial Number, Model, Brand...) vào bảng `inverters` local.
4.  **Cập nhật số lượng**: Đếm số Inverter tìm thấy thực tế và cập nhật lại trường `inverter_count` của Project trong Local DB.

### Giai đoạn 2: Đồng bộ Server (Online)
Sử dụng `scripts/sync_to_server.py` và `scripts/sync_inverters.py`.
1.  **Đăng ký Project**: Gửi thông tin Project lên Server (`POST /api/projects/requests/`).
    - *Trạng thái*: Chuyển thành `pending` trong Local DB.
    - *Lưu trữ*: Lưu `server_request_id` trả về từ Server.
2.  **Đăng ký Inverters**: Gửi danh sách Inverters lên Server (`POST /api/inverters/requests/`).
    - *Liên kết*: Tự động đính kèm `project_request_id` để Server biết Inverter thuộc Project nào.
    - *Lưu trữ*: Lưu `server_request_id` cho từng Inverter local.
3.  **Phê duyệt (CMS)**: Admin dùng CMS để `Approve` các Request.
4.  **Cập nhật ID thật**: Script sync sẽ kiểm tra trạng thái Request. Khi đã `approved`, Local DB sẽ cập nhật `server_id` thật từ Server.

---

## 2. Luồng Dữ liệu (Data Flow)

### A. Dữ liệu Đẩy lên (Upstream - Requests)

**1. Project Request Payload (`/api/projects/requests/`):**
```json
{
  "elec_meter_no": "string",
  "elec_price_per_kwh": 1783.0,
  "name": "Project Name",
  "location": "Province",
  "lat": 14.821533,
  "lon": 108.945834,
  "capacity_kwp": 1000.0,
  "ac_capacity_kw": 880.0,
  "inverter_count": 8
}
```

**2. Inverter Request Payload (`/api/inverters/requests/`):**
```json
{
  "inverter_index": 1,
  "serial_number": "SN123...",
  "brand": "Huawei",
  "model": "SUN2000...",
  "firmware_version": "V...",
  "phase_count": 3,
  "mppt_count": 10,
  "string_count": 20,
  "rate_dc_kwp": 110.0,
  "rate_ac_kw": 100.0,
  "is_active": true,
  "project_request_id": 1
}
```

### B. Dữ liệu Phản hồi (Downstream - Responses)

Khi thành công, Server trả về thông tin Request bao gồm `id` (Request ID) và `status` (pending/approved/rejected). Sau khi Admin duyệt, phản hồi sẽ có thêm `approved_project_id` hoặc `approved_inverter_id`.

---

## 3. Cấu trúc Database Local (SQLite)

Hệ thống sử dụng hai file database chính:

### metadata.db
Lưu trữ thông tin cấu hình và định danh thiết bị.
-   **Bảng `projects`**: Lưu thông tin dự án, `server_id`, `server_request_id`, và `sync_status`.
-   **Bảng `inverters`**: Lưu thông tin kỹ thuật của Inverter, Slave ID, và các ID đồng bộ với server.

### realtime.db
Lưu trữ dữ liệu vận hành (Polling dữ liệu mỗi 30-60 giây).
-   **Bảng `project_realtime`**: Tổng công suất, năng lượng trong ngày của cả dự án.
-   **Bảng `inverter_ac_realtime`**: Thông số điện xoay chiều (V, I, P, Q, F) của từng Inverter.
-   **Bảng `mppt_realtime` & `string_realtime`**: Thông số chi tiết phía DC.
-   **Bảng `inverter_errors`**: Lưu mã lỗi và mô tả lỗi từ Inverter.

---

## 4. Truy xuất Dữ liệu

### Local Retrieval
- Sử dụng class `MetadataDB` trong `database/sqlite_manager.py` để lấy thông tin Project/Inverter.
- Dùng SQL Window Functions để lấy dữ liệu realtime mới nhất từ `realtime.db`.

### Server Synchronization Logic
Hệ thống sử dụng `AuthService` để lấy JWT Token, sau đó gọi REST API qua `SetupService`.
- **Logic Sync**: Nếu bản ghi local chưa có `server_id`, nó sẽ gửi Request. Nếu đã có `server_request_id`, nó sẽ kiểm tra trạng thái (`Poll`) thay vì gửi lại.

---
*Tài liệu được cập nhật ngày: 2026-03-11*
