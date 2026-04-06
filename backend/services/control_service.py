import logging

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

    def apply(self, schedule: ControlScheduleResponse):
        logger.info(f"[ControlService] Applying schedule: {schedule.id}")

        try:
            project_item = self._find_project_item(schedule.project_id)

            if not project_item:
                logger.error(f"[ControlService] Project {schedule.project_id} not found in polling config.")
                return False

            if schedule.scope == "PROJECT":
                target_inverters = project_item["inverters"]
            else:
                target_inverters = [
                    inv for inv in project_item["inverters"]
                    if inv.inverter_index == schedule.inverter_index
                ]

            if not target_inverters:
                logger.error("[ControlService] No target inverters found for schedule.")
                return False

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
                target_inverters = project_item["inverters"]
            else:
                target_inverters = [
                    inv for inv in project_item["inverters"]
                    if inv.inverter_index == schedule.inverter_index
                ]

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
            return True

        except Exception as e:
            logger.error(f"[ControlService] Error reset limit: {e}")
            return False
