"""
web/config_manager.py

Quản lý cấu hình theo lớp:
  1. config.py  (defaults cứng)
  2. metadata.db (lưu từ Web UI)

Web UI ghi đè → lưu vào database.
"""
import logging
from dataclasses import asdict

from backend.core import config as app_config
from backend.database import MetadataDB
from backend.models.comm import CommConfig

logger = logging.getLogger(__name__)

def load_config() -> dict:
    """Merge config.py + metadata.db. metadata.db thắng."""
    # Layer 1: defaults từ config.py
    cfg = {
        "project": {
            "name": app_config.PROJECT_INFO.get("name", ""),
            "location": app_config.PROJECT_INFO.get("location", ""),
            "lat": app_config.PROJECT_INFO.get("lat", 0.0),
            "lon": app_config.PROJECT_INFO.get("lon", 0.0),
            "capacity_kwp": app_config.PROJECT_INFO.get("capacity_kwp", 0.0),
            "ac_capacity_kw": app_config.PROJECT_INFO.get("ac_capacity_kw", 0.0),
            "inverter_count": app_config.PROJECT_INFO.get("inverter_count", 0),
            "elec_meter_no": app_config.PROJECT_INFO.get("elec_meter_no"),
            "elec_price_per_kwh": app_config.PROJECT_INFO.get("elec_price_per_kwh", 1783.0),
        },
        "comm": {
            "driver": app_config.DRIVER,
            "comm_type": app_config.COMM_TYPE,
            "host": app_config.MODBUS_TCP_HOST,
            "port": app_config.MODBUS_TCP_PORT,
            "com_port": app_config.MODBUS_PORT,
            "baudrate": app_config.MODBUS_BAUDRATE,
            "databits": 8,
            "parity": "N",
            "stopbits": 1,
            "timeout": 1.0,
            "slave_id_start": 1,
            "slave_id_end": 30,
        }
    }

    try:
        db = MetadataDB(app_config.METADATA_DB)
        
        # Merge comm info if available from db - Default to the first one for legacy support
        comms = db.get_all_comm_configs()
        if comms:
            _deep_update(cfg["comm"], asdict(comms[0]))
            logger.info("Loaded first comm config from metadata.db")
            
        # Merge project info if available from db
        proj = db.get_project_first()
        if proj:
            proj_dict = asdict(proj)
            proj_dict = {k: v for k, v in proj_dict.items() if v is not None}
            _deep_update(cfg["project"], proj_dict)
            logger.info("Loaded project from metadata.db")
            
    except Exception as e:
        logger.warning(f"Failed to read from metadata.db: {e}")

    return cfg


def save_config(data: dict):
    """Lưu cấu hình mới vào metadata.db."""
    try:
        db = MetadataDB(app_config.METADATA_DB)
        
        if "comm" in data:
            comm_data = data["comm"]
            # Maintain default fields if not provided in the patch
            existing_comm = load_config()["comm"]
            _deep_update(existing_comm, comm_data)
            comm_config = CommConfig(**existing_comm)
            db.upsert_comm_config(comm_config)
            logger.info("Comm config saved to metadata.db")
            
        if "project" in data:
            from backend.models.project import ProjectCreate
            proj_data = data["project"]
            
            proj_create = ProjectCreate(
                name=proj_data.get("name", "Datalogger Project"),
                elec_meter_no=proj_data.get("elec_meter_no"),
                elec_price_per_kwh=proj_data.get("elec_price_per_kwh", 1783.0),
                location=proj_data.get("location"),
                lat=proj_data.get("lat", 0.0),
                lon=proj_data.get("lon", 0.0),
                capacity_kwp=proj_data.get("capacity_kwp", 0.0),
                ac_capacity_kw=proj_data.get("ac_capacity_kw", 0.0),
                inverter_count=proj_data.get("inverter_count", 0)
            )
            existing_proj = db.get_project_first()
            if existing_proj:
                db.upsert_project(proj_create, project_id=existing_proj.id)
            else:
                db.upsert_project(proj_create)
            logger.info("Project config saved to metadata.db")
            
    except Exception as e:
        logger.error(f"Failed to save to metadata.db: {e}")
        raise e


def _deep_update(base: dict, override: dict):
    for k, v in override.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
