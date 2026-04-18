I. CƠ SỞ DỮ LIỆU (DATABASE)
Hệ thống sử dụng hai tệp cơ sở dữ liệu SQLite chính:

metadata.db: Lưu trữ cấu hình tĩnh và thông tin định danh.
Bảng projects: Lưu tên dự án, mã công tơ (elec_meter_no), tọa độ, công suất, và trạng thái đồng bộ (sync_status, server_id, server_request_id).
Bảng inverters: Lưu số Serial (serial_number), Slave ID, cấu hình phần cứng, và liên kết với dự án (project_id).
realtime.db: Lưu trữ dữ liệu động và hàng đợi gửi tin.
Bảng outbox: Hàng đợi chứa các gói telemetry đang chờ uploader đẩy lên server.
Các bảng dữ liệu lịch sử (project_realtime, inverter_realtime).
II. LOGIC CỦA PROJECT (DỰ ÁN)
1. Create (Tạo mới)
Local Action: Gọi POST /api/projects.
DB Call: MetadataDB.post_project. Chèn bản ghi mới vào bảng projects.
Trạng thái: sync_status mặc định là pending, server_id = 0, server_request_id = 0.
Sync Action (Manual nhấn nút Sync): Gọi POST /api/sync/project/{id}.
Cloud API: POST /api/projects/requests/.
Payload: {elec_meter_no, name, location, lat, lon, capacity_kwp, ac_capacity_kw, inverter_count}.
Kết quả: Nhận về request_id, lưu vào cột server_request_id ở Local DB.
2. Update (Cập nhật)
Local Action: Gọi PATCH /api/projects/{id}.
DB Call: MetadataDB.patch_project. Cập nhật các trường thay đổi vào bảng projects.
Sync Action (Manual nhấn nút Sync): Gọi POST /api/sync/project/{id}. Hệ thống sẽ kiểm tra trạng thái:
Trường hợp pending: Gọi PATCH /api/projects/requests/{server_request_id} để sửa yêu cầu đang chờ duyệt.
Trường hợp approved: Gọi POST /api/projects/requests/update/{server_id}.
Smart Diff: Hệ thống so sánh dữ liệu Local với dữ liệu hiện tại trên Cloud (qua GET /api/projects/{server_id}). Chỉ những trường thực sự thay đổi mới được gửi đi.
3. Delete (Xóa)
Local Action: Gọi DELETE /api/projects/{id}.
Sync Action: Tự động gọi SetupService.request_delete_project_sync.
Cloud API: POST /api/projects/requests/delete/{server_id}.
DB Cleanup:
Xóa toàn bộ Inverters liên quan trong bảng inverters.
Xóa bản ghi trong bảng projects.
Xóa sạch dữ liệu telemetry liên quan trong realtime.db.
III. LOGIC CỦA INVERTER (BIẾN TẦN)
1. Create (Tạo mới)
Local Action: Thường từ kết quả Scan hoặc gọi POST /api/inverters.
DB Call: MetadataDB.upsert_inverter. Lưu thông tin vào bảng inverters, liên kết với project_id.
Sync Action: Gọi POST /api/sync/inverter/{id}.
Cloud API: POST /api/inverters/requests/.
Payload quan trọng: Phải gửi kèm project_id (Server ID) hoặc project_request_id (Server Request ID của dự án) để server biết Inverter này thuộc về dự án nào.
2. Update (Cập nhật)
Local Action: Gọi PATCH /api/inverters/{id}.
DB Call: MetadataDB.patch_inverter.
Sync Action: Gọi POST /api/sync/inverter/{id}.
Nếu pending: PATCH /api/inverters/requests/{server_request_id}.
Nếu approved: POST /api/inverters/requests/update/{server_id}.
3. Delete (Xóa)
Local Action: Gọi DELETE /api/inverters/{id}.
Sync Action: Gọi SetupService.request_delete_inverter_sync.
Cloud API: POST /api/inverters/requests/delete/{server_id}.
DB Cleanup: Xóa bản ghi trong bảng inverters và xóa dữ liệu cache/telemetry của inverter đó trong realtime.db.
IV. BẢNG TỔNG HỢP API CLOUD
Chức năng	Phương thức	Endpoint Cloud
Project (Create)	POST	/api/projects/requests/
Project (Sửa Pending)	PATCH	/api/projects/requests/{req_id}
Project (Sửa Approved)	POST	/api/projects/requests/update/{server_id}
Project (Xóa)	POST	/api/projects/requests/delete/{server_id}
Inverter (Create)	POST	/api/inverters/requests/
Inverter (Sửa Pending)	PATCH	/api/inverters/requests/{req_id}
Inverter (Sửa Approved)	POST	/api/inverters/requests/update/{server_id}
Inverter (Xóa)	POST	/api/inverters/requests/delete/{server_id}
Lưu ý về Xác thực (Auth): Mọi API Cloud đều yêu cầu Header Authorization: Bearer {token}. Token này được tự động làm mới nếu hết hạn thông qua AuthService.