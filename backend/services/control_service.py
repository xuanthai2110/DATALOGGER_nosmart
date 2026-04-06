import logging

from backend.drivers.smartloggerHuawei import SmartLoggerHuawei
from backend.models.schedule import ControlScheduleResponse


logger = logging.getLogger(__name__)


class ControlService:
    def __init__(self, polling_service):
        self.polling_service = polling_service

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

    def _apply_inverters(self, target_inverters, schedule: ControlScheduleResponse) -> bool:
        success = True
        for inv in target_inverters:
            transport = self.polling_service._get_transport(inv.brand)
            driver = self.polling_service._get_driver(inv.brand, transport, inv.slave_id)

            if not driver:
                continue

            try:
                with transport.arbiter.operation("control"):
                    if schedule.mode == "MAXP" and schedule.limit_watts is not None:
                        if hasattr(driver, "control_P"):
                            driver.control_P(schedule.limit_watts / 1000.0)
                        elif hasattr(driver, "set_power_w"):
                            driver.set_power_w(schedule.limit_watts)
                        elif hasattr(driver, "set_power_kw"):
                            driver.set_power_kw(schedule.limit_watts / 1000.0)
                        logger.info(f"[ControlService] Set {schedule.limit_watts}W cho Inv ID {inv.id}")

                    elif schedule.mode == "LIMIT_PERCENT" and schedule.limit_percent is not None:
                        if hasattr(driver, "control_percent"):
                            driver.control_percent(schedule.limit_percent)
                        elif hasattr(driver, "set_power_percent"):
                            driver.set_power_percent(schedule.limit_percent)
                        logger.info(f"[ControlService] Set {schedule.limit_percent} percent cho Inv ID {inv.id}")
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
                continue

            try:
                with transport.arbiter.operation("control"):
                    if hasattr(driver, "control_percent"):
                        driver.control_percent(100.0)
                    elif hasattr(driver, "set_power_percent"):
                        driver.set_power_percent(100.0)
                logger.info(f"[ControlService] Reset to 100 percent limit cho Inv ID {inv.id}")
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

            target_inverters = self._find_target_inverters(project_item, schedule)
            if not target_inverters:
                logger.error(
                    "[ControlService] No target inverters found for reset. serial_number=%s",
                    schedule.serial_number,
                )
                return False

            return self._reset_inverters(target_inverters)

        except Exception as e:
            logger.error(f"[ControlService] Error reset limit: {e}")
            return False
