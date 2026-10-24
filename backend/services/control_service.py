import logging
import threading
import time
from contextlib import ExitStack, contextmanager
from typing import Any, Dict, List, Optional, Tuple

from backend.core import settings
from backend.models.schedule import ControlScheduleResponse


logger = logging.getLogger(__name__)


class ControlService:
    def __init__(self, polling_service):
        self.polling_service = polling_service
        self.post_control_readback_delay_sec = 10.0
        self._project_maxp_lock = threading.Lock()
        self._project_maxp_stop_events: Dict[int, threading.Event] = {}

        # EVN Priority Lock — khi EVN đang điều khiển, server/MQTT không được ghi đè
        self._evn_lock = threading.Lock()
        self._evn_p_locked: set = set()  # {project_id} đang bị EVN giới hạn P
        self._evn_q_locked: set = set()  # {project_id} đang bị EVN giới hạn Q

    def _find_project_item(self, schedule_project_id: int):
        for force_refresh in (False, True):
            polling_config = self.polling_service.get_polling_config(force_refresh=force_refresh)

            project_item = next(
                (item for item in polling_config if item["project"].id == schedule_project_id),
                None,
            )
            if project_item:
                return project_item

            project_item = next(
                (
                    item for item in polling_config
                    if getattr(item["project"], "server_id", None) == schedule_project_id
                ),
                None,
            )
            if project_item:
                logger.info(
                    "[ControlService] Resolved schedule project_id=%s via server_id -> local project_id=%s",
                    schedule_project_id,
                    project_item["project"].id,
                )
                return project_item

        return None

    def _active_inverters(self, project_item) -> List[Any]:
        invs = project_item.get("inverters") or []
        return [inv for inv in invs if getattr(inv, "is_active", True)]

    def _stop_project_maxp_loop(self, schedule_id: int) -> None:
        with self._project_maxp_lock:
            stop = self._project_maxp_stop_events.pop(schedule_id, None)
        if stop is not None:
            stop.set()

    @contextmanager
    def _control_priority_for(self, inverters):
        """Reserve control priority on each physical bus for the full command."""
        with ExitStack() as stack:
            seen = set()
            for inv in inverters:
                try:
                    transport = self.polling_service._get_transport(self._resolve_inv_comm_id(inv))
                except Exception as e:
                    logger.debug(
                        "[ControlService] Could not reserve bus for Inv ID %s: %s",
                        getattr(inv, "id", None),
                        e,
                    )
                    continue
                arbiter = getattr(transport, "arbiter", None)
                if arbiter is not None and id(arbiter) not in seen:
                    seen.add(id(arbiter))
                    stack.enter_context(arbiter.operation("control"))
            yield

    # =====================================================
    # EVN Priority Lock API
    # =====================================================
    def set_evn_lock(self, project_id: int, lock_p: bool = False, lock_q: bool = False):
        """Đặt/gỡ khóa EVN cho project. Gọi từ EVNCommandWorker."""
        with self._evn_lock:
            if lock_p:
                self._evn_p_locked.add(project_id)
                logger.info(f"[ControlService] EVN LOCK P for project {project_id}")
            else:
                self._evn_p_locked.discard(project_id)
                logger.info(f"[ControlService] EVN UNLOCK P for project {project_id}")

            if lock_q:
                self._evn_q_locked.add(project_id)
                logger.info(f"[ControlService] EVN LOCK Q for project {project_id}")
            else:
                self._evn_q_locked.discard(project_id)
                logger.info(f"[ControlService] EVN UNLOCK Q for project {project_id}")

    def is_evn_locked_p(self, project_id: int) -> bool:
        with self._evn_lock:
            return project_id in self._evn_p_locked

    def is_evn_locked_q(self, project_id: int) -> bool:
        with self._evn_lock:
            return project_id in self._evn_q_locked

    @staticmethod
    def _clamp_percent(pct: float) -> float:
        return max(0.0, min(100.0, float(pct)))

    @staticmethod
    def _inverter_rated_kw(inv) -> float:
        r = getattr(inv, "rate_ac_kw", None)
        if r is not None and r > 0:
            return float(r)
        c = getattr(inv, "capacity_kw", None)
        if c is not None and c > 0:
            return float(c)
        return 0.0

    def _resolve_inv_comm_id(self, inv) -> Optional[int]:
        comm_id = getattr(inv, "comm_id", None)
        if isinstance(comm_id, int):
            return comm_id
        if isinstance(comm_id, str) and comm_id.isdigit():
            return int(comm_id)

        try:
            inv_id = getattr(inv, "id", None)
            if inv_id and hasattr(self.polling_service, "project_svc") and self.polling_service.project_svc and self.polling_service.project_svc.metadata_db:
                db_inv = self.polling_service.project_svc.metadata_db.get_inverter_by_id(inv_id)
                if db_inv and isinstance(db_inv.comm_id, int):
                    return db_inv.comm_id
        except Exception as e:
            logger.warning("[ControlService] Error resolving DB comm_id for Inv ID %s: %s", getattr(inv, "id", None), e)

        return None

    def _collect_read_power_w_map(self, inverters: List[Any]) -> Optional[Dict[int, int]]:
        """Read power for every target; return None if any reading is unavailable."""
        out: Dict[int, int] = {}
        for inv in inverters:
            comm_id = self._resolve_inv_comm_id(inv)
            transport = self.polling_service._get_transport(comm_id)
            driver = self.polling_service._get_driver(inv.brand, transport, inv.slave_id, getattr(inv, "model", None))
            if not driver or not hasattr(driver, "read_power"):
                logger.warning(
                    "[ControlService] Inv ID %s: driver missing read_power(); aborting MAXP allocation",
                    inv.id,
                )
                return None
            try:
                with transport.arbiter.operation("control"):
                    out[inv.id] = int(driver.read_power())
            except Exception as e:
                logger.warning(
                    "[ControlService] Inv ID %s read_power failed: %s; aborting MAXP allocation",
                    inv.id,
                    e,
                )
                return None
        return out

    def _build_maxp_setpoints_kw(
        self,
        inverters: List[Any],
        limit_watts: float,
        power_w_by_id: Dict[int, int],
    ) -> Dict[int, float]:
        total_kw = float(limit_watts) / 1000.0
        if total_kw < 0:
            total_kw = 0.0
        n = len(inverters)
        if n == 0:
            return {}

        eps = float(settings.PROJECT_MAXP_POWER_WEIGHT_EPS_W)
        weights = [max(0, int(power_w_by_id.get(inv.id, 0))) for inv in inverters]
        w_sum = float(sum(weights))

        if w_sum > eps:
            basis = "measured_power_w"
            use_weights = [float(x) for x in weights]
        else:
            basis = "rated_kw"
            rates = [self._inverter_rated_kw(inv) for inv in inverters]
            r_sum = sum(rates)
            if r_sum > 0:
                use_weights = rates
            else:
                basis = "equal_split"
                use_weights = [1.0] * n
            w_sum = sum(use_weights)

        logger.debug(
            "[ControlService] MAXP allocate basis=%s total_kw=%.4f w_sum=%.4f",
            basis,
            total_kw,
            w_sum,
        )

        denom = w_sum if w_sum > 0 else 1.0
        out: Dict[int, float] = {}
        allocated = 0.0
        for i, inv in enumerate(inverters[:-1]):
            share = total_kw * (use_weights[i] / denom)
            kw = max(0.0, round(share, 4))
            out[inv.id] = kw
            allocated += kw
        last = inverters[-1]
        out[last.id] = max(0.0, round(total_kw - allocated, 4))
        return out

    def _apply_single_inverter_limits(
        self,
        inv,
        mode: str,
        limit_watts: Optional[float],
        limit_percent: Optional[float],
        schedule_id: int,
        *,
        do_post_log: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        comm_id = self._resolve_inv_comm_id(inv)
        transport = self.polling_service._get_transport(comm_id)
        driver = self.polling_service._get_driver(inv.brand, transport, inv.slave_id, getattr(inv, "model", None))

        if not driver:
            logger.error(f"[ControlService] No driver resolved for inverter {inv.id} ({inv.brand}).")
            return False, None

        try:
            with transport.arbiter.operation("control"):
                if mode == "MAXP" and limit_watts is not None:
                    method_name = None
                    command_ok = False
                    kw = float(limit_watts) / 1000.0

                    if hasattr(driver, "control_P"):
                        method_name = "control_P"
                        command_ok = bool(driver.control_P(kw))
                    elif hasattr(driver, "set_power_kw"):
                        method_name = "set_power_kw"
                        command_ok = bool(driver.set_power_kw(kw))
                    elif hasattr(driver, "write_power_limit_kw"):
                        method_name = "write_power_limit_kw"
                        enable_ok = True
                        if hasattr(driver, "enable_power_limit"):
                            enable_ok = bool(driver.enable_power_limit(True))
                        command_ok = enable_ok and bool(driver.write_power_limit_kw(kw))
                    elif hasattr(driver, "set_power_w"):
                        method_name = "set_power_w"
                        command_ok = bool(driver.set_power_w(float(limit_watts)))

                    if not method_name:
                        logger.error(
                            "[ControlService] Driver %s does not support MAXP control for Inv ID %s",
                            driver.__class__.__name__,
                            inv.id,
                        )
                        return False, None
                    if not command_ok:
                        logger.error(
                            "[ControlService] Driver %s failed MAXP control for Inv ID %s",
                            driver.__class__.__name__,
                            inv.id,
                        )
                        return False, None
                    logger.info(
                        "[ControlService] Set %.1fW cho Inv ID %s via %s (schedule %s)",
                        limit_watts,
                        inv.id,
                        method_name,
                        schedule_id,
                    )
                    if do_post_log:
                        self._schedule_post_control_power_log(inv, schedule_id)
                    return True, method_name

                if mode in ("PERCENT", "LIMIT_PERCENT") and limit_percent is not None:
                    pct = self._clamp_percent(limit_percent)
                    method_name = None
                    command_ok = False

                    if hasattr(driver, "control_percent"):
                        method_name = "control_percent"
                        command_ok = bool(driver.control_percent(pct))
                    elif hasattr(driver, "set_power_percent"):
                        method_name = "set_power_percent"
                        command_ok = bool(driver.set_power_percent(pct))
                    elif hasattr(driver, "write_power_limit_percent"):
                        method_name = "write_power_limit_percent"
                        enable_ok = True
                        if hasattr(driver, "enable_power_limit"):
                            enable_ok = bool(driver.enable_power_limit(True))
                        command_ok = enable_ok and bool(driver.write_power_limit_percent(pct))

                    if not method_name:
                        logger.error(
                            "[ControlService] Driver %s does not support PERCENT for Inv ID %s",
                            driver.__class__.__name__,
                            inv.id,
                        )
                        return False, None
                    if not command_ok:
                        logger.error(
                            "[ControlService] Driver %s failed PERCENT for Inv ID %s",
                            driver.__class__.__name__,
                            inv.id,
                        )
                        return False, None
                    logger.info(
                        "[ControlService] Set %s%% cho Inv ID %s via %s (schedule %s)",
                        pct,
                        inv.id,
                        method_name,
                        schedule_id,
                    )
                    if do_post_log:
                        self._schedule_post_control_power_log(inv, schedule_id)
                    return True, method_name

                logger.error(
                    "[ControlService] Unsupported payload mode=%s limit_watts=%s limit_percent=%s",
                    mode,
                    limit_watts,
                    limit_percent,
                )
                return False, None
        except Exception as e:
            logger.error(f"[ControlService] Modbus write fail on Inv {inv.id}: {e}")
            return False, None

    def _write_maxp_setpoints_kw(
        self,
        inverters: List[Any],
        setpoints_kw: Dict[int, float],
        schedule_id: int,
    ) -> bool:
        ok_all = True
        for inv in inverters:
            kw = setpoints_kw.get(inv.id, 0.0)
            watts = kw * 1000.0
            ok, _ = self._apply_single_inverter_limits(
                inv,
                "MAXP",
                watts,
                None,
                schedule_id,
                do_post_log=False,
            )
            if not ok:
                ok_all = False
        return ok_all

    def _project_maxp_loop_worker(
        self,
        schedule_id: int,
        project_id: int,
        limit_watts: float,
        stop_event: threading.Event,
    ) -> None:
        interval = max(1, int(settings.PROJECT_MAXP_CONTROL_INTERVAL_SEC))
        try:
            while not stop_event.is_set():
                if stop_event.wait(timeout=interval):
                    break
                project_item = self._find_project_item(project_id)
                if not project_item:
                    logger.error(
                        "[ControlService] PROJECT MAXP loop schedule=%s: project %s missing from config",
                        schedule_id,
                        project_id,
                    )
                    break
                inverters = self._active_inverters(project_item)
                if not inverters:
                    logger.error(
                        "[ControlService] PROJECT MAXP loop schedule=%s: no active inverters",
                        schedule_id,
                    )
                    break
                with self._control_priority_for(inverters):
                    power_map = self._collect_read_power_w_map(inverters)
                    if power_map is None:
                        logger.error("[ControlService] PROJECT MAXP tick schedule=%s aborted: power read failed", schedule_id)
                        continue
                    sp = self._build_maxp_setpoints_kw(inverters, limit_watts, power_map)
                    logger.info(
                        "[ControlService] PROJECT MAXP tick schedule=%s project=%s powers=%s setpoints_kw=%s",
                        schedule_id,
                        project_id,
                        power_map,
                        {iid: round(sp.get(iid, 0), 4) for iid in sp},
                    )
                    self._write_maxp_setpoints_kw(inverters, sp, schedule_id)
        finally:
            with self._project_maxp_lock:
                self._project_maxp_stop_events.pop(schedule_id, None)

    def _start_project_maxp_loop(
        self,
        schedule_id: int,
        project_id: int,
        limit_watts: float,
    ) -> None:
        with self._project_maxp_lock:
            if schedule_id in self._project_maxp_stop_events:
                logger.warning(
                    "[ControlService] PROJECT MAXP loop already running for schedule=%s",
                    schedule_id,
                )
                return
            stop_event = threading.Event()
            self._project_maxp_stop_events[schedule_id] = stop_event

        thread = threading.Thread(
            target=self._project_maxp_loop_worker,
            args=(schedule_id, project_id, float(limit_watts), stop_event),
            name=f"project_maxp_schedule_{schedule_id}",
            daemon=True,
        )
        thread.start()

    def _find_target_inverters(self, project_item, schedule: ControlScheduleResponse):
        inverters = project_item["inverters"]

        if not schedule.serial_number:
            logger.error(
                "[ControlService] INVERTER scope requires serial_number from server schedule. schedule_id=%s",
                schedule.id,
            )
            return []

        target = [inv for inv in inverters if inv.serial_number == schedule.serial_number]
        if not target:
            logger.error(
                "[ControlService] No local inverter matched serial_number=%s for schedule_id=%s",
                schedule.serial_number,
                schedule.id,
            )
        return target

    def _find_group_inverters(self, project_item, schedule: ControlScheduleResponse):
        """
        Tìm danh sách inverter trong nhóm GROUP dựa trên inverter_ids (Server ID).

        Quy tắc map:
          - inverter_ids là list Server ID của inverter (từ server gửi xuống)
          - So sánh với inv.server_id (primary)

        KHÔNG dùng inverter_indices vì index trên server != slave_id dưới logger.
        """
        all_inverters = project_item.get("inverters", [])

        if not schedule.inverter_ids:
            logger.error(
                "[ControlService] GROUP scope schedule=%s: inverter_ids is empty or null. "
                "Cannot determine group targets.",
                schedule.id,
            )
            return []

        server_ids = set(schedule.inverter_ids)  # list[int] — Server ID của inverter

        # Ưu tiên: map qua inv.server_id
        targets = [inv for inv in all_inverters if getattr(inv, "server_id", None) in server_ids]

        if not targets:
            logger.warning(
                "[ControlService] GROUP scope schedule=%s: No inverter matched by server_id=%s. "
                "Ensure inverters have server_id configured.",
                schedule.id, sorted(server_ids),
            )

        logger.info(
            "[ControlService] GROUP scope schedule=%s: matched %d/%d inverters from server_ids=%s",
            schedule.id, len(targets), len(all_inverters), sorted(server_ids),
        )
        return targets

    def _apply_group_scope(self, project_item, schedule: ControlScheduleResponse) -> bool:
        """Áp dụng lệnh điều khiển cho nhóm inverter GROUP. Các inverter ngoài nhóm không bị ảnh hưởng."""
        group_inverters = self._find_group_inverters(project_item, schedule)
        if not group_inverters:
            logger.error(
                "[ControlService] GROUP scope schedule=%s: no group inverters resolved, aborting apply.",
                schedule.id,
            )
            return False

        if schedule.mode == "MAXP" and schedule.limit_watts is not None:
            # MAXP cho GROUP: phân bổ theo tỉ lệ công suất đo được (1 lần, không loop như PROJECT)
            power_map = self._collect_read_power_w_map(group_inverters)
            if power_map is None:
                logger.error("[ControlService] GROUP MAXP schedule=%s aborted: power read failed", schedule.id)
                return False
            sp = self._build_maxp_setpoints_kw(group_inverters, schedule.limit_watts, power_map)
            for inv in group_inverters:
                logger.info(
                    "[ControlService] GROUP MAXP apply schedule=%s inv=%s server_id=%s rated_kw=%.3f p_w=%s setpoint_kw=%.4f",
                    schedule.id,
                    inv.id,
                    getattr(inv, "server_id", None),
                    self._inverter_rated_kw(inv),
                    power_map.get(inv.id),
                    sp.get(inv.id, 0.0),
                )
            return self._write_maxp_setpoints_kw(group_inverters, sp, schedule.id)

        if schedule.mode in ("PERCENT", "LIMIT_PERCENT") and schedule.limit_percent is not None:
            logger.info(
                "[ControlService] GROUP PERCENT apply schedule=%s: %s%% to %d inverters",
                schedule.id, schedule.limit_percent, len(group_inverters),
            )
            return self._apply_inverters(group_inverters, schedule)

        logger.error(
            "[ControlService] Unsupported GROUP schedule: mode=%s limit_watts=%s limit_percent=%s",
            schedule.mode, schedule.limit_watts, schedule.limit_percent,
        )
        return False

    def _reset_group_scope(self, project_item, schedule: ControlScheduleResponse) -> bool:
        """Chỉ reset (100%) các inverter trong nhóm GROUP. Inverter ngoài nhóm không bị ảnh hưởng."""
        group_inverters = self._find_group_inverters(project_item, schedule)
        if not group_inverters:
            logger.error(
                "[ControlService] GROUP scope schedule=%s: no group inverters resolved, aborting reset.",
                schedule.id,
            )
            return False
        logger.info(
            "[ControlService] GROUP reset schedule=%s: resetting %d inverters to 100%%",
            schedule.id, len(group_inverters),
        )
        return self._reset_inverters(group_inverters)

    def _apply_project_scope(self, project_item, schedule: ControlScheduleResponse) -> bool:
        inverters = self._active_inverters(project_item)
        if not inverters:
            logger.error(
                "[ControlService] PROJECT scope schedule=%s: no active inverters",
                schedule.id,
            )
            return False

        if schedule.mode == "MAXP" and schedule.limit_watts is not None:
            power_map = self._collect_read_power_w_map(inverters)
            if power_map is None:
                logger.error("[ControlService] PROJECT MAXP schedule=%s aborted: power read failed", schedule.id)
                return False
            sp = self._build_maxp_setpoints_kw(inverters, schedule.limit_watts, power_map)
            for inv in inverters:
                rated = self._inverter_rated_kw(inv)
                logger.info(
                    "[ControlService] PROJECT MAXP apply schedule=%s inv=%s serial=%s rated_kw=%.3f p_w=%s setpoint_kw=%.4f",
                    schedule.id,
                    inv.id,
                    getattr(inv, "serial_number", None),
                    rated,
                    power_map.get(inv.id),
                    sp.get(inv.id, 0.0),
                )
            if not self._write_maxp_setpoints_kw(inverters, sp, schedule.id):
                return False
            self._start_project_maxp_loop(
                schedule.id,
                schedule.project_id,
                float(schedule.limit_watts),
            )
            return True

        if schedule.mode in ("PERCENT", "LIMIT_PERCENT") and schedule.limit_percent is not None:
            pct = self._clamp_percent(schedule.limit_percent)
            success = True
            for inv in inverters:
                ok, _ = self._apply_single_inverter_limits(
                    inv,
                    "PERCENT",
                    None,
                    pct,
                    schedule.id,
                    do_post_log=True,
                )
                if not ok:
                    success = False
            return success

        logger.error(
            "[ControlService] Unsupported PROJECT schedule: mode=%s limit_watts=%s limit_percent=%s",
            schedule.mode,
            schedule.limit_watts,
            schedule.limit_percent,
        )
        return False

    def _reset_project_scope(self, project_item, schedule: ControlScheduleResponse) -> bool:
        self._stop_project_maxp_loop(schedule.id)
        inverters = self._active_inverters(project_item)
        if not inverters:
            return False
        return self._reset_inverters(inverters)

    def _read_inverter_power(self, driver):
        if hasattr(driver, "read_power"):
            return driver.read_power()

        if hasattr(driver, "read_all"):
            snapshot = driver.read_all() or {}
            if "p_inv_w" in snapshot:
                return snapshot["p_inv_w"]

        raise AttributeError(f"Driver {driver.__class__.__name__} has no supported power read method")

    def _schedule_post_control_power_log(self, inv, schedule_id: int):
        def worker():
            try:
                time.sleep(self.post_control_readback_delay_sec)

                transport = self.polling_service._get_transport(getattr(inv, "comm_id", None))
                driver = self.polling_service._get_driver(inv.brand, transport, inv.slave_id, getattr(inv, "model", None))
                if not driver:
                    logger.error(
                        "[ControlService] Cannot read back power for Inv ID %s after schedule %s because driver is unavailable.",
                        inv.id,
                        schedule_id,
                    )
                    return

                with transport.arbiter.operation("control"):
                    power_w = self._read_inverter_power(driver)

                logger.info(
                    "[ControlService] Power readback after %.1fs for Inv ID %s (schedule %s, slave_id=%s, serial=%s): %s W",
                    self.post_control_readback_delay_sec,
                    inv.id,
                    schedule_id,
                    inv.slave_id,
                    getattr(inv, "serial_number", None),
                    power_w,
                )
            except Exception as e:
                logger.error(
                    "[ControlService] Failed to read back power after schedule %s for Inv ID %s: %s",
                    schedule_id,
                    inv.id,
                    e,
                )

        threading.Thread(
            target=worker,
            name=f"post_control_power_inv_{inv.id}_schedule_{schedule_id}",
            daemon=True,
        ).start()

    def _apply_inverters(self, target_inverters, schedule: ControlScheduleResponse) -> bool:
        success = True
        for inv in target_inverters:
            if schedule.mode == "MAXP" and schedule.limit_watts is not None:
                ok, _ = self._apply_single_inverter_limits(
                    inv,
                    "MAXP",
                    schedule.limit_watts,
                    None,
                    schedule.id,
                    do_post_log=True,
                )
                if not ok:
                    success = False
            elif schedule.mode in ("PERCENT", "LIMIT_PERCENT") and schedule.limit_percent is not None:
                ok, _ = self._apply_single_inverter_limits(
                    inv,
                    "PERCENT",
                    None,
                    schedule.limit_percent,
                    schedule.id,
                    do_post_log=True,
                )
                if not ok:
                    success = False
            else:
                logger.error(
                    "[ControlService] Unsupported inverter schedule payload: mode=%s limit_watts=%s limit_percent=%s",
                    schedule.mode,
                    schedule.limit_watts,
                    schedule.limit_percent,
                )
                success = False
        return success

    def _reset_inverters(self, target_inverters) -> bool:
        success = True
        for inv in target_inverters:
            transport = self.polling_service._get_transport(getattr(inv, "comm_id", None))
            driver = self.polling_service._get_driver(inv.brand, transport, inv.slave_id, getattr(inv, "model", None))
            if not driver:
                logger.error(f"[ControlService] No driver resolved for inverter {inv.id} ({inv.brand}) during reset.")
                success = False
                continue

            try:
                with transport.arbiter.operation("control"):
                    method_name = None
                    command_ok = False

                    if hasattr(driver, "control_percent"):
                        method_name = "control_percent"
                        command_ok = bool(driver.control_percent(100.0))
                    elif hasattr(driver, "set_power_percent"):
                        method_name = "set_power_percent"
                        command_ok = bool(driver.set_power_percent(100.0))
                    elif hasattr(driver, "write_power_limit_percent"):
                        method_name = "write_power_limit_percent"
                        enable_ok = True
                        if hasattr(driver, "enable_power_limit"):
                            enable_ok = bool(driver.enable_power_limit(True))
                        command_ok = enable_ok and bool(driver.write_power_limit_percent(100.0))

                    if not method_name:
                        logger.error(
                            "[ControlService] Driver %s does not support reset by percent for Inv ID %s",
                            driver.__class__.__name__,
                            inv.id,
                        )
                        success = False
                        continue
                    if not command_ok:
                        logger.error(
                            "[ControlService] Driver %s failed reset by percent for Inv ID %s",
                            driver.__class__.__name__,
                            inv.id,
                        )
                        success = False
                        continue
                logger.info(f"[ControlService] Reset to 100 percent limit cho Inv ID {inv.id} via {method_name}")
            except Exception as e:
                logger.error(f"[ControlService] Reset Modbus fail limit Inv {inv.id}: {e}")
                success = False

        return success

    def apply(self, schedule: ControlScheduleResponse):
        """Thực hiện lệnh điều khiển từ Server/MQTT. Kiểm tra EVN lock trước."""
        logger.info(f"[ControlService] Applying schedule: {schedule.id}")

        try:
            project_item = self._find_project_item(schedule.project_id)

            if not project_item:
                logger.error(f"[ControlService] Project {schedule.project_id} not found in polling config.")
                return False

            # --- Kiểm tra EVN Priority Lock ---
            local_project_id = project_item["project"].id
            mode = getattr(schedule, 'mode', '')
            is_p_control = mode in ('MAXP', 'PERCENT')
            is_q_control = mode in ('LIMIT_Q_PERCENT', 'LIMIT_Q_KVAR')

            if is_p_control and self.is_evn_locked_p(local_project_id):
                logger.warning(
                    "[ControlService] BLOCKED schedule %s (mode=%s) for project %s (local_id=%s) — EVN is controlling P axis.",
                    schedule.id, mode, schedule.project_id, local_project_id,
                )
                return False

            if is_q_control and self.is_evn_locked_q(local_project_id):
                logger.warning(
                    "[ControlService] BLOCKED schedule %s (mode=%s) for project %s (local_id=%s) — EVN is controlling Q axis.",
                    schedule.id, mode, schedule.project_id, local_project_id,
                )
                return False

            if schedule.scope == "PROJECT":
                targets = self._active_inverters(project_item)
                with self._control_priority_for(targets):
                    return self._apply_project_scope(project_item, schedule)
            elif schedule.scope == "GROUP":
                targets = self._find_group_inverters(project_item, schedule)
                with self._control_priority_for(targets):
                    return self._apply_group_scope(project_item, schedule)

            target_inverters = self._find_target_inverters(project_item, schedule)

            if not target_inverters:
                logger.error(
                    "[ControlService] No target inverters found for schedule. serial_number=%s",
                    schedule.serial_number,
                )
                return False

            with self._control_priority_for(target_inverters):
                return self._apply_inverters(target_inverters, schedule)

        except Exception as e:
            logger.error(f"[ControlService] Error apply schedule: {e}")
            return False

    def reset(self, schedule: ControlScheduleResponse):
        """Reset lệnh điều khiển từ Server/MQTT. Kiểm tra EVN lock trước."""
        logger.info(f"[ControlService] Resetting limit for schedule: {schedule.id}")
        try:
            project_item = self._find_project_item(schedule.project_id)

            if not project_item:
                return False

            # --- Kiểm tra EVN Priority Lock khi reset ---
            local_project_id = project_item["project"].id
            mode = getattr(schedule, 'mode', '')
            is_p_control = mode in ('MAXP', 'PERCENT')
            is_q_control = mode in ('LIMIT_Q_PERCENT', 'LIMIT_Q_KVAR')

            if is_p_control and self.is_evn_locked_p(local_project_id):
                logger.warning(
                    "[ControlService] BLOCKED reset schedule %s for project %s (local_id=%s) — EVN is controlling P axis.",
                    schedule.id, schedule.project_id, local_project_id,
                )
                return False

            if is_q_control and self.is_evn_locked_q(local_project_id):
                logger.warning(
                    "[ControlService] BLOCKED reset schedule %s for project %s (local_id=%s) — EVN is controlling Q axis.",
                    schedule.id, schedule.project_id, local_project_id,
                )
                return False

            if schedule.scope == "PROJECT":
                targets = self._active_inverters(project_item)
                with self._control_priority_for(targets):
                    return self._reset_project_scope(project_item, schedule)
            elif schedule.scope == "GROUP":
                targets = self._find_group_inverters(project_item, schedule)
                with self._control_priority_for(targets):
                    return self._reset_group_scope(project_item, schedule)
            elif schedule.scope == "INVERTER":
                target_inverters = self._find_target_inverters(project_item, schedule)
                if not target_inverters:
                    logger.error(
                        "[ControlService] No target inverters found for reset. serial_number=%s",
                        schedule.serial_number,
                    )
                    return False

                with self._control_priority_for(target_inverters):
                    return self._reset_inverters(target_inverters)
            else:
                logger.warning(f"[ControlService] Unsupported scope for reset: {schedule.scope}")
                return False

        except Exception as e:
            logger.error(f"[ControlService] Error reset limit: {e}")
            return False

    # =====================================================
    # EVN Control Methods (Granular P/Q)
    # =====================================================
    def apply_evn_p_control(self, project_id: int, mode: str, value: float) -> bool:
        """
        Áp dụng lệnh điều khiển P từ EVN.
        
        Args:
            project_id: ID dự án
            mode: "PERCENT" hoặc "KW"
            value: Giá trị setpoint
        """
        try:
            project_item = self._find_project_item(project_id)
            if not project_item:
                logger.error("[ControlService] EVN P: project %s not found", project_id)
                return False

            # Tạo pseudo-schedule để tái sử dụng logic phân bổ
            from types import SimpleNamespace
            pseudo_schedule = SimpleNamespace(
                id=-1,
                project_id=project_id,
                scope="PROJECT",
                mode="LIMIT_PERCENT" if mode == "PERCENT" else "MAXP",
                limit_percent=value if mode == "PERCENT" else None,
                limit_watts=value * 1000.0 if mode == "KW" else None,
                serial_number=None,
            )

            if mode not in ("PERCENT", "KW"):
                logger.warning("[ControlService] EVN P: Unknown mode %s", mode)
                return False
            with self._control_priority_for(self._active_inverters(project_item)):
                result = self._apply_project_scope(project_item, pseudo_schedule)

            logger.info(
                "[ControlService] EVN P control applied: mode=%s value=%.2f project=%s result=%s",
                mode, value, project_id, result,
            )
            return result

        except Exception as e:
            logger.error("[ControlService] EVN P control error: %s", e, exc_info=True)
            return False

    def apply_evn_q_control(self, project_id: int, mode: str, value: float) -> bool:
        """
        Áp dụng lệnh điều khiển Q từ EVN.
        
        Args:
            project_id: ID dự án
            mode: "PERCENT" hoặc "KVAR"
            value: Giá trị setpoint
        
        Note: Cần driver hỗ trợ Q control methods.
              User sẽ cung cấp register map cho từng hãng.
        """
        try:
            project_item = self._find_project_item(project_id)
            if not project_item:
                logger.error("[ControlService] EVN Q: project %s not found", project_id)
                return False

            inverters = project_item.get("inverters", [])
            if not inverters:
                logger.warning("[ControlService] EVN Q: no inverters for project %s", project_id)
                return False

            success_count = 0
            with self._control_priority_for(inverters):
                for inv in inverters:
                    try:
                        transport = self.polling_service._get_transport(inv.comm_id)
                        driver = self.polling_service._get_driver(
                            inv.brand, transport, inv.slave_id, inv.model
                        )
                        if not driver:
                            continue

                        if mode == "PERCENT" and hasattr(driver, "set_reactive_power_percent"):
                            driver.set_reactive_power_percent(value)
                            success_count += 1
                        elif mode == "KVAR" and hasattr(driver, "set_reactive_power_kvar"):
                            driver.set_reactive_power_kvar(value)
                            success_count += 1
                        else:
                            logger.warning(
                                "[ControlService] EVN Q: Driver %s does not support Q control (mode=%s)",
                                type(driver).__name__, mode,
                            )
                    except Exception as e:
                        logger.error("[ControlService] EVN Q error on inv %s: %s", inv.id, e)

            logger.info(
                "[ControlService] EVN Q control: mode=%s value=%.2f success=%d/%d",
                mode, value, success_count, len(inverters),
            )
            return success_count > 0

        except Exception as e:
            logger.error("[ControlService] EVN Q control error: %s", e, exc_info=True)
            return False

    def reset_evn_p_control(self, project_id: int) -> bool:
        """Reset P control khi EVN tắt Enable_Set_P → trả inverter về 100%."""
        try:
            project_item = self._find_project_item(project_id)
            if not project_item:
                return False

            from types import SimpleNamespace
            pseudo_schedule = SimpleNamespace(
                id=-1,
                project_id=project_id,
                scope="PROJECT",
                mode="PERCENT",
                setpoint=100.0,
                serial_number=None,
            )
            with self._control_priority_for(self._active_inverters(project_item)):
                return self._reset_project_scope(project_item, pseudo_schedule)
        except Exception as e:
            logger.error("[ControlService] EVN P reset error: %s", e)
            return False

    def reset_evn_q_control(self, project_id: int) -> bool:
        """Reset Q control khi EVN tắt Enable_Set_Q."""
        try:
            project_item = self._find_project_item(project_id)
            if not project_item:
                return False

            inverters = project_item.get("inverters", [])
            with self._control_priority_for(inverters):
                for inv in inverters:
                    try:
                        transport = self.polling_service._get_transport(inv.comm_id)
                        driver = self.polling_service._get_driver(
                            inv.brand, transport, inv.slave_id, inv.model
                        )
                        if driver and hasattr(driver, "set_reactive_power_percent"):
                            driver.set_reactive_power_percent(0.0)  # Reset Q về 0
                    except Exception as e:
                        logger.error("[ControlService] EVN Q reset error inv %s: %s", inv.id, e)

            logger.info("[ControlService] EVN Q control reset for project %s", project_id)
            return True
        except Exception as e:
            logger.error("[ControlService] EVN Q reset error: %s", e)
            return False
