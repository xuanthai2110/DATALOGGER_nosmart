# Tích hợp EVN qua Modbus TCP Server — Plan v3

Datalogger đóng vai trò **Modbus TCP Server**. EVN là client kết nối đến để đọc/ghi.

## Thay đổi so với Plan v2

| Hạng mục | v2 | v3 |
|----------|----|----|
| P_out nguồn | SUM(P_ac) inverter | **Từ Meter** (công suất phát lưới) |
| U, I, F, PF | AVG/SUM inverter | **Ưu tiên: SmartLogger → Meter → Inverter đại diện** |
| Meter | Không có | **Thêm Meter subsystem** (model, cache, driver, polling) |
| EVN_connect | Chưa rõ | **True khi EVN client có TCP connection tới server** |
| Logger_connect | Luôn True | **True nếu SmartLogger connected; nếu ko có SmartLogger → luôn True** |
| Telemetry vs Modbus | Độc lập | **Giá trị telemetry phải trùng với giá trị trên thanh ghi Modbus** |

---

## Open Questions

1. **Q Control register map**: Cứ tạo placeholder trong `register_map`, user sẽ sửa sau. OK.
2. **Meter brand/model**: Meter sử dụng hãng/model nào phổ biến? (Để tạo driver mẫu — Acrel, Eastron SDM630, Schneider PM, v.v.)

---

## Proposed Changes

### Component 1: Meter Subsystem (MỚI)

Meter là thiết bị đo lường tại điểm đấu nối lưới, đọc qua Modbus RTU/TCP giống inverter.

#### [NEW] [meter.py](file:///e:/datalogger_project_2102_nosmartlogger/backend/models/meter.py) — Thay thế file hiện tại

```python
@dataclass
class MeterCreate:
    project_id: int
    brand: str              # "Acrel", "Eastron", "Schneider"...
    model: str              # "SDM630", "PM5110"...
    serial_number: str
    slave_id: Optional[int] = None
    comm_id: Optional[int] = None   # Liên kết comm config
    is_active: bool = True

@dataclass
class MeterUpdate:
    project_id: Optional[int] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    slave_id: Optional[int] = None
    comm_id: Optional[int] = None
    is_active: Optional[bool] = None

@dataclass
class MeterResponse:
    id: int
    project_id: int
    brand: str
    model: str
    serial_number: str
    slave_id: Optional[int]
    comm_id: Optional[int]
    is_active: Optional[bool] = True
```

#### [MODIFY] [metadata.py](file:///e:/datalogger_project_2102_nosmartlogger/backend/db_manager/metadata.py)

Thêm bảng `meters` + CRUD methods:

```sql
CREATE TABLE IF NOT EXISTS meters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    brand TEXT, model TEXT, serial_number TEXT,
    slave_id INTEGER, comm_id INTEGER,
    is_active INTEGER DEFAULT 1
);
```

Methods: `upsert_meter()`, `get_meter()`, `get_meters_by_project()`, `delete_meter()`

#### [MODIFY] [cache.py](file:///e:/datalogger_project_2102_nosmartlogger/backend/db_manager/cache.py)

Thêm bảng `meter_cache` trong hirubic_cache.db:

```sql
CREATE TABLE IF NOT EXISTS meter_cache (
    meter_id INTEGER PRIMARY KEY,
    project_id INTEGER,
    -- Công suất
    P_total REAL,           -- Tổng P tác dụng (kW) — đây chính là P_out
    Q_total REAL,           -- Tổng Q phản kháng (kVAr)
    S_total REAL,           -- Tổng S biểu kiến (kVA)
    -- Điện áp pha-trung tính
    V_a REAL, V_b REAL, V_c REAL,
    -- Điện áp dây
    V_ab REAL, V_bc REAL, V_ca REAL,
    -- Dòng điện
    I_a REAL, I_b REAL, I_c REAL,
    -- Hệ số
    PF REAL,                -- Power Factor tổng
    PF_a REAL, PF_b REAL, PF_c REAL,
    F REAL,                 -- Tần số (Hz)
    -- Năng lượng
    E_import REAL,          -- Tổng năng lượng nhập (kWh) — từ lưới vào
    E_export REAL,          -- Tổng năng lượng xuất (kWh) — phát lên lưới
    E_import_daily REAL,    -- Năng lượng nhập trong ngày
    E_export_daily REAL,    -- Năng lượng xuất trong ngày
    -- Metadata
    updated_at TEXT
);
```

Methods: `upsert_meter_cache()`, `get_meter_cache()`, `get_meter_cache_by_project()`

#### [NEW] Meter Driver (placeholder)

File `backend/drivers/meter_base.py` — Base class cho meter driver:

```python
class MeterDriverBase:
    register_map = {}  # User sẽ điền thanh ghi cụ thể theo hãng
    
    def read_all(self) -> dict:
        """Đọc toàn bộ dữ liệu meter, trả về dict chuẩn."""
        # Keys: p_total, q_total, s_total, v_a, v_b, v_c, 
        #        i_a, i_b, i_c, pf, f, e_import, e_export...
```

#### [MODIFY] [polling_service.py](file:///e:/datalogger_project_2102_nosmartlogger/backend/services/polling_service.py)

Thêm `poll_meters(project_id)`: đọc meter qua Modbus → ghi vào `meter_cache`.

---

### Component 2: Configuration

#### [MODIFY] [settings.py](file:///e:/datalogger_project_2102_nosmartlogger/backend/core/settings.py)

```python
EVN_ENABLED = os.getenv("EVN_ENABLED", "False").lower() in ("true", "1", "yes")
EVN_MODBUS_HOST = os.getenv("EVN_MODBUS_HOST", "0.0.0.0")
EVN_MODBUS_PORT = int(os.getenv("EVN_MODBUS_PORT", "502"))
EVN_TELEMETRY_INTERVAL = int(os.getenv("EVN_TELEMETRY_INTERVAL", "300"))
```

#### [MODIFY] [metadata.py](file:///e:/datalogger_project_2102_nosmartlogger/backend/db_manager/metadata.py)

Thêm cột `evn_slave_id INTEGER DEFAULT 0` vào bảng `projects`.
Thêm `get_evn_project_map() -> dict[int, Project]`.

---

### Component 3: Nguồn dữ liệu cho thanh ghi Modbus

**Thứ tự ưu tiên lấy U, I, F, PF:**

```
1. SmartLogger (nếu có) → đọc trực tiếp từ SmartLogger cache
2. Meter (nếu có) → đọc từ meter_cache 
3. Inverter đại diện (fallback):
   - U, F, PF → lấy từ inverter đầu tiên trong cache
   - I → tổng I của tất cả inverter
```

**Bảng Register Mapping (READ — FC04):**

| Addr | Thông số | Nguồn |
|------|----------|-------|
| 1-2 | P_out (kW) | **meter_cache.P_total** (nếu có meter), else SUM(P_ac) inverter |
| 3-4 | Pinv_out (kW) | SUM(P_ac) inverter cache |
| 5-6 | Ainv_D-1 (kWh) | Record cuối ngày hôm qua từ realtime |
| 7-8 | Q_out (kVAr) | **meter_cache.Q_total** (nếu có), else SUM(Q_ac) |
| 9-10 | Ua (V) | Ưu tiên: SmartLogger → Meter → Inv đại diện |
| 11-12 | Ub (V) | Tương tự |
| 13-14 | Uc (V) | Tương tự |
| 15-16 | Ia (A) | Ưu tiên: SmartLogger → Meter → SUM(I_a) inverter |
| 17-18 | Ib (A) | Tương tự |
| 19-20 | Ic (A) | Tương tự |
| 21-22 | F (Hz) | Ưu tiên: SmartLogger → Meter → Inv đại diện |
| 23-24 | PF | Ưu tiên: SmartLogger → Meter → Inv đại diện |
| 25+4*(i-1) | Inv_i P (kW) | P_ac inv i từ cache |
| 27+4*(i-1) | Inv_i E_D-1 | Record cuối ngày hôm qua inv i |

---

### Component 4: ModbusServerService (MỚI)

#### [NEW] [modbus_server_service.py](file:///e:/datalogger_project_2102_nosmartlogger/backend/services/modbus_server_service.py)

- `pymodbus.server.StartAsyncTcpServer` + `ModbusServerContext(slaves={...}, single=False)`
- Mỗi project có `evn_slave_id > 0` → 1 `ModbusSlaveContext`
- **WRITE registers** (FC05 Coils + FC06 Holding):
  - Coil 11: Enable_Set_P, Coil 12: Enable_Set_Q
  - HR 13-14: Set_P_pct, HR 15-16: Set_P_kW, HR 17-18: Set_Q_pct, HR 19-20: Set_Q_kVAr
- `is_evn_controlling_p(slave_id)` / `is_evn_controlling_q(slave_id)`
- `get_connection_status() -> bool`: True khi có TCP connection từ EVN client
- Float: `struct.pack('>f', value)` → 2 registers Big-Endian IEEE754

---

### Component 5: D-1 Query

#### [MODIFY] [realtime.py](file:///e:/datalogger_project_2102_nosmartlogger/backend/db_manager/realtime.py)

```python
def get_yesterday_energy_by_inverter(self, inverter_id: int) -> float:
    """Lấy E_daily từ record CUỐI CÙNG của ngày hôm qua."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    # ... ORDER BY created_at DESC LIMIT 1

def get_yesterday_energy_by_project(self, project_id: int) -> float:
    """Tổng E_daily cuối ngày hôm qua của tất cả inverter trong project."""
```

---

### Component 6: Control Integration

#### [MODIFY] [control_service.py](file:///e:/datalogger_project_2102_nosmartlogger/backend/services/control_service.py)

- `apply_evn_p_control(project_id, mode, value)` → tái sử dụng `_apply_project_scope`
- `apply_evn_q_control(project_id, mode, value)` → gọi driver Q methods
- `reset_evn_p_control()` / `reset_evn_q_control()`

#### [MODIFY] [schedule_worker.py](file:///e:/datalogger_project_2102_nosmartlogger/backend/workers/schedule_worker.py)

Granular priority: EVN giữ P → Cloud P rejected, Cloud Q vẫn OK (và ngược lại).

#### [MODIFY] Drivers (Huawei, Sungrow)

Thêm Q control methods + placeholder `register_map` cho Q. User sẽ sửa thanh ghi sau.

---

### Component 7: EVNTelemetryService (MỚI)

#### [NEW] [evn_telemetry_service.py](file:///e:/datalogger_project_2102_nosmartlogger/backend/services/evn_telemetry_service.py)

> **Quan trọng**: Giá trị trong payload JSON phải **trùng khớp** với giá trị trên các thanh ghi Modbus server. Cả hai đều đọc từ cùng nguồn DB.

```python
def build_evn_payload(self, project_id, slave_id) -> dict:
    # Đọc từ cùng nguồn với ModbusServerService
    return {
        "EVN_connect": modbus_server.get_connection_status(),  # TCP connection active
        "Logger_connect": True,  # Không có SmartLogger hãng → datalogger = logger → True
        "P_out": ...,   # = giá trị tại register 1-2
        "Q_out": ...,   # = giá trị tại register 7-8
        # ... tất cả giá trị khớp với Modbus registers
        "Invs_Data": [[P_inv1, E_yday1], ...],
        "created_at": "ISO8601"
    }
```

- **EVN_connect**: True khi có client TCP đang kết nối tới Modbus server
- **Logger_connect**: True nếu có SmartLogger hãng connected. Nếu không có SmartLogger, datalogger = logger → luôn True
- Interval: 300s (5 phút)

---

### Component 8: EVNWorker + Bootstrap + Docker

#### [NEW] [evn_worker.py](file:///e:/datalogger_project_2102_nosmartlogger/backend/workers/evn_worker.py)

Thread quản lý EVN lifecycle (start server, update registers, detect WRITE, send telemetry).

#### [MODIFY] [run_polling.py](file:///e:/datalogger_project_2102_nosmartlogger/backend/scripts/run_polling.py)

Bootstrap EVN khi `EVN_ENABLED=True`.

#### [MODIFY] [docker-compose.yml](file:///e:/datalogger_project_2102_nosmartlogger/docker-compose.yml)

Expose port 502.

---

## Tóm tắt Files

| File | Loại | Mô tả |
|------|------|-------|
| `backend/models/meter.py` | **REPLACE** | Model Meter (Create/Update/Response) |
| `backend/drivers/meter_base.py` | **NEW** | Base driver cho meter |
| `backend/services/modbus_server_service.py` | **NEW** | Modbus TCP Server |
| `backend/services/evn_telemetry_service.py` | **NEW** | EVN telemetry |
| `backend/workers/evn_worker.py` | **NEW** | EVN worker thread |
| `backend/db_manager/metadata.py` | MODIFY | Bảng meters + cột evn_slave_id |
| `backend/db_manager/cache.py` | MODIFY | Bảng meter_cache |
| `backend/db_manager/realtime.py` | MODIFY | D-1 query methods |
| `backend/services/polling_service.py` | MODIFY | Thêm poll_meters() |
| `backend/services/control_service.py` | MODIFY | EVN P/Q control |
| `backend/workers/schedule_worker.py` | MODIFY | Granular EVN priority |
| `backend/core/settings.py` | MODIFY | Biến EVN |
| `.env` | MODIFY | Section EVN |
| `docker-compose.yml` | MODIFY | Port 502 |
| Drivers (Huawei, Sungrow) | MODIFY | Q control + register_map |

---

## Verification Plan

### Unit Tests
1. Meter cache CRUD
2. Float IEEE754 ↔ 2 registers
3. Multi-slave register mapping
4. D-1 query (record cuối ngày hôm qua)
5. Granular priority (P/Q độc lập)
6. Telemetry payload = Modbus register values

### Integration Test
1. `EVN_ENABLED=True` → pymodbus client đọc FC04 → verify data khớp cache
2. Ghi FC05 Enable_Set_P + FC06 Set_P_pct → verify inverter nhận lệnh
3. Cloud P schedule khi EVN P active → FAILED; Cloud Q → OK
