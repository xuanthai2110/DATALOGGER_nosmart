# Spec: Setup, Scan & Đồng Bộ Server (Cập nhật)

## 1. Mục Tiêu

Datalogger được cấu hình thông qua một **Local Web UI** (chạy trên port 5000 cục bộ). Kỹ thuật viên sử dụng giao diện này để đăng nhập vào hệ thống, cấu hình thông tin trạm (Project), quét (scan) các Inverter qua giao thức Modbus, và đồng bộ (sync) dữ liệu này lên Cloud Server.

---

## 2. Kiến Trúc Tổng Quan

```
         Máy tính kỹ thuật viên / Màn hình local
         (Trình duyệt web)
                  │
          http://localhost:5000
                  │
┌─────────────────▼────────────────────────┐
│               Datalogger                 │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │     Local Web UI (FastAPI)         │  │
│  │     scripts/run_web.py             │  │
│  │                                    │  │
│  │  - Đăng nhập trên web (Lưu Token)  │  │
│  │  - Nhập thông tin Project          │  │
│  │  - Chọn Driver + Comm params       │  │
│  │  - Trigger Scan / Detect           │  │
│  │  - Xem kết quả, confirm & Sync     │  │
│  └─────────────┬──────────────────────┘  │
│                │ đọc/ghi                 │
│  ┌─────────────▼──────────────────────┐  │
│  │ SQLite DB (metadata.db)            │  │
│  │ File lưu Token (tokens.json)       │  │
│  └─────────────┬──────────────────────┘  │
│                │                         │
│  ┌─────────────▼──────────────────────┐  │
│  │ AuthService / SetupService / ...   │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
                  │  Internet
                  ▼
        Cloud Server (CMS + REST API)
```

---

## 3. Quản Lý Xác Thực (Authentication)

Datalogger sử dụng **Token-based Authentication** để giao tiếp với Server:
- Kỹ thuật viên nhập email/password trên Web UI (Tab "Login").
- `AuthService` gọi API `/api/auth/token` lấy `access_token` và `refresh_token`.
- Token được lưu trữ trực tiếp vào tệp cục bộ (`database/tokens.json`) để dự phòng mất điện/khởi động lại.
- Các request đồng bộ sau này đều đính kèm `Bearer {access_token}`. Nếu token hết hạn, hệ thống tự động gọi API refresh.

---

## 4. Giao Diện Web UI (Local)

Web UI chia làm các Tab chức năng chính:


### 4.1 Tab: Login
4.1.1: Login trên server
- Check xem đã có access token chưa, nếu có thì dùng access token, tự động gọi API refresh. nếu access token hết hạn thì gọi API refresh.
- Nếu không có access token thì đăng nhập vào Server bằng tài khoản do Admin cấp. Lưu thông tin xác thực.
4.1.2: Login cục bộ trên web
- khi vào url của web (ví dụ http://{ip local _rasberrypi})thì vào page login trước
- Đăng nhập bằng tài khoản mặc định: username: admin, pass: admin -> server cũng trả về access token và refresh token cho web ui để lưu vào file tokens_local.json
- 

### 4.2 Tab: Dự Án
- Cấu hình thông tin cơ bản: Tên dự án, Mã công tơ điện (quan trọng để định danh), Tọa độ, Công suất...
- Lưu thông tin vào `metadata.db` cục bộ.

### 4.3 Tab: Thiết Bị (Danh Sách Inverter)
- Cấu hình RS485/Modbus (Host, Port, loại Driver).
- Nhập dải Slave ID (VD: 1-30).
- **Hành động:** 
  - `Quét (Scan)`: Chạy dò tìm inverter(retry 1 lần nếu không được, timeout 1s) trên dải ID đã cấu hình. Lưu kết quả vào Local DB.
  - `Đồng Bộ Server`: Đẩy thông tin Project và danh sách thiết bị hiển thị lên Cloud.khoảng cách mỗi request là 1s. Kiểm tra lại server trả về những gì. Đọc REQUEST_APPROVAL_FLOW.md để hiểu luồng giao tiếp giữa datalogger vs server trong trường hợp request approval.
  - Đồng bộ project trước, sau khi đồng bộ project xong thì mới đồng bộ inverter. Khi đồng bộ project lên server sẽ có 3 trường hợp:
        - Nếu project đã tồn tại trên server conflict
        - Nếu project chưa tồn tại trên server thì sẽ trả về 
        {
                "elec_meter_no": "string",
                "elec_price_per_kwh": 0,
                "name": "string",
                "location": "string",
                "lat": 0,
                "lon": 0,
                "capacity_kwp": 0,
                "ac_capacity_kw": 0,
                "inverter_count": 0,
                "id": 0,  // id của request
                "owner_id": 0,
                "requested_by_id": 0, // id của user
                "reviewed_by_id": 0, // id của admin
                "approved_project_id": 0, // id của project nếu được chấp nhận
                "status": "pending", // pending, approved, rejected
                "review_note": "string", // ghi chú khi approve/reject
                "reviewed_at": "2026-03-13T09:06:01.633Z", // thời điểm review
                "created_at": "2026-03-13T09:06:01.633Z", // thời điểm tạo
                "updated_at": "2026-03-13T09:06:01.633Z" // thời điểm cập nhật
                }
        Lấy request_id để get kiểm tra Xem chi tiết 1 request project

        - `GET /api/projects/requests/{request_id}` để xem trạng thái của request đã được approve hay reject hay vẫn còn pending
  - Xóa Inverter hoặc Xóa toàn bộ Data Local.

---

## 5. Luồng Scan & Detect

```
POST /api/setup/scan (Web UI)
        │
        ▼
Load cấu hình Modbus (Loại Inverter, Host, Port)
        │
        ▼
Khởi tạo TCP/RTU Transport và Driver tương ứng (VD: HuaweiDriver)
        │
        ▼
Vòng lặp (Slave ID từ 1 đến 30):
  └── driver.read_info()
        ├── Quét thấy → Gán `project_id`, `inverter_index`. Lưu vào `inverters` DB.
        └── Không thấy → Bỏ qua, thử ID tiếp theo.
        │
        ▼
Trả về danh sách các Slave ID tìm thấy cho Web UI hiển thị.
```

---

## 6. Luồng Đồng Bộ Lên Cloud Server (Sync)

Khi ấn "Đồng Bộ", Datalogger sẽ gọi tuần tự quy trình Request-Approval.

### 6.1 Đồng Bộ Project
1. Lấy dữ liệu Project từ Local DB.
2. Nếu đã có `server_id` → Bỏ qua, đã đồng bộ xong.
3. Nếu gửi Request mới (`POST /api/projects/requests/`):
        - Nếu project đã tồn tại trên server conflict
        - Nếu project chưa tồn tại trên server thì sẽ trả về 
        {
                "elec_meter_no": "string",
                "elec_price_per_kwh": 0,
                "name": "string",
                "location": "string",
                "lat": 0,
                "lon": 0,
                "capacity_kwp": 0,
                "ac_capacity_kw": 0,
                "inverter_count": 0,
                "id": 0,  // id của request
                "owner_id": 0,
                "requested_by_id": 0, // id của user
                "reviewed_by_id": 0, // id của admin
                "approved_project_id": 0, // id của project nếu được chấp nhận
                "status": "pending", // pending, approved, rejected
                "review_note": "string", // ghi chú khi approve/reject
                "reviewed_at": "2026-03-13T09:06:01.633Z", // thời điểm review
                "created_at": "2026-03-13T09:06:01.633Z", // thời điểm tạo
                "updated_at": "2026-03-13T09:06:01.633Z" // thời điểm cập nhật
                }
        Lấy request_id để get kiểm tra Xem chi tiết 1 request project

        - `GET /api/projects/requests/{request_id}` để xem trạng thái của request đã được approve hay reject hay vẫn còn pending

### 6.2 Đồng Bộ Inverter
1. Lấy danh sách Inverters từ Local DB.
2. Với các inverter chưa có ID:
   - Gửi request mới (`POST /api/inverters/requests/`) kèm tham chiếu tới Dự án (Bằng `project_request_id` hoặc `project_id`).
   - Xử lý mã trả về tương tự như Project:
     - `200/201`: Lưu `server_request_id`, trạng thái `pending`.
     - `409 Conflict`: Inverter đã tồn tại trên Server. Cập nhật `sync_status = 'approved'`.

### 6.3 Polling Trạng Thái Phê Duyệt
Các script/API (ví dụ khi khởi động lại hoặc có Cron Job) sẽ thực hiện kiểm tra trạng thái (`GET /api/projects/requests/<id>`...). Nếu CMS đã duyệt, Server trả về trạng thái `approved` và cung cấp Identifier thật (Ví dụ: `approved_project_id`). Datalogger sẽ cập nhật trường `server_id` tương ứng vào Local DB.

---

## 7. Cấu Trúc Script Chức Năng Cốt Lõi

- `scripts/run_web.py`: Chạy Local Dashboard (FastAPI/Uvicorn).
- `scripts/setup_project_local.py`: (Dành cho Dev/Terminal) Tạo/xóa project và quét thiết bị (chỉ lưu local).
- `scripts/sync_to_server.py`: (Dành cho Dev/Terminal) Đồng bộ dữ liệu có sẵn từ `metadata.db` local đẩy thẳng lên Server mà không quét lại.
- `services/setup_service.py`: Chứa class `SetupService` thực thi logic Scan và Sync phức tạp.
