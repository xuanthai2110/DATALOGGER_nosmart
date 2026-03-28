from fastapi import APIRouter, Depends, HTTPException
from database.sqlite_manager import MetadataDB, RealtimeDB, CacheDB
from backend.api.auth_api import get_current_user_id, get_db, get_rdb, get_cdb
from dataclasses import asdict
import logging

router = APIRouter(tags=["monitoring"])
logger = logging.getLogger(__name__)

@router.get("/project/{project_id}/latest")
def get_latest_project_data(project_id: int, cdb: CacheDB = Depends(get_cdb), rdb: RealtimeDB = Depends(get_rdb), current_user = Depends(get_current_user_id)):
    """Lấy dữ liệu realtime mới nhất của một dự án (ưu tiên RAM)."""
    try:
        # 1. Thử lấy từ Cache RAM trước (Dữ liệu 10s)
        # Lưu ý: CacheDB lưu theo inverter_id, nên chúng ta cần tổng hợp hoặc lấy từ rdb nếu muốn gói project cũ
        # Tuy nhiên, để nhất quán, nếu muốn gói project 'latest' kiểu snapshot thì vẫn dùng rdb.
        # Nhưng để Web UI mượt nhất, ta nên trả về dữ liệu snapshot mới nhất từ rdb.
        data = rdb.get_latest_project_realtime(project_id)
        if not data:
            return {"ok": False, "message": "No data found"}
        return asdict(data)
    except Exception as e:
        logger.error(f"get_latest_project_data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/inverter/{inverter_id}/latest")
def get_latest_inverter_data(inverter_id: int, cdb: CacheDB = Depends(get_cdb), current_user = Depends(get_current_user_id)):
    """Lấy dữ liệu realtime 10s từ RAM."""
    try:
        data = cdb.get_latest_realtime(inverter_id)
        if not data:
            return {"ok": False, "message": "No data found in cache"}
        return data  # CacheDB returns dict already
    except Exception as e:
        logger.error(f"get_latest_inverter_data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/inverter/{inverter_id}/detail")
def get_inverter_detail(inverter_id: int, rdb: RealtimeDB = Depends(get_rdb), current_user = Depends(get_current_user_id)):
    """Lấy toàn bộ dữ liệu realtime chi tiết (AC, MPPT, String, Errors) của một biến tần."""
    try:
        ac = rdb.get_latest_inverter_ac_realtime(inverter_id)
        mppts = rdb.get_latest_mppt_batch(inverter_id)
        strings = rdb.get_latest_string_batch(inverter_id)
        errors = rdb.get_inverter_errors(inverter_id) # Lấy danh sách lỗi gần đây
        
        return {
            "ac": asdict(ac) if ac else None,
            "mppts": [asdict(m) for m in mppts],
            "strings": [asdict(s) for s in strings],
            "errors": [asdict(e) for e in errors[:10]] # Giới hạn 10 lỗi mới nhất
        }
    except Exception as e:
        logger.error(f"get_inverter_detail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/summary")
def get_dashboard_summary(db: MetadataDB = Depends(get_db), rdb: RealtimeDB = Depends(get_rdb), current_user = Depends(get_current_user_id)):
    """Lấy tóm tắt dữ liệu cho dashboard."""
    try:
        projects = db.get_projects() # MetadataDB method
        inverters = db.get_inverter()
        
        # Create map for inverter counts per project
        inv_counts = {}
        for inv in inverters:
            inv_counts[inv.project_id] = inv_counts.get(inv.project_id, 0) + 1
            
        total_p_ac = 0.0
        total_e_daily = 0.0
        total_revenue = 0.0
        active_projects_count = 0
        project_summaries = []
        
        for p in projects:
            latest = rdb.get_latest_project_realtime(p.id)
            p_ac = latest.P_ac if latest else 0.0
            e_daily = latest.E_daily if latest else 0.0
            
            revenue = e_daily * (p.elec_price_per_kwh or 0.0)
            
            total_p_ac += p_ac
            total_e_daily += e_daily
            total_revenue += revenue
            
            if p_ac > 0: active_projects_count += 1
            
            project_summaries.append({
                "id": p.id,
                "name": p.name,
                "inverter_count": inv_counts.get(p.id, 0),
                "capacity_kwp": p.capacity_kwp,
                "ac_capacity_kw": p.ac_capacity_kw,
                "elec_meter_no": p.elec_meter_no,
                "p_ac": p_ac,
                "e_daily": e_daily,
                "revenue": revenue,
                "status": "online" if p_ac > 0 else "offline"
            })
                
        return {
            "total_p_ac": total_p_ac,
            "total_e_daily": total_e_daily,
            "total_revenue": total_revenue,
            "total_projects": len(projects),
            "active_projects": active_projects_count,
            "total_inverters": len(inverters),
            "projects": project_summaries
        }
    except Exception as e:
        logger.error(f"get_dashboard_summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/project/{project_id}/range")
def get_project_history(project_id: int, start: str, end: str, rdb: RealtimeDB = Depends(get_rdb), current_user = Depends(get_current_user_id)):
    """Lấy dữ liệu lịch sử của dự án trong khoảng thời gian (start/end format YYYY-MM-DD HH:MM:SS)."""
    try:
        data = rdb.get_project_realtime_range(project_id, start, end)
        return [asdict(d) for d in data]
    except Exception as e:
        logger.error(f"get_project_history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/inverter/{inverter_id}/range")
def get_inverter_history(inverter_id: int, start: str, end: str, rdb: RealtimeDB = Depends(get_rdb), current_user = Depends(get_current_user_id)):
    """Lấy dữ liệu lịch sử AC của biến tần trong khoảng thời gian."""
    try:
        data = rdb.get_inverter_ac_range(inverter_id, start, end)
        return [asdict(d) for d in data]
    except Exception as e:
        logger.error(f"get_inverter_history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
