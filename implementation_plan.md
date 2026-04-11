# Kế hoạch triển khai: Điều khiển Project khi không có SmartLogger

## 1) Mục tiêu

Triển khai cơ chế fallback cho điều khiển `scope=PROJECT` khi không có SmartLogger.
Fallback phải phân bổ setpoint cấp dự án xuống từng inverter đang hoạt động theo đúng thuật toán trong `prod/specs/spec_control_nosmartlogger.md`.

## 2) Khoảng trống hiện tại

- `ControlService.apply()` hiện tại đang route `scope=PROJECT` theo nhánh SmartLogger.
- Nếu không có SmartLogger thì điều khiển cấp project bị fail, thay vì áp setpoint từng inverter.
- Trạng thái này chưa đáp ứng kịch bản không dùng SmartLogger.

## 3) Hành vi mục tiêu

Khi nhận một schedule `PROJECT`:

1. Thử nhánh SmartLogger trước (giữ hành vi hiện có).
2. Nếu nhánh SmartLogger không khả dụng hoặc không resolve được controller:
   - Tạo `project_setpoints` theo từng inverter active.
   - Ghi setpoint xuống từng inverter qua các method điều khiển đã có.
3. Giữ nguyên vòng đời trạng thái schedule:
   - `SCHEDULED -> RUNNING -> COMPLETED`
   - `FAILED` nếu apply/reset không thực hiện an toàn được.

## 4) Thiết kế thuật toán (không SmartLogger)

### 4.1 Input

- `mode`: `MAXP` hoặc `LIMIT_PERCENT`
- `limit_watts` cho `MAXP`
- `limit_percent` cho `LIMIT_PERCENT`
- `active_inverters` của project mục tiêu

### 4.2 Nguồn công suất rated

Ưu tiên lấy công suất AC rated theo thứ tự:

1. `inv.rate_ac_kw`
2. `inv.capacity_kw` (fallback nếu thiếu `rate_ac_kw`)
3. mặc định `0.0`

### 4.3 Mode MAXP

- `total_kw = limit_watts / 1000.0`
- `rates = [rated_kw(inv)]`
- Nếu `sum(rates) > 0`: chia theo tỷ lệ rated.
- Nếu không: chia đều cho các inverter active.
- Hiệu chỉnh cuối: cân lại phần dư do làm tròn ở inverter cuối để tổng setpoint khớp `total_kw` trong ngưỡng sai số.

### 4.4 Mode LIMIT_PERCENT

- Chặn `pct` trong `[0, 100]`
- Mỗi inverter: `setpoint_kw = rated_kw * pct / 100`
- Nếu rated thiếu/0 thì setpoint inverter đó = 0 (đồng thời ghi warning log).

### 4.5 Quy tắc an toàn

- Bỏ qua inverter không active.
- Từ chối apply nếu không có inverter active.
- Chặn setpoint âm.
- Ghi log đầy đủ thông tin phân bổ để audit/debug.

## 5) Thay đổi mã nguồn

## 5.1 `backend/services/control_service.py`

Thêm/chỉnh các method:

- `_get_active_project_inverters(project_item) -> list`
- `_get_inverter_rated_kw(inv) -> float`
- `_build_project_setpoints(schedule, inverters) -> dict[inverter_id, kw]`
- `_apply_project_scope_without_smartlogger(project_item, schedule) -> bool`
- `_reset_project_scope_without_smartlogger(project_item) -> bool` (set 100% hoặc gỡ limit tùy khả năng driver)

Cập nhật luồng xử lý:

- Trong `apply()` cho `scope=PROJECT`:
  - Thử nhánh SmartLogger hiện tại.
  - Nếu không khả dụng thì chuyển qua fallback không SmartLogger.
- Trong `reset()` cho `scope=PROJECT`:
  - Dùng cùng pattern fallback.

Tận dụng cơ chế kiểm tra khả năng driver từng inverter đã có trong `_apply_inverters()`:

- Method MAXP: `control_P`, `set_power_kw`, `write_power_limit_kw`, `set_power_w`
- Method PERCENT: `control_percent`, `set_power_percent`, `write_power_limit_percent`

## 5.2 Logging

Thêm log có cấu trúc:

- schedule id, project id, mode
- inverter id, serial, rated_kw, setpoint_kw
- tổng yêu cầu vs tổng thực áp
- lý do fallback (ví dụ: không resolve được SmartLogger)

## 5.3 Không cần đổi schema DB

Các field trong `control_schedules` hiện tại đã đủ.
Không cần migration cho tính năng này.

## 6) Kế hoạch kiểm thử

## 6.1 Unit test (mới)

Tạo: `backend/tests/test_control_project_nosmartlogger.py`

Các case:

1. `MAXP` chia tỷ lệ với rated power hỗn hợp.
2. `MAXP` chia đều khi toàn bộ rated thiếu/0.
3. `LIMIT_PERCENT` chia theo phần trăm.
4. Chặn phần trăm >100 và <0.
5. Không có inverter active -> apply fail.
6. Không có SmartLogger -> fallback path được gọi.
7. Reset theo fallback -> toàn bộ inverter về 100%.

Dùng fake driver stubs để assert chính xác command và giá trị được gọi.

## 6.2 Kiểm thử tích hợp

1. Khởi động hệ thống với project có inverter nhưng không có SmartLogger.
2. Publish MQTT `schedule_created` với `scope=PROJECT`.
3. Xác nhận:
   - Schedule local được insert/update.
   - `ScheduleWorker` chạy apply đúng thời điểm start.
   - Lệnh điều khiển từng inverter được gửi đúng setpoint.
   - Trạng thái được patch về server.
4. Chờ đến `end_at`, xác nhận reset và trạng thái `COMPLETED`.

## 7) Kế hoạch rollout

Giai đoạn 1:
- Triển khai fallback với log chi tiết.
- Bật trong môi trường test.

Giai đoạn 2:
- Shadow validation (so sánh setpoint kỳ vọng với log setpoint thực tế).

Giai đoạn 3:
- Deploy production.
- Theo dõi 3-5 lần chạy schedule đầu tiên ở mỗi site.

## 8) Rủi ro và giảm thiểu

- Thiếu dữ liệu rated power:
  - Giảm thiểu: fallback chia đều + warning.
- Lệch khả năng điều khiển giữa các driver:
  - Giảm thiểu: tái sử dụng pattern detect capability và guard theo driver.
- Sai số làm tròn:
  - Giảm thiểu: hiệu chỉnh inverter cuối + kiểm tra tolerance.

## 9) Tiêu chí nghiệm thu

Tính năng được chấp nhận khi:

1. Schedule `PROJECT` chạy được khi không có SmartLogger.
2. Phân bổ tuân thủ spec cho cả `MAXP` và `LIMIT_PERCENT`.
3. Vòng đời schedule và đồng bộ trạng thái vẫn giữ nguyên.
4. Không gây regression cho project đang dùng SmartLogger.

