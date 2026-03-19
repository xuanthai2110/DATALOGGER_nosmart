# tests/test_run_polling.py
"""
Script chạy polling giả lập (hoặc thật) nhưng KHÔNG gửi dữ liệu lên server.
Dùng để kiểm tra luồng đọc Modbus -> Ghi Cache -> Ghi RealtimeDB -> Build Telemetry (Local).
"""

import sys
import os
import logging
import json

# Thêm project root vào path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.sqlite_manager import MetadataDB, RealtimeDB, CacheDB
from services.polling_service import PollingService
from services.uploader_service import UploaderService
from services.buffer_service import BufferService
from services.project_service import ProjectService
from services.telemetry_service import TelemetryService
from services.fault_state_service import FaultStateService
import config

# Cấu hình logging - Chỉ hiện WARNING trở lên cho các module khác để output sạch
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Tắt triệt để log từ các module ồn ào
logging.getLogger("pymodbus").setLevel(logging.WARNING)
logging.getLogger("services.polling_service").setLevel(logging.WARNING)
logging.getLogger("communication.modbus_tcp").setLevel(logging.WARNING)
logging.getLogger("communication.modbus_rtu").setLevel(logging.WARNING)

# Logger riêng cho script test này để in thông tin theo yêu cầu
test_logger = logging.getLogger("TestConsole")
test_logger.setLevel(logging.INFO)

# Handler để in ra console với định dạng sạch
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s', '%H:%M:%S'))
test_logger.addHandler(console_handler)
test_logger.propagate = False

class MockUploader:
    """Uploader giả lập để không gửi dữ liệu thật lên server"""
    def __init__(self, buffer_service):
        self.buffer_service = buffer_service
        
    def upload(self):
        records = self.buffer_service.get_all()
        count = len(records)
        if count > 0:
            test_logger.info(f"🚀 [SERVER] Đã (giả) gửi telemetry cho {count} project(s). Đang ghi file data.json...")
            
            # Ghi file data.json để user kiểm tra (lấy bản ghi cuối cùng hoặc bản ghi đầu tiên tùy ý, 
            # ở đây ta ghi toàn bộ list nếu có nhiều project, hoặc chỉ object nếu là 1)
            output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data.json")
            
            try:
                # Nếu chỉ có 1 bản ghi (thông thường cho 1 project), ghi trực tiếp object đó
                # Nếu có nhiều, ghi thành list
                data_to_save = records[0] if count == 1 else records
                
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(data_to_save, f, indent=4, ensure_ascii=False)
                test_logger.info(f"💾 [FILE] Đã lưu payload vào: {output_path}")
            except Exception as e:
                test_logger.error(f"❌ [FILE] Lỗi khi ghi data.json: {e}")

            # In chi tiết lỗi của từng inverter nếu có
            for rec in records:
                inverters = rec.get("inverters", [])
                for inv in inverters:
                    sn = inv.get("serial_number", "N/A")
                    errs = inv.get("errors", [])
                    if errs:
                        err_json = json.dumps(errs, indent=4, ensure_ascii=False)
                        test_logger.info(f"   └─ [INV {sn}] Errors Payload:\n{err_json}")

            # Xoá bản ghi để giả lập đã gửi xong
            for rec in records:
                self.buffer_service.delete(rec["id"])
        return True

def main():
    try:
        print("\n" + "="*60)
        print("  Hệ thống Polling đang chạy (Chế độ TEST - Không Upload)")
        print("="*60)
        
        metadata_db = MetadataDB(config.METADATA_DB)
        realtime_db = RealtimeDB(config.REALTIME_DB)
        cache_db = CacheDB(config.CACHE_DB)
        
        project_service = ProjectService(metadata_db, realtime_db)
        buffer_service = BufferService(realtime_db)
        telemetry_service = TelemetryService(project_service, buffer_service)
        
        uploader = MockUploader(buffer_service)
        fault_service = FaultStateService()
        
        service = PollingService(
            metadata_db, 
            realtime_db, 
            uploader=uploader, 
            telemetry_service=telemetry_service, 
            cache_db=cache_db, 
            fault_service=fault_service
        )
        
        # Monkey patch PollingService để in thông báo theo style yêu cầu
        original_poll = service.poll_all_inverters
        def patched_poll(project_id):
            test_logger.info(f"🔍 [POLL] Bắt đầu quét Project ID: {project_id}")
            inverters = service.metadata_db.get_inverters_by_project(project_id)
            active_count = len([inv for inv in inverters if inv.is_active])
            
            # Chạy poll gốc
            p_total = original_poll(project_id)
            
            # Thống kê kết quả
            results = []
            for inv_id, data in service.buffer.items():
                results.append(f"Inverter {inv_id}: OK")
            
            if results:
                test_logger.info(f"✅ [READ] {', '.join(results)} | Tổng P_ac: {p_total:.1f}W")
            else:
                test_logger.info(f"❌ [READ] Thất bại: Không đọc được dữ liệu từ {active_count} inverters.")
            return p_total
            
        original_check = service._check_and_send_immediate
        def patched_check(inv, raw_data):
            # Lấy trạng thái cũ trước khi update
            old_state = service.last_states.get(inv.id)
            old_fault = service.last_faults.get(inv.id)
            
            new_state = raw_data.get("state_id")
            new_fault = raw_data.get("fault_code", 0)
            
            # Gọi gốc để thực hiện logic (bao gồm set last_states/faults)
            original_check(inv, raw_data)
            
            # Nếu có thay đổi thì in ra
            if old_state is not None and old_state != new_state:
                test_logger.warning(f"⚠️  [CHANGE] Inverter {inv.id}: State {old_state} -> {new_state} ({raw_data.get('state_name')})")
            if old_fault is not None and old_fault != new_fault:
                test_logger.warning(f"🚨 [CHANGE] Inverter {inv.id}: Fault {old_fault} -> {new_fault} ({raw_data.get('fault_description')})")

        service.poll_all_inverters = patched_poll
        service._check_and_send_immediate = patched_check

        service.run_forever()
        
    except KeyboardInterrupt:
        print("\n" + "="*60)
        print("  Dừng hệ thống Polling.")
        print("="*60 + "\n")
    except Exception as e:
        logging.error(f"Lỗi nghiêm trọng: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
