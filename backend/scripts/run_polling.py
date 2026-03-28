import sys
import os
import logging
import time
from datetime import datetime

# 1. Thêm đường dẫn gốc của project vào sys.path để import được các module trong backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.sqlite_manager import MetadataDB, CacheDB
from services.polling_service import PollingService
import config

# 2. Cấu hình Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("polling.log")
    ]
)

logger = logging.getLogger("RunPolling")


def print_cache_table(project, cache_db):
    """In bảng dữ liệu tóm tắt từ RAM Cache để giám sát trực quan"""
    try:
        ac_list = cache_db.get_ac_cache_by_project(project.id)
        if not ac_list:
            return

        # Lấy thêm lỗi (nếu có) từ error_cache
        err_list = cache_db.get_error_cache_by_project(project.id)
        err_map = {r['inverter_id']: r['fault_code'] for r in err_list}

        print(f"\n{'='*75}")
        print(f">>> [CACHE SNAPSHOT] Dự án: {project.name} | Lúc: {datetime.now().strftime('%H:%M:%S')} <<<")
        print(f"{'='*75}")
        print(f"{'ID':<4} | {'P_ac (W)':<10} | {'E_daily':<12} | {'V_a (V)':<8} | {'Temp':<6} | {'Fault'}")
        print(f"{'-'*75}")
        
        for r in ac_list:
            inv_id = r['inverter_id']
            p_ac = r.get('P_ac', 0)
            e_day = r.get('E_daily', 0)
            v_a = r.get('V_a', 0)
            temp = r.get('Temp_C', 0)
            fault = err_map.get(inv_id, 0)
            
            fault_str = "OK" if fault == 0 else f"ERR:{fault}"
            
            print(f"{inv_id:<4} | {p_ac:<10} | {e_day:<12} | {v_a:<8} | {temp:<6} | {fault_str}")
        print(f"{'='*75}\n")
    except Exception as e:
        logger.error(f"Lỗi khi in bảng snapshot: {e}")
def print_full_cache_snapshot(project, cache_db):
    """In toàn bộ thông số chi tiết từ RAM Cache (AC, MPPT, String, Status)"""
    try:
        # 1. Lấy toàn bộ dữ liệu từ các bảng cache
        ac_list = cache_db.get_ac_cache_by_project(project.id)
        if not ac_list:
            return

        mppt_list = cache_db.get_mppt_cache_by_project(project.id)
        string_list = cache_db.get_string_cache_by_project(project.id)
        err_list = cache_db.get_error_cache_by_project(project.id)

        # 2. Map dữ liệu để truy xuất nhanh theo inverter_id
        mppt_map = {}
        for m in mppt_list:
            inv_id = m['inverter_id']
            if inv_id not in mppt_map: mppt_map[inv_id] = []
            mppt_map[inv_id].append(m)

        string_map = {}
        for s in string_list:
            inv_id = s['inverter_id']
            if inv_id not in string_map: string_map[inv_id] = []
            string_map[inv_id].append(s)

        err_map = {e['inverter_id']: e for e in err_list}

        # 3. In Header của Project
        print(f"\n{'='*95}")
        print(f">>> [FULL SNAPSHOT] PROJECT: {project.name.upper()} (ID:{project.id}) | {datetime.now().strftime('%H:%M:%S')} <<<")
        print(f"{'='*95}")

        # 4. In bảng AC Summary
        print(f"--- [AC PARAMETERS] ---")
        ac_header = f"{'ID':<4} | {'P_ac (W)':<10} | {'E_daily':<10} | {'V_a (V)':<8} | {'Temp':<5} | {'Status'}"
        print(ac_header)
        print("-" * len(ac_header))
        
        for r in ac_list:
            inv_id = r['inverter_id']
            
            # Lấy mã Status và Fault từ cache
            err_data = err_map.get(inv_id, {})
            status_code = err_data.get('status_code', 0)
            fault_code = err_data.get('fault_code', 0)
            
            # Hiển thị dạng Code:Code (ví dụ 2:0)
            status_display = f"{status_code}:{fault_code}"
            print(f"{inv_id:<4} | {r.get('P_ac',0):<10} | {r.get('E_daily',0):<10} | {r.get('V_a',0):<8} | {r.get('Temp_C',0):<5} | {status_display}")

        # 5. In chi tiết MPPT & Strings
        print(f"\n--- [MPPT & STRINGS DETAIL] ---")
        for r in ac_list:
            inv_id = r['inverter_id']
            inv_mppts = sorted(mppt_map.get(inv_id, []), key=lambda x: x['mppt_index'])
            inv_strings = sorted(string_map.get(inv_id, []), key=lambda x: x['string_id'])
            
            # Group MPPT info: "M1: 600V/5A/3000W | M2: ..."
            mppt_info = " | ".join([f"M{m['mppt_index']}: {m['P_mppt']}W" for m in inv_mppts])
            # Group String info: "S1: 2.5A, S2: 2.5A..."
            string_info = ", ".join([f"S{s['string_id']}: {s['I_string']}A" for s in inv_strings])
            
            print(f"[Inv {inv_id:02d}] MPPTs: {mppt_info}")
            if string_info:
                print(f"         Strings: {string_info}")
        
        print(f"{'='*95}\n")

    except Exception as e:
        logger.error(f"Lỗi khi in full snapshot: {e}")
        # 1. Thực hiện quét dữ liệu
        service.poll_all_inverters(project.id, inverters=inverters)
        
        # 2. In bảng dữ liệu Cache kết quả ngay sau khi đọc
        print_cache_table(project, cache_db)
        # 1. Thực hiện quét dữ liệu
        service.poll_all_inverters(project.id, inverters=inverters)
        
        # 2. In toàn bộ thông số từ Cache ngay sau khi đọc
        print_full_cache_snapshot(project, cache_db)


def main():
    try:
        logger.info("Initializing Simple Polling System (Cache Only Mode)...")
        
        metadata_db = MetadataDB(config.METADATA_DB)
        cache_db = CacheDB(config.CACHE_DB)
        
        service = PollingService(metadata_db, cache_db)
        
        logger.info(f"Polling loop started (Interval: {config.POLL_INTERVAL}s)")
        
        while True:
            t0 = time.time()
            try:
                # 1. Lấy cấu hình từ cache (hoặc database nếu hết hạn)
                polling_config = service.get_polling_config()
                
                for item in polling_config:
                    project = item["project"]
                    inverters = item["inverters"]
                    
                    # 2. Thực hiện quét dữ liệu cho danh sách inverter đã cache
                    service.poll_all_inverters(project.id, inverters=inverters)
                    
                    # 3. In bảng dữ liệu Cache kết quả ngay sau khi đọc
                    print_full_cache_snapshot(project, cache_db)
                    
            except Exception as loop_err:
                logger.error(f"Error in polling cycle: {loop_err}")
            
            # Đảm bảo chu kỳ quét đều đặn theo POLL_INTERVAL
            elapsed = time.time() - t0
            sleep_time = max(0.1, config.POLL_INTERVAL - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("Polling Service stopped by user.")
    except Exception as e:
        logger.error(f"Critical error in Polling Service: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
