# tests/test_telemetry.py
"""
Bài test one-shot cho toàn bộ luồng telemetry.

LUỒNG CHÍNH:
  Bước 1 - Đọc dữ liệu    : Poll inverter qua Modbus → raw_data
  Bước 2 - Xử lý          : Chuẩn hoá + mapping fault/state → ghi DB
  Bước 3 - Tạo telemetry  : Build payload từ snapshot → ghi data.json

Chạy:
  cd backend
  python tests/test_telemetry.py
"""

import os
import sys
import json
import logging

# --- Path setup -------------------------------------------------------
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from database.sqlite_manager import MetadataDB, RealtimeDB, CacheDB
from services.project_service import ProjectService
from services.buffer_service import BufferService
from services.telemetry_service import TelemetryService
from services.fault_state_service import FaultStateService
from services.polling_service import PollingService
import config

# --- Logging ----------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("TestTelemetry")

OUTPUT_FILE = "data.json"


# ======================================================================
# BƯỚC 1: ĐỌC DỮ LIỆU
# ======================================================================
def buoc_1_doc_du_lieu(service: PollingService, project_id: int) -> bool:
    """
    Poll tất cả inverter của project qua Modbus.
    Kết quả raw_data được lưu vào service.buffer[inv.id].

    Returns:
        True  – nếu ít nhất một inverter phản hồi.
        False – nếu không có inverter nào.
    """
    logger.info("=== BƯỚC 1: ĐỌC DỮ LIỆU TỪ INVERTER ===")
    total_p_ac = service.poll_all_inverters(project_id)

    if not service.buffer:
        logger.warning("Không có dữ liệu từ inverter (buffer rỗng). Kiểm tra kết nối Modbus.")
        return False

    logger.info(f"Poll thành công {len(service.buffer)} inverter(s). Tổng P_ac = {total_p_ac:.2f} kW")
    for inv_id, raw in service.buffer.items():
        logger.info(
            f"  [INV {inv_id}] state={raw.get('state_id')} | "
            f"fault={raw.get('fault_code')} | "
            f"p_ac={raw.get('p_inv_w')} kW | "
            f"e_total={raw.get('e_total')} kWh"
        )
    return True


# ======================================================================
# BƯỚC 2: TÍNH TOÁN, CHUẨN HOÁ, MAPPING LỖI & TRẠNG THÁI
# ======================================================================
def buoc_2_xu_ly(service: PollingService, project_id: int) -> bool:
    """
    Từ buffer đã có:
      - NormalizationService chuẩn hoá các giá trị vật lý (đơn vị, làm tròn, loại bỏ ngoài khoảng).
      - FaultStateService đã map fault_code → fault_description, state_id → state_name (đã chạy ở bước 1).
      - Ghi snapshot 5 phút vào RealtimeDB (bảng inverter_ac, mppt, string, project).
      - TelemetryService build payload và đẩy vào buffer gửi server.

    Returns:
        True nếu ghi DB thành công.
    """
    logger.info("=== BƯỚC 2: CHUẨN HOÁ + MAPPING + GHI DATABASE ===")

    if not service.buffer:
        logger.error("Buffer rỗng – bỏ qua bước 2.")
        return False

    # Log kết quả mapping (đã thực hiện trong bước 1 bởi FaultStateService)
    for inv_id, raw in service.buffer.items():
        logger.info(
            f"  [INV {inv_id}] state_name='{raw.get('state_name')}' | "
            f"fault_desc='{raw.get('fault_description')}' | "
            f"severity='{raw.get('severity')}' | "
            f"e_monthly={raw.get('e_monthly')} kWh"
        )

    # Chuẩn hoá + ghi DB + build telemetry buffer
    service.save_to_database(project_id)
    logger.info(f"Đã ghi snapshot vào RealtimeDB cho project {project_id}.")
    return True


# ======================================================================
# BƯỚC 3: TẠO TELEMETRY
# ======================================================================
def buoc_3_tao_telemetry(
    project_service: ProjectService,
    telemetry_service: TelemetryService,
    project,
    output_file: str,
) -> dict | None:
    """
    Lấy snapshot mới nhất từ RealtimeDB → build telemetry payload.
    Ghi kết quả ra file JSON theo format giống data.txt để kiểm tra trực quan:
      - Chỉ giữ "project" và "inverters" (bỏ project_id, server_id, timestamp cấp ngoài)
      - Khi inverter không có lỗi → errors = ["RUNNING"]

    Returns:
        payload dict nếu thành công, None nếu không có snapshot.
    """
    logger.info("=== BƯỚC 3: TẠO TELEMETRY PAYLOAD ===")

    snapshot = project_service.get_project_snapshot(project.id)
    if not snapshot:
        logger.warning(f"Không có snapshot cho project {project.id} – bỏ qua.")
        return None

    payload = telemetry_service._build_payload(project.id, snapshot)

    # --- Post-process: errors = ["RUNNING"] object khi không có lỗi thực ---
    current_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    for inv in payload.get("inverters", []):
        if not inv.get("errors"):
            inv["errors"] = [
                {
                    "fault_code": 0,
                    "fault_description": "RUNNING",
                    "repair_instruction": "N/A",
                    "severity": "STABLE",
                    "created_at": current_ts
                }
            ]

    # --- Format giống data.txt: chỉ "project" và "inverters", không có { } ngoài cùng ---
    output_payload = {
        "project":   payload["project"],
        "inverters": payload["inverters"],
    }

    logger.info(
        f"Telemetry built cho project '{project.name}' (server_id={project.server_id}): "
        f"{len(payload.get('inverters', []))} inverter(s)"
    )

    # Dump JSON string and strip the first { and last }
    json_str = json.dumps(output_payload, indent=4, ensure_ascii=False).strip()
    if json_str.startswith("{") and json_str.endswith("}"):
        json_str = json_str[1:-1].strip()

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(json_str)
        
    logger.info(f"Đã lưu telemetry → {os.path.abspath(output_file)}")

    # Trả về full payload (có project_id, server_id) cho all_results
    return payload


# ======================================================================
# MAIN
# ======================================================================
def run_test():
    logger.info("Bắt đầu One-Shot Telemetry Test (3 bước)...")

    try:
        # --- Khởi tạo DB ---
        metadata_db = MetadataDB(config.METADATA_DB)
        realtime_db = RealtimeDB(config.REALTIME_DB)
        cache_db    = CacheDB(config.CACHE_DB)

        # --- Khởi tạo Services ---
        buffer_service   = BufferService(realtime_db)
        project_service  = ProjectService(metadata_db, realtime_db)
        telemetry_service = TelemetryService(project_service, buffer_service)
        fault_service    = FaultStateService()

        # uploader=None → không gửi lên server
        service = PollingService(
            metadata_db,
            realtime_db,
            uploader=None,
            telemetry_service=telemetry_service,
            cache_db=cache_db,
            fault_service=fault_service,
        )

        # --- Lấy danh sách projects ---
        projects = metadata_db.get_all_projects()
        if not projects:
            logger.error("Không tìm thấy project nào trong database!")
            return

        all_results = []

        for project in projects:
            logger.info(f"\n{'='*60}")
            logger.info(f"PROJECT: {project.name} (local_id={project.id}, server_id={project.server_id})")
            logger.info(f"{'='*60}")

            # BƯỚC 1
            ok = buoc_1_doc_du_lieu(service, project.id)
            if not ok:
                logger.warning(f"Bỏ qua project {project.id} do không đọc được dữ liệu.")
                continue

            # BƯỚC 2
            ok = buoc_2_xu_ly(service, project.id)
            if not ok:
                logger.warning(f"Bỏ qua project {project.id} do lỗi ghi DB.")
                continue

            # BƯỚC 3
            payload = buoc_3_tao_telemetry(
                project_service,
                telemetry_service,
                project,
                OUTPUT_FILE,
            )
            if payload:
                all_results.append(payload)

        # --- Tổng kết ---
        print("\n" + "=" * 60)
        if all_results:
            print(f"DONE: {len(all_results)} project(s) xử lý thành công.")
            print(f"      Kiểm tra kết quả tại: {os.path.abspath(OUTPUT_FILE)}")
        else:
            print("DONE: Không có telemetry nào được tạo (xem log phía trên).")
        print("=" * 60 + "\n")

    except Exception as e:
        logger.error(f"Test thất bại: {e}", exc_info=True)


if __name__ == "__main__":
    run_test()
