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
                    print_cache_table(project, cache_db)
                    
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
