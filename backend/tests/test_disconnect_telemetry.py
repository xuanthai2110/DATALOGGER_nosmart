import os
import sys
from types import SimpleNamespace

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from backend.services.telemetry_service import TelemetryService
from backend.workers.build_tele_worker import BuildTeleWorker


class FakeCacheDB:
    def __init__(self, ac_rows=None, err_rows=None):
        self.ac_rows = ac_rows or {}
        self.err_rows = err_rows or {}

    def get_ac_cache(self, inverter_id):
        return self.ac_rows.get(inverter_id)

    def get_error_cache(self, inverter_id):
        return self.err_rows.get(inverter_id)


class FakeRealtimeDB:
    def __init__(self):
        self.outbox = []

    def post_to_outbox(self, project_id, server_id, data):
        self.outbox.append((project_id, server_id, data))

    def trim_outbox(self, max_rows):
        return None


class FakeProjectService:
    def __init__(self):
        self.project = SimpleNamespace(id=1, server_id=99)
        self.inverters = [
            SimpleNamespace(id=1, serial_number="INV-1", is_active=True),
            SimpleNamespace(id=2, serial_number="INV-2", is_active=True),
        ]

    def get_project(self, project_id):
        if project_id == self.project.id:
            return self.project
        return None

    def get_inverters_by_project(self, project_id):
        if project_id == self.project.id:
            return list(self.inverters)
        return []


def test_is_all_inverters_disconnect_from_fault_json():
    cache_db = FakeCacheDB(
        ac_rows={
            1: {"updated_at": "2026-04-17T08:00:00"},
            2: {"updated_at": "2026-04-17T08:00:00"},
        },
        err_rows={
            1: {"fault_json": '[{"severity":"DISCONNECT"}]'},
            2: {"fault_json": '[{"severity":"DISCONNECT"}]'},
        },
    )

    telemetry = TelemetryService(realtime_db=None)

    assert telemetry.is_all_inverters_disconnect([1, 2], cache_db) is True
    assert telemetry.is_all_inverters_disconnect([1, 3], cache_db) is False


def test_build_worker_only_saves_first_all_disconnect_payload():
    cache_db = FakeCacheDB()
    realtime_db = FakeRealtimeDB()
    project_svc = FakeProjectService()
    worker = BuildTeleWorker(cache_db, project_svc, realtime_db, interval=300.0)

    worker.telemetry.is_all_inverters_disconnect = lambda inverter_ids, cache: True
    worker.telemetry.build_payload_from_cache = lambda project_id, server_id, inverters, cache: [{"project": {}, "inverters": []}]

    worker._build_for_project(1)
    worker._build_for_project(1)

    assert len(realtime_db.outbox) == 1
    assert worker._disconnect_notified_projects[1] is True
