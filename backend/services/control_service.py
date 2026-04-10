import logging
import threading
import time

from backend.drivers.smartloggerHuawei import SmartLoggerHuawei
from backend.models.schedule import ControlScheduleResponse


logger = logging.getLogger(__name__)


class ControlService:
    def __init__(self, polling_service):
        self.polling_service = polling_service
        self.post_control_readback_delay_sec = 10.0

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

    def _get_project_controller(self, project_item):
        inverters = project_item["inverters"]
        if not inverters:
            return None, None

        if not all("Huawei" in (inv.brand or "") for inv in inverters):
            return None, None

        transport = self.polling_service._get_transport(inverters[0].brand)
        controller = SmartLoggerHuawei(transport, slave_id=0)
        return transport, controller

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

    def _apply_project_scope(self, project_item, schedule: ControlScheduleResponse) -> bool:
        transport, controller = self._get_project_controller(project_item)
        if not controller:
            logger.error("[ControlService] PROJECT scope requires SmartLogger controller but none was resolved.")
            return False

        try:
            with transport.arbiter.operation("control"):
                if schedule.mode == "MAXP" and schedule.limit_watts is not None:
                    controller.control_P(schedule.limit_watts / 1000.0)
                    logger.info(
                        f"[ControlService] Set {schedule.limit_watts}W cho PROJECT qua SmartLogger"
                    )
                elif schedule.mode == "LIMIT_PERCENT" and schedule.limit_percent is not None:
                    controller.control_percent(schedule.limit_percent)
                    logger.info(
                        f"[ControlService] Set {schedule.limit_percent} percent cho PROJECT qua SmartLogger"
                    )
                else:
                    logger.error(
                        f"[ControlService] Unsupported schedule payload for PROJECT scope: mode={schedule.mode}"
                    )
                    return False
            return True
        except Exception as e:
            logger.error(f"[ControlService] SmartLogger write fail for PROJECT scope: {e}")
            return False

    def _reset_project_scope(self, project_item) -> bool:
        transport, controller = self._get_project_controller(project_item)
        if not controller:
            logger.error("[ControlService] PROJECT scope reset requires SmartLogger controller but none was resolved.")
            return False

        try:
            with transport.arbiter.operation("control"):
                controller.control_percent(100.0)
            logger.info("[ControlService] Reset PROJECT limit to 100 percent qua SmartLogger")
            return True
        except Exception as e:
            logger.error(f"[ControlService] SmartLogger reset fail for PROJECT scope: {e}")
            return False

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

                transport = self.polling_service._get_transport(inv.brand)
                driver = self.polling_service._get_driver(inv.brand, transport, inv.slave_id)
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
            transport = self.polling_service._get_transport(inv.brand)
            driver = self.polling_service._get_driver(inv.brand, transport, inv.slave_id)

            if not driver:
                logger.error(f"[ControlService] No driver resolved for inverter {inv.id} ({inv.brand}).")
                success = False
                continue

            try:
                with transport.arbiter.operation("control"):
                    if schedule.mode == "MAXP" and schedule.limit_watts is not None:
                        method_name = None
                        command_ok = False

                        if hasattr(driver, "control_P"):
                            method_name = "control_P"
                            command_ok = bool(driver.control_P(schedule.limit_watts / 1000.0))
                        elif hasattr(driver, "set_power_kw"):
                            method_name = "set_power_kw"
                            command_ok = bool(driver.set_power_kw(schedule.limit_watts / 1000.0))
                        elif hasattr(driver, "write_power_limit_kw"):
                            method_name = "write_power_limit_kw"
                            enable_ok = True
                            if hasattr(driver, "enable_power_limit"):
                                enable_ok = bool(driver.enable_power_limit(True))
                            command_ok = enable_ok and bool(driver.write_power_limit_kw(schedule.limit_watts / 1000.0))
                        elif hasattr(driver, "set_power_w"):
                            method_name = "set_power_w"
                            command_ok = bool(driver.set_power_w(schedule.limit_watts))

                        if not method_name:
                            logger.error(
                                "[ControlService] Driver %s does not support MAXP control for Inv ID %s",
                                driver.__class__.__name__,
                                inv.id,
                            )
                            success = False
                            continue
                        if not command_ok:
                            logger.error(
                                "[ControlService] Driver %s failed MAXP control for Inv ID %s",
                                driver.__class__.__name__,
                                inv.id,
                            )
                            success = False
                            continue
                        logger.info(
                            "[ControlService] Set %sW cho Inv ID %s via %s",
                            schedule.limit_watts,
                            inv.id,
                            method_name,
                        )
                        self._schedule_post_control_power_log(inv, schedule.id)

                    elif schedule.mode == "LIMIT_PERCENT" and schedule.limit_percent is not None:
                        method_name = None
                        command_ok = False

                        if hasattr(driver, "control_percent"):
                            method_name = "control_percent"
                            command_ok = bool(driver.control_percent(schedule.limit_percent))
                        elif hasattr(driver, "set_power_percent"):
                            method_name = "set_power_percent"
                            command_ok = bool(driver.set_power_percent(schedule.limit_percent))
                        elif hasattr(driver, "write_power_limit_percent"):
                            method_name = "write_power_limit_percent"
                            enable_ok = True
                            if hasattr(driver, "enable_power_limit"):
                                enable_ok = bool(driver.enable_power_limit(True))
                            command_ok = enable_ok and bool(driver.write_power_limit_percent(schedule.limit_percent))

                        if not method_name:
                            logger.error(
                                "[ControlService] Driver %s does not support LIMIT_PERCENT control for Inv ID %s",
                                driver.__class__.__name__,
                                inv.id,
                            )
                            success = False
                            continue
                        if not command_ok:
                            logger.error(
                                "[ControlService] Driver %s failed LIMIT_PERCENT control for Inv ID %s",
                                driver.__class__.__name__,
                                inv.id,
                            )
                            success = False
                            continue
                        logger.info(
                            "[ControlService] Set %s percent cho Inv ID %s via %s",
                            schedule.limit_percent,
                            inv.id,
                            method_name,
                        )
                        self._schedule_post_control_power_log(inv, schedule.id)
                    else:
                        logger.error(
                            "[ControlService] Unsupported inverter schedule payload: mode=%s limit_watts=%s limit_percent=%s",
                            schedule.mode,
                            schedule.limit_watts,
                            schedule.limit_percent,
                        )
                        success = False
            except Exception as e:
                logger.error(f"[ControlService] Modbus write fail on Inv {inv.id}: {e}")
                success = False

        return success

    def _reset_inverters(self, target_inverters) -> bool:
        success = True
        for inv in target_inverters:
            transport = self.polling_service._get_transport(inv.brand)
            driver = self.polling_service._get_driver(inv.brand, transport, inv.slave_id)
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
        logger.info(f"[ControlService] Applying schedule: {schedule.id}")

        try:
            project_item = self._find_project_item(schedule.project_id)

            if not project_item:
                logger.error(f"[ControlService] Project {schedule.project_id} not found in polling config.")
                return False

            if schedule.scope == "PROJECT":
                return self._apply_project_scope(project_item, schedule)

            target_inverters = self._find_target_inverters(project_item, schedule)

            if not target_inverters:
                logger.error(
                    "[ControlService] No target inverters found for schedule. serial_number=%s",
                    schedule.serial_number,
                )
                return False

            return self._apply_inverters(target_inverters, schedule)

        except Exception as e:
            logger.error(f"[ControlService] Error apply schedule: {e}")
            return False

    def reset(self, schedule: ControlScheduleResponse):
        logger.info(f"[ControlService] Resetting limit for schedule: {schedule.id}")
        try:
            project_item = self._find_project_item(schedule.project_id)

            if not project_item:
                return False

            if schedule.scope == "PROJECT":
                return self._reset_project_scope(project_item)
            elif schedule.scope == "INVERTER":
                target_inverters = self._find_target_inverters(project_item, schedule)
                if not target_inverters:
                    logger.error(
                        "[ControlService] No target inverters found for reset. serial_number=%s",
                        schedule.serial_number,
                    )
                    return False

                return self._reset_inverters(target_inverters)
            else:
                logger.warning(f"[ControlService] Unsupported scope for reset: {schedule.scope}")
                return False

        except Exception as e:
            logger.error(f"[ControlService] Error reset limit: {e}")
            return False
