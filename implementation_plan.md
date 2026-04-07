# Phân tích Kiến trúc & Kế hoạch Tối ưu Codebase

---

## PHẦN 1 — TÔI HIỂU HỆ THỐNG NHƯ SAU

### Hệ thống chạy bằng 3 tiến trình độc lập (3 Docker container)

**Process 1 — WEB** (`backend/app.py`)
FastAPI REST API + WebSocket. Phục vụ: Auth, Config UI, Monitoring, Schedule API.

**Process 2 — POLLING** (`run_polling.py`) — Lõi chính
Khởi động một bộ 6 thread song song:

| Worker | Chu kỳ | Nhiệm vụ |
|--------|--------|----------|
| `PollingWorker` | 10s | Đọc Modbus từ Inverter → ghi CacheDB (RAM) |
| `LogicWorker` | 1s | Tính Energy, Max V/I/P, phát hiện lỗi từ RAM cache |
| `BuildTeleWorker` | Event / 300s | Đóng gói telemetry → ghi vào SQLite outbox |
| `PersistenceWorker` | 300s | Snapshot RAM → ghi ra SQLite `RealtimeDB` |
| `ScheduleWorker` | 1s | Thực thi lịch điều khiển công suất |
| `MqttSubscriber` | Realtime | Nhận lệnh từ cloud MQTT → lưu lịch điều khiển |

**Process 3 — UPLOADER** (`run_uploader.py`)
Mỗi 10s: đọc SQLite outbox → HTTP POST lên cloud API → xóa record đã gửi.

---

### Luồng dữ liệu tổng

```
Modbus Inverter
  → PollingService → CacheDB (RAM)
       ↓ (1s, LogicWorker)
  EnergyService, MaxTrackingService, FaultService → cập nhật lại RAM
       ↓ (event trigger khi có thay đổi trạng thái)
  BuildTeleWorker → TelemetryService → RealtimeDB.outbox (SQLite)
       ↓ (300s, PersistenceWorker)
  RealtimeDB (inverter_ac, mppt, string, project_realtime)
       ↓ (10s, Process riêng)
  UploaderService → Cloud API POST /api/telemetry/project/{server_id}
```

### Luồng Điều khiển Công suất

```
Cloud MQTT → MqttSubscriber.on_message()
  → ScheduleService.sync_schedule_from_server()
      → HTTP GET cloud API để lấy chi tiết lịch
      → Lưu vào RealtimeDB (bảng control_schedules)

ScheduleWorker (1s) → ScheduleService.get_all()
  → So sánh thời gian: start_at <= now <= end_at
  → ControlService.apply(schedule)
      → Nếu scope=PROJECT: SmartLoggerHuawei.control_P / control_percent()
      → Nếu scope=INVERTER: Driver.control_P / control_percent()
  → Khi hết giờ: ControlService.reset() → set 100%
```

---

## PHẦN 2 — CÁC VẤN ĐỀ TÌM THẤY & ĐỀ XUẤT TỐI ƯU

### #1 · ƯU TIÊN CAO — Dead code: 3 file worker trong services/

**Vấn đề:** Thư mục `backend/services/` chứa 3 file là bản sao lỗi thời không còn được gọi:
- `services/logic_worker.py` — interface cũ, không tương thích workers/
- `services/persistence_worker.py` — thiếu các logic mới nhất
- `services/uploader_worker.py` — không dùng UploaderService mới

Xác nhận: Grep toàn dự án không có file nào import các file này.

**Đề xuất:** Xóa cả 3 file.

---

### #2 · ƯU TIÊN CAO — schedule_api.py khởi tạo DB ở module-level

**Vấn đề:** 2 dòng ở đầu `backend/api/schedule_api.py`:
```python
db = RealtimeDB(settings.REALTIME_DB)
schedule_service = ScheduleService(db)
```
Chạy ngay lúc FastAPI **import module** (khi app khởi động), không phải khi có request. Đây là anti-pattern của FastAPI — nếu DB lỗi lúc startup, toàn bộ app crash.

**Đề xuất:** Chuyển sang Depends() như các API khác.

---

### #3 · TRUNG — parse_iso() định nghĩa trong vòng lặp for

**Vấn đề:** `backend/workers/schedule_worker.py` định nghĩa hàm `parse_iso()` bên trong `for s in schedules:`. Hàm này được tạo lại mỗi 1s × số lịch đang chạy.

**Đề xuất:** Chuyển ra thành `@staticmethod` ở cấp class.

---

### #4 · TRUNG — BuildTeleWorker gọi SQL thô, vi phạm phân lớp

**Vấn đề:** `_enforce_limit()` trong `build_tele_worker.py` gọi:
```python
with self.realtime_db._connect() as conn:
    count = conn.execute("SELECT COUNT(*) FROM uploader_outbox")...
```
Tầng Worker không nên viết SQL trực tiếp — logic này cần nằm trong DB Manager.

**Đề xuất:** Thêm method `RealtimeDB.trim_outbox(max_rows: int)`, gọi từ Worker.

---

### #5 · TRUNG — FaultService(None, None) anti-pattern

**Vấn đề:** `PollingService.__init__()`:
```python
self.fault_service = FaultService(None, None)
```
Tạo instance với cả 2 DB là `None`. Chỉ dùng 2 hàm stateless `get_inverter_status_payload()` và `get_state_snapshot()` — hoàn toàn không cần DB. Nếu vô tình gọi `self.metadata_db.get_inverter_by_id()`, crash ngay.

**Đề xuất:** Cho phép DB params là Optional với default None + guard trước khi dùng.

---

### #6 · THẤP — import json bên trong hàm

**Vấn đề:** `polling_service.py` line 126: `import json` nằm trong thân hàm `poll_all_inverters()`, chạy mỗi 10s.

**Đề xuất:** Chuyển lên đầu file.

---

### #7 · THẤP — import logging trùng 2 lần

**Vấn đề:** `schedule_worker.py` dòng 2 và 3 đều là `import logging`.

**Đề xuất:** Xóa 1 dòng thừa.

---

### #8 · THẤP — DEBUG print sót trong production

**Vấn đề:** `run_polling.py` line 16: `print(f"DEBUG - sys.path[0]: {sys.path[0]}")`

**Đề xuất:** Xóa hoặc đổi thành `logger.debug(...)`.

---

## Tổng hợp

| # | Vấn đề | Loại | Rủi ro | Ưu tiên |
|---|--------|------|--------|---------|
| 1 | 3 file dead code | DELETE | Không | CAO |
| 2 | schedule_api global DB | MODIFY | Thấp | CAO |
| 3 | parse_iso trong loop | MODIFY nhỏ | Không | TRUNG |
| 4 | raw SQL trong Worker | MODIFY + thêm method | Thấp | TRUNG |
| 5 | FaultService(None, None) | MODIFY | Thấp | TRUNG |
| 6 | import json trong hàm | MODIFY nhỏ | Không | THẤP |
| 7 | import logging trùng | MODIFY nhỏ | Không | THẤP |
| 8 | DEBUG print sót | MODIFY nhỏ | Không | THẤP |

> Tất cả thay đổi KHÔNG đụng business logic, register map, control algorithm, hay luồng dữ liệu chính.
