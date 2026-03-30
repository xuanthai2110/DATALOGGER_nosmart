import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BASE_DIR)

from backend.db_manager import MetadataDB 
from backend.models.project import ProjectCreate
from config import METADATA_DB,REALTIME_DB
from backend.services.project_service import ProjectService

def test():
    metadata_db = MetadataDB(METADATA_DB)
    realtime_db = MetadataDB(REALTIME_DB)
    project_service = ProjectService(metadata_db, realtime_db)

    all_project = project_service.get_project_snapshot(1)
    print(all_project)

if __name__ == "__main__":
    test()