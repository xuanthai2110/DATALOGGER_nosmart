import json
from dataclasses import asdict
from database.sqlite_manager import MetadataDB, RealtimeDB
from typing import Dict, List, Any

# Sử dụng chính xác class từ sqlite_manager
meta_db = MetadataDB("metadata.db")
rt_db = RealtimeDB("realtime.db")

def build_json_optimized(project_id: int) -> Dict[str, Any]:
    """
    Xây dựng cấu trúc JSON snapshot mới nhất cho toàn bộ dự án.
    Tối ưu hóa bằng cách load dữ liệu theo lô (Batch Load) thay vì query lẻ từng Inverter/MPPT.
    """
    
    # 1. Lấy Project Realtime mới nhất
    # SQL đơn giản vì chỉ có 1 project_id
    project_rt_list = rt_db.get_project_realtime_range(
        project_id, "2000-01-01", "2100-01-01"
    )
    project_rt = project_rt_list[-1] if project_rt_list else None

    # 2. Lấy danh sách Inverter từ Metadata
    inverters_meta = meta_db.get_inverters_by_project(project_id)
    inv_ids = [inv.id for inv in inverters_meta]
    
    if not inv_ids:
        return {"project": project_rt, "inverters": []}

    # 3. Batch Load toàn bộ AC mới nhất cho tất cả Inverters
    # Sử dụng raw query trực tiếp vào connection để dùng Window Function
    ac_map = {}
    with rt_db._connect() as conn:
        rows = conn.execute(f"""
            SELECT * FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY inverter_id ORDER BY created_at DESC) as rn
                FROM inverter_ac_realtime
                WHERE project_id = ?
            ) WHERE rn = 1
        """, (project_id,)).fetchall()
        for r in rows:
            ac_map[r["inverter_id"]] = dict(r)

    # 4. Batch Load toàn bộ MPPT mới nhất cho tất cả Inverters
    mppt_map = {} # inverter_id -> [mppts]
    with rt_db._connect() as conn:
        rows = conn.execute(f"""
            SELECT * FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY inverter_id, mppt_index ORDER BY created_at DESC) as rn
                FROM mppt_realtime
                WHERE project_id = ?
            ) WHERE rn = 1
        """, (project_id,)).fetchall()
        for r in rows:
            inv_id = r["inverter_id"]
            if inv_id not in mppt_map: mppt_map[inv_id] = []
            mppt_map[inv_id].append(dict(r))

    # 5. Batch Load toàn bộ String mới nhất cho tất cả Inverters
    string_map = {} # (inverter_id, mppt_id) -> [strings]
    with rt_db._connect() as conn:
        rows = conn.execute(f"""
            SELECT * FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY inverter_id, mppt_id, string_id ORDER BY created_at DESC) as rn
                FROM string_realtime
                WHERE project_id = ?
            ) WHERE rn = 1
        """, (project_id,)).fetchall()
        for r in rows:
            key = (r["inverter_id"], r["mppt_id"])
            if key not in string_map: string_map[key] = []
            string_map[key].append({
                "string_index": r["string_id"],
                "I_mppt": r["I_string"],
                "Max_I": r["max_I"],
                "created_at": r["created_at"]
            })

    # 6. Lấy 5 lỗi mới nhất cho mỗi Inverter (Batch)
    error_map = {}
    with rt_db._connect() as conn:
        rows = conn.execute(f"""
            SELECT * FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY inverter_id ORDER BY created_at DESC) as rn
                FROM inverter_errors
                WHERE project_id = ?
            ) WHERE rn <= 5
        """, (project_id,)).fetchall()
        for r in rows:
            inv_id = r["inverter_id"]
            if inv_id not in error_map: error_map[inv_id] = []
            error_map[inv_id].append(dict(r))

    # 7. Hợp nhất dữ liệu (Assembly)
    inverters_json = []
    for inv in inverters_meta:
        inv_id = inv.id
        
        # Gắn strings vào mppts
        mppts = mppt_map.get(inv_id, [])
        for m in mppts:
            m["strings"] = string_map.get((inv_id, m["mppt_index"]), [])

        inverters_json.append({
            "serial_number": inv.serial_number,
            "ac": ac_map.get(inv_id),
            "mppts": mppts,
            "errors": error_map.get(inv_id, [])
        })

    return {
        "project": asdict(project_rt) if project_rt else None,
        "inverters": inverters_json
    }

if __name__ == "__main__":
    import time
    start_time = time.time()
    
    # Test với project id 1
    data = build_json_optimized(project_id=1)
    
    end_time = time.time()
    print(json.dumps(data, indent=2))
    print(f"\n--- Execution Time: {(end_time - start_time)*1000:.2f} ms ---")
