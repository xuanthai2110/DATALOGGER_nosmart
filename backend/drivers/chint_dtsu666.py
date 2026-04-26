"""
backend/drivers/chint_dtsu666.py — Driver cho Meter Chint DTSU666.
Hỗ trợ đọc dữ liệu tức thời và năng lượng tích lũy qua Modbus RTU/TCP.
"""

import logging
from typing import Dict, Any, Optional
from backend.drivers.meter_base import MeterDriverBase

logger = logging.getLogger(__name__)


class MeterChintdtsu666(MeterDriverBase):
    """
    Driver cho Chint DTSU666 (3 pha).
    Sử dụng Function Code 03 (Holding Registers).
    Xử lý đặc biệt cho Năng lượng phản kháng (tính từ 4 góc phần tư).
    """

    # DTSU666 sử dụng FC03 cho các vùng địa chỉ này
    read_function = "holding"

    # Map các thanh ghi theo Manual (Hex -> Dec)
    register_map: Dict[str, Dict[str, Any]] = {
        # --- Điện áp (V) ---
        "v_a":          {"address": 8192, "count": 2, "type": "float32", "unit": "V"},
        "v_b":          {"address": 8194, "count": 2, "type": "float32", "unit": "V"},
        "v_c":          {"address": 8196, "count": 2, "type": "float32", "unit": "V"},
        "v_ab":         {"address": 8198, "count": 2, "type": "float32", "unit": "V"},
        "v_bc":         {"address": 8200, "count": 2, "type": "float32", "unit": "V"},
        "v_ca":         {"address": 8202, "count": 2, "type": "float32", "unit": "V"},

        # --- Dòng điện (I) ---
        "i_a":          {"address": 8204, "count": 2, "type": "float32", "unit": "A"},
        "i_b":          {"address": 8206, "count": 2, "type": "float32", "unit": "A"},
        "i_c":          {"address": 8208, "count": 2, "type": "float32", "unit": "A"},

        # --- Công suất tác dụng (P) ---
        "p_total":      {"address": 8210, "count": 2, "type": "float32", "unit": "kW"},
        "p_a":          {"address": 8212, "count": 2, "type": "float32", "unit": "kW"},
        "p_b":          {"address": 8214, "count": 2, "type": "float32", "unit": "kW"},
        "p_c":          {"address": 8216, "count": 2, "type": "float32", "unit": "kW"},

        # --- Công suất phản kháng (Q) ---
        "q_total":      {"address": 8218, "count": 2, "type": "float32", "unit": "kVAr"},
        "q_a":          {"address": 8220, "count": 2, "type": "float32", "unit": "kVAr"},
        "q_b":          {"address": 8222, "count": 2, "type": "float32", "unit": "kVAr"},
        "q_c":          {"address": 8224, "count": 2, "type": "float32", "unit": "kVAr"},

        # --- Công suất biểu kiến (S) ---
        "s_total":      {"address": 8226, "count": 2, "type": "float32", "unit": "kVA"},
        "s_a":          {"address": 8228, "count": 2, "type": "float32", "unit": "kVA"},
        "s_b":          {"address": 8230, "count": 2, "type": "float32", "unit": "kVA"},
        "s_c":          {"address": 8232, "count": 2, "type": "float32", "unit": "kVA"},

        # --- Hệ số công suất (PF) & Tần số (F) ---
        "pf":           {"address": 8234, "count": 2, "type": "float32", "unit": ""},
        "pf_a":         {"address": 8236, "count": 2, "type": "float32", "unit": ""},
        "pf_b":         {"address": 8238, "count": 2, "type": "float32", "unit": ""},
        "pf_c":         {"address": 8240, "count": 2, "type": "float32", "unit": ""},
        "f":            {"address": 8242, "count": 2, "type": "float32", "unit": "Hz"},

        # --- Năng lượng (Energy) ---
        "e_pt_import":  {"address": 16414, "count": 2, "type": "float32", "unit": "kWh"},
        "e_pt_export":  {"address": 16424, "count": 2, "type": "float32", "unit": "kWh"},
        
        # 4 Góc phần tư cho năng lượng phản kháng
        "q1":           {"address": 16434, "count": 2, "type": "float32", "unit": "kVArh"},
        "q2":           {"address": 16436, "count": 2, "type": "float32", "unit": "kVArh"},
        "q3":           {"address": 16438, "count": 2, "type": "float32", "unit": "kVArh"},
        "q4":           {"address": 16440, "count": 2, "type": "float32", "unit": "kVArh"},
    }

    def read_all(self) -> Optional[Dict[str, float]]:
        """
        Đọc dữ liệu và thực hiện tính toán bổ sung.
        """
        # 1. Sử dụng logic đọc và tính toán ảo của MeterDriverBase
        data = super().read_all()
        if not data:
            return None

        # 2. Quy đổi Năng lượng phản kháng từ 4 góc phần tư
        # Import = Q1 (Cảm kháng thu) + Q4 (Dung kháng thu)
        data["e_qt_import"] = round(data.get("q1", 0.0) + data.get("q4", 0.0), 4)
        
        # Export = Q2 (Dung kháng phát) + Q3 (Cảm kháng phát)
        data["e_qt_export"] = round(data.get("q2", 0.0) + data.get("q3", 0.0), 4)

        return data
