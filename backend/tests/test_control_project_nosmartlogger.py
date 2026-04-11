import os
import sys
import time
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.models.schedule import ControlScheduleResponse
from backend.services.control_service import ControlService


class FakeArbiter:
    @contextmanager
    def operation(self, _name):
        yield


class FakeTransport:
    def __init__(self):
        self.arbiter = FakeArbiter()


class FakePolling:
    def __init__(self, inverters, driver_by_slave):
        self._inverters = list(inverters)
        self._driver_by_slave = dict(driver_by_slave)
        self._transport = FakeTransport()

    def get_polling_config(self, force_refresh=False):
        proj = SimpleNamespace(id=1, server_id=None)
        return [{"project": proj, "inverters": self._inverters}]

    def _get_transport(self, brand):
        return self._transport

    def _get_driver(self, brand, transport, slave_id, model=None):
        return self._driver_by_slave.get(slave_id)


class FakeDriverMaxP:
    def __init__(self, power_w=0):
        self.power_w = power_w
        self.kw_limits = []

    def read_power(self):
        return int(self.power_w)

    def control_P(self, kw):
        self.kw_limits.append(kw)
        return True


class TestBuildMaxpSetpoints(unittest.TestCase):
    def setUp(self):
        self.polling = FakePolling([], {})
        self.svc = ControlService(self.polling)

    def test_rated_proportional(self):
        invs = [
            SimpleNamespace(id=1, rate_ac_kw=10.0, capacity_kw=None, is_active=True),
            SimpleNamespace(id=2, rate_ac_kw=15.0, capacity_kw=None, is_active=True),
            SimpleNamespace(id=3, rate_ac_kw=5.0, capacity_kw=None, is_active=True),
        ]
        power = {1: 0, 2: 0, 3: 0}
        sp = self.svc._build_maxp_setpoints_kw(invs, 21000.0, power)
        self.assertAlmostEqual(sp[1], 7.0, places=3)
        self.assertAlmostEqual(sp[2], 10.5, places=3)
        self.assertAlmostEqual(sp[3], 3.5, places=3)
        self.assertAlmostEqual(sum(sp.values()), 21.0, places=3)

    def test_equal_split_when_no_rated(self):
        invs = [
            SimpleNamespace(id=1, rate_ac_kw=None, capacity_kw=None, is_active=True),
            SimpleNamespace(id=2, rate_ac_kw=None, capacity_kw=None, is_active=True),
        ]
        power = {1: 0, 2: 0}
        sp = self.svc._build_maxp_setpoints_kw(invs, 10000.0, power)
        self.assertAlmostEqual(sp[1], 5.0, places=3)
        self.assertAlmostEqual(sp[2], 5.0, places=3)

    def test_measured_power_weights(self):
        invs = [
            SimpleNamespace(id=1, rate_ac_kw=100.0, capacity_kw=None, is_active=True),
            SimpleNamespace(id=2, rate_ac_kw=100.0, capacity_kw=None, is_active=True),
        ]
        power = {1: 1000, 2: 3000}
        sp = self.svc._build_maxp_setpoints_kw(invs, 8000.0, power)
        self.assertAlmostEqual(sp[1], 2.0, places=3)
        self.assertAlmostEqual(sp[2], 6.0, places=3)


class TestProjectApplyAndLoop(unittest.TestCase):
    def _make_schedule(self, mode="MAXP", limit_watts=8000.0, limit_percent=None):
        return ControlScheduleResponse(
            id=99,
            project_id=1,
            scope="PROJECT",
            mode=mode,
            start_at="2020-01-01T00:00:00+00:00",
            end_at="2030-01-01T00:00:00+00:00",
            status="SCHEDULED",
            limit_watts=limit_watts,
            limit_percent=limit_percent,
        )

    def test_apply_maxp_writes_each_inverter(self):
        d1 = FakeDriverMaxP(power_w=2000)
        d2 = FakeDriverMaxP(power_w=2000)
        invs = [
            SimpleNamespace(
                id=1,
                brand="Huawei",
                slave_id=1,
                serial_number="A",
                rate_ac_kw=50.0,
                capacity_kw=None,
                is_active=True,
            ),
            SimpleNamespace(
                id=2,
                brand="Huawei",
                slave_id=2,
                serial_number="B",
                rate_ac_kw=50.0,
                capacity_kw=None,
                is_active=True,
            ),
        ]
        polling = FakePolling(invs, {1: d1, 2: d2})
        svc = ControlService(polling)
        sch = self._make_schedule(limit_watts=10000.0)
        ok = svc.apply(sch)
        self.assertTrue(ok)
        self.assertEqual(len(d1.kw_limits), 1)
        self.assertEqual(len(d2.kw_limits), 1)
        self.assertAlmostEqual(d1.kw_limits[0] + d2.kw_limits[0], 10.0, places=2)

    def test_reset_stops_loop_and_resets(self):
        d1 = FakeDriverMaxP(power_w=5000)
        invs = [
            SimpleNamespace(
                id=1,
                brand="Huawei",
                slave_id=1,
                serial_number="A",
                rate_ac_kw=100.0,
                capacity_kw=None,
                is_active=True,
            ),
        ]
        polling = FakePolling(invs, {1: d1})

        class FakeDriverReset(FakeDriverMaxP):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.pct_calls = []

            def control_percent(self, p):
                self.pct_calls.append(p)
                return True

        d1 = FakeDriverReset(power_w=5000)
        polling = FakePolling(invs, {1: d1})
        svc = ControlService(polling)
        sch = self._make_schedule(limit_watts=5000.0)

        with patch("backend.services.control_service.settings") as m:
            m.PROJECT_MAXP_CONTROL_INTERVAL_SEC = 1
            m.PROJECT_MAXP_POWER_WEIGHT_EPS_W = 50.0
            svc.apply(sch)
            time.sleep(0.05)
            svc.reset(sch)
            time.sleep(0.05)

        self.assertIn(100.0, d1.pct_calls)

    def test_limit_percent_clamp(self):
        class PctDriver:
            def __init__(self):
                self.pct = None

            def read_power(self):
                return 0

            def control_percent(self, p):
                self.pct = p
                return True

        d1 = PctDriver()
        invs = [
            SimpleNamespace(
                id=1,
                brand="Huawei",
                slave_id=1,
                serial_number="A",
                rate_ac_kw=10.0,
                capacity_kw=None,
                is_active=True,
            ),
        ]
        polling = FakePolling(invs, {1: d1})
        svc = ControlService(polling)
        sch = ControlScheduleResponse(
            id=100,
            project_id=1,
            scope="PROJECT",
            mode="LIMIT_PERCENT",
            start_at="2020-01-01T00:00:00+00:00",
            end_at="2030-01-01T00:00:00+00:00",
            status="SCHEDULED",
            limit_watts=None,
            limit_percent=150.0,
        )
        self.assertTrue(svc.apply(sch))
        self.assertEqual(d1.pct, 100.0)


if __name__ == "__main__":
    unittest.main()
