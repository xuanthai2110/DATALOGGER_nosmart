# services/normalization_service.py
"""
NormalizationService - Chuẩn hoá và kiểm tra dữ liệu đọc từ inverter.

Nhiệm vụ:
  1. Chuẩn hoá: Làm tròn, đổi đơn vị (W -> kW), gán None cho
     các giá trị không hợp lệ.
  2. Kiểm tra khoảng hợp lệ (validation range): Các giá trị nằm
     ngoài khoảng vật lý cho phép sẽ bị thay thế bằng None và
     ghi log cảnh báo.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# =========================================================
# ====== KHOẢNG GIÁ TRỊ HỢP LỆ CHO TỪNG THAM SỐ =========
# =========================================================
# Đơn vị: giống với đơn vị sau khi scale từ driver
#   V       -> V
#   I       -> A
#   P_ac    -> kW  (driver đã scale W -> kW)
#   Q_ac    -> kvar
#   PF      -> -1.0 .. 1.0
#   Hz      -> Hz
#   Temp_C  -> °C
#   IR      -> kΩ
#   E_daily -> kWh
#   E_total -> kWh
#   mppt_voltage -> V
#   mppt_current -> A
#   string_current -> A
#   p_dc_w  -> kW

VALID_RANGE: dict[str, tuple[float, float]] = {
    # AC
    "v_a":        (0.0,    440.0),
    "v_b":        (0.0,    440.0),
    "v_c":        (0.0,    440.0),
    "i_a":        (-1000.0, 1000.0),
    "i_b":        (-1000.0, 1000.0),
    "i_c":        (-1000.0, 1000.0),
    "p_inv_w":    (-200000.0,  200000.0),    # W
    "q_inv_var":  (-200000.0,  200000.0),    # var
    "pf":         (-1.0,    1.0),
    "grid_hz":    (0.0,    70.0),

    # DC
    "p_dc_w":     (0.0,    400000.0),     # W
    **{f"mppt_{i}_voltage": (-1000.0, 1500.0) for i in range(1, 11)},
    **{f"mppt_{i}_current": (-100.0, 100.0)  for i in range(1, 11)},
    **{f"string_{i}_current": (-100.0, 100.0) for i in range(1, 21)},

    # Stat
    "temp_c":   (-40.0,  100.0),
    "ir":       (0.0,    10000.0),  # kΩ
    "e_daily":  (0.0,    10000.0),  # kWh
    "e_monthly": (0.0,   1000000.0), # kWh
    "e_total":  (0.0,    1e9),      # kWh
}

# =========================================================
# ====== ĐỊNH NGHĨA LÀM TRÒN ==============================
# =========================================================
ROUND_DIGITS: dict[str, int] = {
    "v_a": 2, "v_b": 2, "v_c": 2,
    "i_a": 2, "i_b": 2, "i_c": 2,
    "p_inv_w": 2, "q_inv_var": 2, "pf": 2,
    "grid_hz": 2, "p_dc_w": 2,
    "temp_c": 2, "e_daily": 2, "e_monthly": 2, "e_total": 2,
    **{f"mppt_{i}_voltage": 2 for i in range(1, 11)},
    **{f"mppt_{i}_current": 2 for i in range(1, 11)},
    **{f"string_{i}_current": 2 for i in range(1, 21)},
}

DEFAULT_ROUND = 2  # Mặc định làm tròn 2 chữ số thập phân cho các tham số chưa khai báo


class NormalizationService:
    """
    Chuẩn hoá và kiểm tra dữ liệu trả về từ driver.

    Sử dụng:
        svc = NormalizationService()
        clean = svc.normalize(raw_data)
    """

    def __init__(self, strict: bool = False):
        """
        strict=True  -> raise ValueError nếu gặp giá trị ngoài khoảng.
        strict=False -> gán None và log cảnh báo (mặc định).
        """
        self.strict = strict

    # ----------------------------------------------------------
    def normalize(self, data: dict) -> dict:
        """
        Chuẩn hoá toàn bộ dict dữ liệu từ driver.
        Trả về dict mới đã được làm sạch.
        """
        result = {}
        for key, raw_value in data.items():
            result[key] = self._process_field(key, raw_value)
        return result

    # ----------------------------------------------------------
    def _process_field(self, key: str, value: Any) -> Any:
        """Xử lý một trường: kiểm tra None, kiểu số, khoảng hợp lệ, làm tròn."""

        # 1. Giữ nguyên các trường không phải số (string, bool, None)
        if value is None:
            return None
        if isinstance(value, (str, bool)):
            return value

        # 2. Ép về float
        try:
            value = float(value)
        except (TypeError, ValueError):
            logger.warning(f"[Norm] {key}: cannot convert '{value}' to float -> None")
            return None

        # 3. Xử lý noise và reverse polarity cho DC side (MPPT, String)
        if "mppt_" in key or "string_" in key:
            if -1.0 <= value < 0.0:
                # Giá trị rác, cho về 0
                return 0.0
            # Nếu value < -1.0, chúng ta giữ nguyên giá trị âm để TrackingService phát hiện reverse polarity

        # 4. Kiểm tra khoảng hợp lệ
        if key in VALID_RANGE:
            lo, hi = VALID_RANGE[key]
            if not (lo <= value <= hi):
                msg = f"[Norm] {key}={value} out of range [{lo}, {hi}]"
                if self.strict:
                    raise ValueError(msg)
                logger.warning(msg + " -> None")
                return None

        # 5. Làm tròn 2 chữ số thập phân (dùng bảng ROUND_DIGITS nếu có, fallback DEFAULT_ROUND)
        digits = ROUND_DIGITS.get(key, DEFAULT_ROUND)
        value = round(value, digits)

        return value

    # ----------------------------------------------------------
    def validate_snapshot(self, data: dict) -> dict[str, list[str]]:
        """
        Kiểm tra toàn bộ snapshot và trả về dict các cảnh báo theo từng key.
        Dùng để log / debug mà không thay đổi dữ liệu gốc.

        Trả về: {"v_a": ["out of range: 500.0 > 440.0"], ...}
        """
        warnings: dict[str, list[str]] = {}
        for key, value in data.items():
            if value is None or not isinstance(value, (int, float)):
                continue
            if key in VALID_RANGE:
                lo, hi = VALID_RANGE[key]
                if not (lo <= float(value) <= hi):
                    warnings.setdefault(key, []).append(
                        f"out of range: {value} not in [{lo}, {hi}]"
                    )
        return warnings
