# Spec: Chuẩn Hoá Dữ Liệu (Normalization)

## 1. Mục Tiêu

Đảm bảo tất cả dữ liệu đọc từ inverter đều được làm sạch, hợp lệ, và nhất quán **trước khi lưu vào database** hoặc tính toán.

---

## 2. Thành Phần

- **File**: `services/normalization_service.py`
- **Class**: `NormalizationService`
- **Sử dụng bởi**: `PollingService.save_to_database()`

---

## 3. Quy Trình Xử Lý Từng Trường

```
raw_value
    │
    ├── None / str / bool → giữ nguyên
    │
    ├── Không convert được → float → None + log WARNING
    │
    ├── Là MPPT/String value?
    │       ├── -1.0 ≤ value < 0.0 → 0.0 (lọc nhiễu)
    │       └── value < -1.0 → giữ nguyên (TrackingService xử lý ngược cực)
    │
    ├── Nằm ngoài VALID_RANGE[key]? → None + log WARNING
    │
    └── Làm tròn theo ROUND_DIGITS[key] (mặc định 2 chữ số)
```

---

## 4. Khoảng Giá Trị Hợp Lệ (VALID_RANGE)

### Phía AC
| Tham số | Min | Max | Đơn vị |
|---|---|---|---|
| `v_a`, `v_b`, `v_c` | 0 | 440 | V |
| `i_a`, `i_b`, `i_c` | -1000 | 1000 | A |
| `p_inv_w` | -200 | 200 | kW |
| `q_inv_var` | -200 | 200 | kVAr |
| `pf` | -1.0 | 1.0 | — |
| `grid_hz` | 0 | 70 | Hz |

### Phía DC
| Tham số | Min | Max | Đơn vị |
|---|---|---|---|
| `p_dc_w` | 0 | 400 | kW |
| `mppt_{i}_voltage` | -1000 | 1500 | V |
| `mppt_{i}_current` | -100 | 100 | A |
| `string_{i}_current` | -100 | 100 | A |

### Thống kê / Năng lượng
| Tham số | Min | Max | Đơn vị |
|---|---|---|---|
| `temp_c` | -40 | 100 | °C |
| `ir` | 0 | 10000 | kΩ |
| `e_daily` | 0 | 10000 | kWh |
| `e_monthly` | 0 | 1,000,000 | kWh |
| `e_total` | 0 | 1,000,000,000 | kWh |

---

## 5. Xử Lý Giá Trị Âm DC (MPPT / String)

| Khoảng | Hành động | Lý do |
|---|---|---|
| `-1.0 ≤ value < 0.0` | → `0.0` | Nhiễu tín hiệu, giá trị rác |
| `value < -1.0` | Giữ nguyên | Dấu hiệu **cắm ngược cực** — để TrackingService phân loại lỗi |
| `value ≥ 0.0` | Bình thường | Xử lý theo VALID_RANGE |

---

## 6. Làm Tròn (Rounding)

Tất cả giá trị số được làm tròn **2 chữ số thập phân** sau khi vượt qua bước validation. Bảng `ROUND_DIGITS` cho phép cấu hình độ chính xác theo từng trường nếu cần.

---

## 7. Chế Độ Strict

Khởi tạo với `NormalizationService(strict=True)` sẽ **raise `ValueError`** thay vì trả về `None` khi gặp giá trị ngoài khoảng. Dùng cho unit test hoặc validation ngoại tuyến.

---

## 8. Ví Dụ

```python
svc = NormalizationService()
raw = {
    "mppt_1_current": -0.04,  # Nhiễu → 0.0
    "mppt_2_current": -5.2,   # Ngược cực → giữ nguyên -5.2
    "v_a": 999.9,             # Ngoài range → None
    "e_daily": 123.456,       # Hợp lệ → 123.46
}
clean = svc.normalize(raw)
# {"mppt_1_current": 0.0, "mppt_2_current": -5.2, "v_a": None, "e_daily": 123.46}
```
