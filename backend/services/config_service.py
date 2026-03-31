import logging
from dataclasses import asdict, fields
from backend.models.project import ProjectCreate
from backend.models.comm import CommConfig
from backend.models.inverter import InverterCreate

logger = logging.getLogger(__name__)

class ConfigService:
    def __init__(self, metadata_db):
        self.metadata_db = metadata_db

    def get_legacy_config(self) -> dict:
        try:
            projects = self.metadata_db.get_projects()
            project = asdict(projects[0]) if projects else {}

            comms = self.metadata_db.get_comm_config()
            comm = asdict(comms[0]) if comms else {}

            inverters = []
            if projects:
                invs = self.metadata_db.get_inverters_by_project(projects[0].id)
                inverters = [asdict(inv) for inv in invs]

            return {
                "project": project,
                "comm": comm,
                "inverters": inverters
            }
        except Exception as e:
            logger.error(f"ConfigService.get_legacy_config error: {e}")
            raise

    def update_legacy_config(self, data: dict):
        try:
            with self.metadata_db._connect() as conn:
                conn.execute("DELETE FROM inverters")
                conn.execute("DELETE FROM projects")
                conn.execute("DELETE FROM comm_config")
                
            proj_data = data.get("project", {})
            proj_id = None
            if proj_data:
                if "ac_capacity_kw" not in proj_data:
                    proj_data["ac_capacity_kw"] = proj_data.get("capacity_kw", 0.0)
                proj = ProjectCreate(**proj_data)
                proj_id = self.metadata_db.post_project(proj)

            comm_data = data.get("comm", {})
            comm_id = None
            if comm_data:
                # Use the service-wrapped post_comm which now handles UPSERT logic
                comm = CommConfig(**comm_data)
                comm_id = self.metadata_db.post_comm(comm)

            invs_data = data.get("inverters", [])
            for i, inv in enumerate(invs_data):
                inv["project_id"] = proj_id
                inv["comm_id"] = comm_id
                inv["inverter_index"] = i + 1
                # Filter fields for InverterCreate
                inv_fields = {f.name for f in fields(InverterCreate)}
                inv_data = {k: v for k, v in inv.items() if k in inv_fields}
                
                self.metadata_db.upsert_inverter(InverterCreate(**inv_data))

            return True
        except Exception as e:
            logger.error(f"ConfigService.update_legacy_config error: {e}")
            raise
