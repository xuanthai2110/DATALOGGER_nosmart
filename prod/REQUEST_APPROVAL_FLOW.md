# Quy Trình Phê Duyệt Request

Tài liệu này mô tả luồng tạo tạm `Project` và `Inverter` trước khi được admin phê duyệt.

## Mục tiêu

- User không tạo trực tiếp `projects` và `inverters` trong luồng mới.
- Dữ liệu được lưu tạm vào bảng request.
- Chỉ khi admin approve thì mới tạo bản ghi thật.
- Các endpoint CRUD cũ vẫn giữ nguyên, không đổi hành vi.

## Các bảng dữ liệu mới

### 1. `project_create_requests`

Bảng này lưu snapshot dữ liệu project mà user gửi lên.

Các trường quan trọng:

- `owner_id`: user sẽ sở hữu project sau khi được approve
- `requested_by_id`: user gửi request
- `reviewed_by_id`: admin đã review
- `approved_project_id`: id của project thật sau khi approve
- `status`: `pending`, `approved`, `rejected`
- `review_note`: ghi chú khi approve/reject
- `reviewed_at`: thời điểm review
- Các field nghiệp vụ của project: `name`, `location`, `capacity_kwp`, `ac_capacity_kw`, `inverter_count`, ...

### 2. `inverter_create_requests`

Bảng này lưu snapshot dữ liệu inverter mà user gửi lên.

Các trường quan trọng:

- `requested_by_id`: user gửi request
- `reviewed_by_id`: admin đã review
- `approved_inverter_id`: id của inverter thật sau khi approve
- `status`: `pending`, `approved`, `rejected`
- `review_note`: ghi chú khi approve/reject
- `reviewed_at`: thời điểm review
- `project_id`: trỏ đến project thật đã tồn tại
- `project_request_id`: trỏ đến project request nếu project chưa được approve
- Các field nghiệp vụ của inverter: `serial_number`, `brand`, `model`, `mppt_count`, ...

Ràng buộc:

- Chỉ được có một trong hai trường `project_id` hoặc `project_request_id`.
- Không được để trống cả hai.

## Endpoint mới cho Project

### 1. User gửi request tạo project

- `POST /api/projects/requests/`

Kết quả:

- Tạo 1 dòng trong `project_create_requests`
- `status = pending`
- Chưa tạo dòng nào trong bảng `projects`

### 2. Xem danh sách request project

- `GET /api/projects/requests/`

Hỗ trợ:

- Pagination
- Filter theo query `status`

### 3. Xem chi tiết 1 request project

- `GET /api/projects/requests/{request_id}`

### 4. Admin approve request project

- `POST /api/projects/requests/{request_id}/approve`

Khi approve:

1. Kiểm tra request tồn tại
2. Kiểm tra request đang ở trạng thái `pending`
3. Kiểm tra `owner_id` vẫn hợp lệ và đang active
4. Tạo dòng thật trong bảng `projects`
5. Cập nhật request:
   - `status = approved`
   - `approved_project_id = id project vừa tạo`
   - `reviewed_by_id = admin id`
   - `reviewed_at = thời điểm approve`
   - `review_note = ghi chú nếu có`

### 5. Admin reject request project

- `POST /api/projects/requests/{request_id}/reject`

Khi reject:

1. Kiểm tra request tồn tại
2. Kiểm tra request đang ở trạng thái `pending`
3. Không tạo project thật
4. Cập nhật request:
   - `status = rejected`
   - `reviewed_by_id = admin id`
   - `reviewed_at = thời điểm reject`
   - `review_note = ghi chú nếu có`

## Endpoint mới cho Inverter

### 1. User gửi request tạo inverter

- `POST /api/inverters/requests/`

Request này có 2 cách trỏ đến project:

- Dùng `project_id` nếu project đã tồn tại
- Dùng `project_request_id` nếu project vẫn đang chờ approve

Khi submit:

1. Kiểm tra chỉ có một trong hai trường `project_id` hoặc `project_request_id`
2. Nếu dùng `project_id`:
   - Kiểm tra project tồn tại
   - Kiểm tra user có quyền với project đó
3. Nếu dùng `project_request_id`:
   - Kiểm tra project request tồn tại
   - Kiểm tra user có quyền với request đó
4. Kiểm tra `serial_number` là bắt buộc
5. Kiểm tra `serial_number` không trùng với inverter thật đã tồn tại
6. Nếu có `replaced_by_id`:
   - Kiểm tra inverter tồn tại
   - Kiểm tra user có quyền
7. Tạo dòng trong `inverter_create_requests`
8. Đặt `status = pending`

### 2. Xem danh sách request inverter

- `GET /api/inverters/requests/`

Hỗ trợ:

- Pagination
- Filter theo query `status`

### 3. Xem chi tiết 1 request inverter

- `GET /api/inverters/requests/{request_id}`

### 4. Admin approve request inverter

- `POST /api/inverters/requests/{request_id}/approve`

Khi approve:

1. Kiểm tra request tồn tại
2. Kiểm tra request đang ở trạng thái `pending`
3. Kiểm tra `serial_number` hợp lệ và chưa trùng inverter thật
4. Xác định project đích:
   - Nếu request có `project_id` thì dùng project đó
   - Nếu request có `project_request_id` thì project request phải đã `approved`
   - Nếu project request chưa approve thì không thể tạo inverter thật
5. Nếu có `replaced_by_id` thì kiểm tra inverter tồn tại
6. Tạo dòng thật trong bảng `inverters`
7. Cập nhật request:
   - `status = approved`
   - `approved_inverter_id = id inverter vừa tạo`
   - `reviewed_by_id = admin id`
   - `reviewed_at = thời điểm approve`
   - `review_note = ghi chú nếu có`

### 5. Admin reject request inverter

- `POST /api/inverters/requests/{request_id}/reject`

Khi reject:

1. Kiểm tra request tồn tại
2. Kiểm tra request đang ở trạng thái `pending`
3. Không tạo inverter thật
4. Cập nhật request:
   - `status = rejected`
   - `reviewed_by_id = admin id`
   - `reviewed_at = thời điểm reject`
   - `review_note = ghi chú nếu có`

## Phân quyền

### Admin

- Xem tất cả project request
- Xem tất cả inverter request
- Approve/reject tất cả request

### Manager

- Xem request của chính manager
- Xem request của user do manager quản lý
- Không được approve/reject

### User thường

- Chỉ xem được request của chính mình
- Chỉ submit request của chính mình
- Không được approve/reject

## Luồng vận hành đề xuất

### Trường hợp 1: Tạo project mới

1. User gửi `POST /api/projects/requests/`
2. Hệ thống lưu request ở trạng thái `pending`
3. Admin vào danh sách request để xem
4. Admin approve
5. Hệ thống tạo dòng thật trong `projects`

### Trường hợp 2: Tạo inverter cho project đã tồn tại

1. User gửi `POST /api/inverters/requests/` kèm `project_id`
2. Hệ thống lưu request `pending`
3. Admin approve
4. Hệ thống tạo dòng thật trong `inverters`

### Trường hợp 3: Tạo project và inverter cùng lúc nhưng phải chờ duyệt

1. User gửi `POST /api/projects/requests/`
2. User gửi `POST /api/inverters/requests/` kèm `project_request_id`
3. Admin approve project request trước
4. Sau khi project đã được tạo thật, admin approve inverter request
5. Hệ thống map `project_request_id` sang `approved_project_id` rồi tạo inverter thật

## Điểm cần lưu ý cho người vận hành

- Endpoint cũ `POST /api/projects/` và `POST /api/inverters/` vẫn tạo trực tiếp như trước.
- Nếu muốn bắt buộc đi theo luồng chờ duyệt, frontend hoặc client phải gọi endpoint `/requests/` mới.
- Inverter request tham chiếu đến `project_request_id` sẽ không approve được nếu project request chưa được approve.
- Nếu request đã `approved` hoặc `rejected` thì không được review lại trong logic hiện tại.

## Gợi ý thứ tự thao tác cho admin

1. Kiểm tra danh sách `project requests` đang `pending`
2. Approve/reject từng project request
3. Kiểm tra danh sách `inverter requests` đang `pending`
4. Ưu tiên approve các inverter request có `project_request_id` sau khi project liên quan đã được approve

## File code liên quan

- `project/models/project_request.py`
- `project/schemas/project_request.py`
- `project/services/project_request_service.py`
- `project/routes/project_router.py`
- `inverter/models/inverter_request.py`
- `inverter/schemas/inverter_request.py`
- `inverter/services/inverter_request_service.py`
- `inverter/routes/inverter_router.py`
