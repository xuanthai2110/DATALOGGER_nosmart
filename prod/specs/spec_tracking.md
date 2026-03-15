# Spec: Tracking Năng Lượng & Giá Trị Cực Đại

## 1. Mục Tiêu

Duy trì trạng thái **trong bộ nhớ (in-memory)** giữa các lần đọc 30 giây để:
- Tính toán `E_monthly` chính xác bằng cách cộng dồn các hiệu số `E_total`.
- Theo dõi giá trị cực đại `Max_I`, `Max_V`, `Max_P` cho từng MPPT và `max_I` cho từng String trong ngày.
- Phát hiện và ghi lỗi **ngược cực** cho MPPT và String.

---

## 2. Thành Phần

- **File**: `services/tracking_service.py`
- **Class**: `TrackingService`
- **Sử dụng bởi**: `PollingService`

---

## 3. Tính Toán E_monthly

### Thuật toán

```
E_monthly[inv] = Σ max(0, E_total[t] - E_total[t-1])
```

### Xử Lý Lần Đầu (Cold Start)

| Tình huống | Hành động |
|---|---|
| Chưa có record trong DB | `E_monthly = 0`, `last_E_total = None` |
| Record từ tháng trước | `E_monthly = 0` (reset), `last_E_total = E_total_cũ` |
| Record từ tháng hiện tại | `E_monthly = E_monthly_cũ`, `last_E_total = E_total_cũ` |
| Lần đọc đầu tiên sau cold start | Chỉ cập nhật `last_E_total`, **không cộng delta** |

> **Lý do**: Tránh trường hợp lần đọc đầu tiên cộng nguyên `E_total` (~hàng nghìn kWh) vào `E_monthly`.

### Bảo Vệ Khỏi Nhảy Số Ảo

Nếu `delta > 100.0 kWh` trong một chu kỳ 30 giây → coi là số ảo, không cộng vào `E_monthly`.

---

## 4. Tracking Giá Trị Cực Đại

### MPPT Max

Mỗi 30 giây, với từng MPPT `i`:

```python
Max_V[inv][i] = max(Max_V[inv][i], current_V)
Max_I[inv][i] = max(Max_I[inv][i], current_I)
Max_P[inv][i] = max(Max_P[inv][i], |current_V × current_I| / 1000)
```

> Công suất `P_mppt` tính bằng giá trị **tuyệt đối** để tránh số âm.

### String Max

```python
max_I[inv][string_id] = max(max_I[inv][string_id], current_I)
```

---

## 5. Reset Hàng Ngày / Hàng Tháng

| Chu kỳ | Giá trị được reset |
|---|---|
| Mỗi ngày (00:00) | `mppt_max`, `string_max` |
| Mỗi tháng (ngày 1) | `e_monthly_map` |

`last_e_total_map` **không bao giờ reset** để delta luôn tính từ giá trị cuối trước đó.

---

## 6. Phát Hiện Ngược Cực (Reverse Polarity)

Sau khi dữ liệu được đọc từ `NormalizationService`, nếu:
- `mppt_{i}_voltage < -1.0` hoặc `mppt_{i}_current < -1.0`
- `string_{i}_current < -1.0`

→ Ghi lỗi vào bảng `inverter_errors`:

| Trường | Giá trị |
|---|---|
| `fault_code` | `9999` (Reverse Polarity) |
| `fault_description` | `"REVERSE POLARITY on MPPT_1"` |
| `repair_instruction` | `"Check DC wiring and connector polarity."` |
| `severity` | `"ERROR"` |

---

## 7. Ghi Lỗi Inverter

Hàm `log_inverter_error(inv, data)` chỉ ghi vào DB khi:
- `fault_code != 0` **VÀ**
- `severity == "ERROR"`

Các trạng thái `STABLE`, `WARNING`, `DERATING` sẽ **không** được ghi vào bảng lỗi để tránh spam.
