from typing import Optional, List, Dict, Any
from dataclasses import asdict

def find_raw_fault(brand: str, unified_code: int, old_instruction: str) -> Optional[int]:
    from backend.services.fault_mappings import FAULT_MAPS
    fault_map = FAULT_MAPS.get(brand.upper(), {})
    possible_faults = []
    for raw_code, info in fault_map.items():
        if info.get("id_unified") == unified_code:
            possible_faults.append((raw_code, info))
            
    if not possible_faults:
        return None
        
    if old_instruction:
        for raw_code, info in possible_faults:
            if info.get("repair_instruction") == old_instruction:
                return raw_code
                
    return possible_faults[0][0]

class MonitoringService:
    def __init__(self, metadata_db, realtime_db, cache_db=None):
        self.metadata_db = metadata_db
        self.realtime_db = realtime_db
        self.cache_db = cache_db

    def get_latest_project_data(self, project_id: int) -> Optional[dict]:
        data = self.realtime_db.get_latest_project_realtime(project_id)
        if not data:
            return None
        return asdict(data)

    def get_latest_inverter_data(self, inverter_id: int) -> Optional[dict]:
        if not self.cache_db:
            return None
        return self.cache_db.get_latest_realtime(inverter_id)

    def get_inverter_detail(self, inverter_id: int) -> dict:
        ac = self.realtime_db.get_latest_inverter_ac_realtime(inverter_id)
        mppts = self.realtime_db.get_latest_mppt_batch(inverter_id)
        strings = self.realtime_db.get_latest_string_batch(inverter_id)
        errors = self.realtime_db.get_inverter_errors(inverter_id)
        
        # Nâng cấp động các lỗi cũ từ database chưa có tiền tố
        try:
            inv = self.metadata_db.get_inverter_by_id(inverter_id)
            if inv and errors:
                brand = inv.brand.upper()
                from backend.services.fault_service import FaultService
                for e in errors:
                    if e.repair_instruction and not e.repair_instruction.startswith("mã lỗi ") and e.fault_code != 23:
                        raw_code = find_raw_fault(brand, e.fault_code, e.repair_instruction)
                        if raw_code is not None:
                            e.repair_instruction = FaultService.format_repair_instruction(brand, raw_code, e.repair_instruction)
        except Exception as ex:
            import logging
            logging.getLogger(__name__).warning(f"Failed to auto-format history error: {ex}")
            
        return {
            "ac": asdict(ac) if ac else None,
            "mppts": [asdict(m) for m in mppts],
            "strings": [asdict(s) for s in strings],
            "errors": [asdict(e) for e in errors[:10]]
        }

    def get_dashboard_summary(self) -> dict:
        projects = self.metadata_db.get_projects()
        inverters = self.metadata_db.get_all_inverters()
        
        inv_counts = {}
        for inv in inverters:
            inv_counts[inv.project_id] = inv_counts.get(inv.project_id, 0) + 1
            
        total_p_ac = 0.0
        total_e_daily = 0.0
        total_revenue = 0.0
        active_projects_count = 0
        project_summaries = []
        
        for p in projects:
            latest = self.realtime_db.get_latest_project_realtime(p.id)
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

    def get_project_history(self, project_id: int, start: str, end: str) -> List[dict]:
        data = self.realtime_db.get_project_realtime_range(project_id, start, end)
        return [asdict(d) for d in data]

    def get_inverter_history(self, inverter_id: int, start: str, end: str) -> List[dict]:
        data = self.realtime_db.get_inverter_ac_range(inverter_id, start, end)
        return [asdict(d) for d in data]
