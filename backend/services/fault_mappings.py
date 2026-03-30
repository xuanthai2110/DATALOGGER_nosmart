# backend/services/fault_mappings.py

UNIFIED_STATES = {
    1: "RUNNING", 2: "STANDBY", 3: "STARTING", 4: "STOPPED", 5: "FAULT",
    6: "ALARM_RUNNING", 7: "DERATING", 8: "DISPATCH_RUNNING", 9: "COMMUNICATION_FAULT",
    10: "EMERGENCY_STOP", 11: "KEY_STOP", 12: "INITIAL_STANDBY", 13: "GRID_DETECTING",
    14: "INSULATION_CHECK", 15: "SELF_CHECK", 16: "OFF_GRID_RUNNING", 17: "MAINTENANCE_MODE",
    18: "UPGRADING", 19: "SHUTTING_DOWN", 20: "POWER_LIMITED", 21: "GRID_FAULT_WAIT", 22: "SLEEP"
}

UNIFIED_FAULTS = {
    # GRID
    1001: "GRID_OVERVOLTAGE", 1002: "GRID_TRANSIENT_OVERVOLTAGE", 1003: "GRID_UNDERVOLTAGE",
    1004: "GRID_OVERCURRENT", 1005: "GRID_OVER_FREQUENCY", 1006: "GRID_UNDER_FREQUENCY",
    1007: "GRID_POWER_OUTAGE", 1008: "GRID_VOLTAGE_UNBALANCE", 1009: "GRID_PHASE_LOSS",
    1010: "GRID_ABNORMAL", 1011: "GRID_10MIN_OVERVOLTAGE", 1012: "GRID_IMPEDANCE_ABNORMAL",
    1013: "GRID_REVERSE_POWER", 1014: "GRID_CONNECTION_LOST", 1015: "GRID_PROTECTION_TRIGGERED",
    # PV
    1101: "PV_REVERSE_CONNECTION", 1102: "PV_OVERVOLTAGE", 1103: "PV_CONFIGURATION_ERROR",
    1104: "PV_INPUT_ABNORMAL", 1105: "PV_STRING_FAULT", 1106: "PV_STRING_LOSS",
    1107: "PV_STRING_IMBALANCE", 1108: "PV_LOW_VOLTAGE", 1109: "PV_DC_BUS_OVERVOLTAGE",
    1110: "PV_DC_BUS_UNDERVOLTAGE",
    # ELECTRICAL
    1201: "LEAKAGE_CURRENT", 1202: "LOW_INSULATION_RESISTANCE", 1203: "AC_OVERLOAD",
    1204: "AC_SHORT_CIRCUIT", 1205: "DC_OVER_CURRENT", 1206: "GROUND_FAULT",
    1207: "RESIDUAL_CURRENT_FAULT", 1208: "DC_COMPONENT_HIGH", 1209: "DC_INJECTION_HIGH",
    # TEMPERATURE
    1301: "DEVICE_OVER_TEMPERATURE", 1302: "AMBIENT_OVER_TEMPERATURE", 1303: "AMBIENT_LOW_TEMPERATURE",
    1304: "HEATSINK_OVER_TEMPERATURE", 1305: "MODULE_OVER_TEMPERATURE",
    # HARDWARE
    1401: "FAN_FAULT", 1402: "AC_SPD_FAULT", 1403: "DC_SPD_FAULT", 1404: "RELAY_FAULT",
    1405: "CONTACTOR_FAULT", 1406: "SENSOR_FAULT", 1407: "EEPROM_FAULT",
    1408: "INTERNAL_COMMUNICATION_FAULT", 1409: "CONTROL_BOARD_FAULT", 1410: "POWER_MODULE_FAULT",
    # COMMUNICATION
    1501: "COMMUNICATION_FAULT", 1502: "METER_COMMUNICATION_FAULT", 1503: "RS485_COMMUNICATION_FAULT",
    1504: "MODBUS_COMMUNICATION_FAULT", 1505: "ETHERNET_COMMUNICATION_FAULT", 1506: "CLOUD_COMMUNICATION_FAULT",
    # SAFETY
    1601: "ARC_FAULT", 1602: "ARC_DETECTION_DISABLED", 1603: "RAPID_SHUTDOWN_TRIGGERED",
    1604: "FIRE_PROTECTION_TRIGGERED", 1605: "EMERGENCY_STOP_TRIGGERED",
    # SYSTEM
    1701: "DEVICE_ABNORMAL", 1702: "GRID_PROTECTION_SELF_CHECK_FAILURE", 1703: "SYSTEM_SELF_CHECK_FAILURE",
    1704: "SOFTWARE_EXCEPTION", 1705: "FIRMWARE_UPGRADE_FAILURE", 1706: "CONFIGURATION_ERROR",
    # DERATING
    1801: "POWER_DERATING", 1802: "TEMPERATURE_DERATING", 1803: "GRID_LIMIT_DERATING",
    1804: "FREQUENCY_DERATING", 1805: "POWER_LIMIT_CONTROL",
}

SUNGROW_FAULT_MAP = {
    1: {"id_sungrow": 1, "id_unified": 1001, "name": "GRID_OVERVOLTAGE", "severity": "ERROR", "repair_instruction": "Check grid voltage and transformer tap setting."},
    2: {"id_sungrow": 2, "id_unified": 1003, "name": "GRID_UNDERVOLTAGE", "severity": "ERROR", "repair_instruction": "Check grid voltage level and cable connection."},
    3: {"id_sungrow": 3, "id_unified": 1005, "name": "GRID_OVERFREQUENCY", "severity": "ERROR", "repair_instruction": "Check grid frequency stability."},
    4: {"id_sungrow": 4, "id_unified": 1006, "name": "GRID_UNDERFREQUENCY", "severity": "ERROR", "repair_instruction": "Check utility grid frequency."},
    5: {"id_sungrow": 5, "id_unified": 1007, "name": "GRID_LOSS", "severity": "ERROR", "repair_instruction": "Check AC breaker and grid cable."},
    6: {"id_sungrow": 6, "id_unified": 1009, "name": "GRID_PHASE_FAULT", "severity": "ERROR", "repair_instruction": "Check phase sequence and wiring."},
    10: {"id_sungrow": 10, "id_unified": 1102, "name": "DC_OVERVOLTAGE", "severity": "ERROR", "repair_instruction": "Check PV string voltage."},
    11: {"id_sungrow": 11, "id_unified": 1202, "name": "DC_INSULATION_FAULT", "severity": "ERROR", "repair_instruction": "Check insulation resistance between PV and ground."},
    12: {"id_sungrow": 12, "id_unified": 1206, "name": "GROUND_FAULT", "severity": "ERROR", "repair_instruction": "Inspect grounding system."},
    13: {"id_sungrow": 13, "id_unified": 1201, "name": "LEAKAGE_CURRENT", "severity": "ERROR", "repair_instruction": "Check residual current leakage."},
    14: {"id_sungrow": 14, "id_unified": 1105, "name": "STRING_FAULT", "severity": "WARNING", "repair_instruction": "Inspect PV string current and connectors."},
    20: {"id_sungrow": 20, "id_unified": 1301, "name": "OVER_TEMPERATURE", "severity": "ERROR", "repair_instruction": "Check inverter cooling and ambient temperature."},
    21: {"id_sungrow": 21, "id_unified": 1401, "name": "FAN_FAULT", "severity": "WARNING", "repair_instruction": "Inspect cooling fan."},
    22: {"id_sungrow": 22, "id_unified": 1304, "name": "HEATSINK_OVER_TEMP", "severity": "ERROR", "repair_instruction": "Check heat sink airflow."},
    30: {"id_sungrow": 30, "id_unified": 1701, "name": "HARDWARE_FAULT", "severity": "ERROR", "repair_instruction": "Inspect inverter internal modules."},
    31: {"id_sungrow": 31, "id_unified": 1704, "name": "SOFTWARE_FAULT", "severity": "ERROR", "repair_instruction": "Restart inverter or update firmware."},
    32: {"id_sungrow": 32, "id_unified": 1410, "name": "POWER_MODULE_FAULT", "severity": "ERROR", "repair_instruction": "Check internal power module."},
    33: {"id_sungrow": 33, "id_unified": 1109, "name": "BUS_OVERVOLTAGE", "severity": "ERROR", "repair_instruction": "Check DC bus voltage."},
    34: {"id_sungrow": 34, "id_unified": 1110, "name": "BUS_UNDERVOLTAGE", "severity": "ERROR", "repair_instruction": "Inspect DC bus system."},
    35: {"id_sungrow": 35, "id_unified": 1404, "name": "RELAY_FAULT", "severity": "ERROR", "repair_instruction": "Inspect AC relay."},
    40: {"id_sungrow": 40, "id_unified": 1501, "name": "COMMUNICATION_FAULT", "severity": "DISCONNECT", "repair_instruction": "Check communication module and cable."},
    41: {"id_sungrow": 41, "id_unified": 1503, "name": "RS485_FAULT", "severity": "DISCONNECT", "repair_instruction": "Check RS485 wiring."},
    42: {"id_sungrow": 42, "id_unified": 1505, "name": "WIFI_FAULT", "severity": "DISCONNECT", "repair_instruction": "Inspect WiFi module."},
    43: {"id_sungrow": 43, "id_unified": 1504, "name": "PLC_FAULT", "severity": "DISCONNECT", "repair_instruction": "Check PLC communication."},
    44: {"id_sungrow": 44, "id_unified": 1502, "name": "METER_COMM_FAULT", "severity": "DISCONNECT", "repair_instruction": "Check smart meter communication."},
    50: {"id_sungrow": 50, "id_unified": 1601, "name": "ARC_FAULT", "severity": "ERROR", "repair_instruction": "Inspect PV cables for arc fault."},
    51: {"id_sungrow": 51, "id_unified": 1402, "name": "SPD_FAULT", "severity": "WARNING", "repair_instruction": "Check surge protection device."},
    52: {"id_sungrow": 52, "id_unified": 1015, "name": "ANTI_ISLANDING_FAULT", "severity": "ERROR", "repair_instruction": "Check grid protection settings."},
    60: {"id_sungrow": 60, "id_unified": 1703, "name": "STARTUP_FAIL", "severity": "ERROR", "repair_instruction": "Restart inverter and verify parameters."},
    61: {"id_sungrow": 61, "id_unified": 1701, "name": "SHUTDOWN_FAULT", "severity": "ERROR", "repair_instruction": "Check shutdown cause."},
    62: {"id_sungrow": 62, "id_unified": 1706, "name": "CONFIGURATION_FAULT", "severity": "ERROR", "repair_instruction": "Verify inverter configuration."},
    70: {"id_sungrow": 70, "id_unified": 1406, "name": "CURRENT_SENSOR_FAULT", "severity": "ERROR", "repair_instruction": "Inspect current sensor."},
    71: {"id_sungrow": 71, "id_unified": 1406, "name": "VOLTAGE_SENSOR_FAULT", "severity": "ERROR", "repair_instruction": "Inspect voltage sensing circuit."},
    72: {"id_sungrow": 72, "id_unified": 1406, "name": "TEMPERATURE_SENSOR_FAULT", "severity": "ERROR", "repair_instruction": "Inspect temperature sensor."},
}

SUNGROW_STATE_MAP = {
    0: {"id_sungrow": 0, "id_unified": 2, "name": "STANDBY", "severity": "STABLE", "description": "Standby"},
    1: {"id_sungrow": 1, "id_unified": 3, "name": "STARTING", "severity": "WARNING", "description": "Starting"},
    2: {"id_sungrow": 2, "id_unified": 1, "name": "RUNNING", "severity": "STABLE", "description": "Running normally"},
    3: {"id_sungrow": 3, "id_unified": 6, "name": "ALARM_RUNNING", "severity": "WARNING", "description": "Running with alarm"},
    4: {"id_sungrow": 4, "id_unified": 7, "name": "DERATING", "severity": "WARNING", "description": "Derating"},
    5: {"id_sungrow": 5, "id_unified": 8, "name": "DISPATCH_RUNNING", "severity": "WARNING", "description": "Dispatch running"},
    6: {"id_sungrow": 6, "id_unified": 4, "name": "STOPPED", "severity": "ERROR", "description": "Stopped"},
    7: {"id_sungrow": 7, "id_unified": 5, "name": "FAULT", "severity": "ERROR", "description": "Fault"},
    8: {"id_sungrow": 8, "id_unified": 10, "name": "EMERGENCY_STOP", "severity": "ERROR", "description": "Emergency stop"},
    9: {"id_sungrow": 9, "id_unified": 11, "name": "KEY_STOP", "severity": "ERROR", "description": "Key stop"},
    10: {"id_sungrow": 10, "id_unified": 20, "name": "POWER_LIMITED", "severity": "WARNING", "description": "Power limited"},
}

HUAWEI_FAULT_MAP = {
    2000: {"id_huawei": 2000, "id_unified": 0, "name": "RUNNING", "severity": "STABLE", "repair_instruction": "Normal."},
    2001: {"id_huawei": 2001, "id_unified": 1001, "name": "GRID_OVERVOLTAGE", "severity": "ERROR", "repair_instruction": "Check grid voltage."},
    2002: {"id_huawei": 2002, "id_unified": 1003, "name": "GRID_UNDERVOLTAGE", "severity": "ERROR", "repair_instruction": "Check grid voltage."},
    2003: {"id_huawei": 2003, "id_unified": 1005, "name": "GRID_OVERFREQUENCY", "severity": "ERROR", "repair_instruction": "Check frequency."},
    2004: {"id_huawei": 2004, "id_unified": 1006, "name": "GRID_UNDERFREQUENCY", "severity": "ERROR", "repair_instruction": "Check frequency."},
    2005: {"id_huawei": 2005, "id_unified": 1007, "name": "GRID_LOSS", "severity": "ERROR", "repair_instruction": "Check AC breaker."},
    2006: {"id_huawei": 2006, "id_unified": 1009, "name": "GRID_PHASE_FAULT", "severity": "ERROR", "repair_instruction": "Check phase sequence."},
    2011: {"id_huawei": 2011, "id_unified": 1102, "name": "DC_OVERVOLTAGE", "severity": "ERROR", "repair_instruction": "Check PV voltage."},
    2012: {"id_huawei": 2012, "id_unified": 1202, "name": "DC_INSULATION_FAULT", "severity": "ERROR", "repair_instruction": "Check insulation."},
    2013: {"id_huawei": 2013, "id_unified": 1206, "name": "GROUND_FAULT", "severity": "ERROR", "repair_instruction": "Check grounding."},
    2014: {"id_huawei": 2014, "id_unified": 1201, "name": "LEAKAGE_CURRENT", "severity": "ERROR", "repair_instruction": "Check leakage."},
    2015: {"id_huawei": 2015, "id_unified": 1105, "name": "STRING_FAULT", "severity": "WARNING", "repair_instruction": "Check connectors."},
    2021: {"id_huawei": 2021, "id_unified": 1301, "name": "OVER_TEMPERATURE", "severity": "ERROR", "repair_instruction": "Check ventilation."},
    2022: {"id_huawei": 2022, "id_unified": 1401, "name": "FAN_FAULT", "severity": "WARNING", "repair_instruction": "Check fan."},
}

HUAWEI_STATE_MAP = {

    0: {
    "id_huawei": 0,
    "id_unified": 12,
    "name": "INITIAL_STANDBY",
    "severity": "STABLE",
    "description": "Inverter initialized and waiting"
    },

    1: {
    "id_huawei": 1,
    "id_unified": 13,
    "name": "GRID_DETECTING",
    "severity": "WARNING",
    "description": "Detecting grid parameters"
    },

    2: {
    "id_huawei": 2,
    "id_unified": 14,
    "name": "INSULATION_CHECK",
    "severity": "WARNING",
    "description": "Performing insulation resistance test"
    },

    3: {
    "id_huawei": 3,
    "id_unified": 15,
    "name": "SELF_CHECK",
    "severity": "WARNING",
    "description": "Self check before startup"
    },

    4: {
    "id_huawei": 4,
    "id_unified": 3,
    "name": "STARTING",
    "severity": "WARNING",
    "description": "Inverter starting"
    },

    5: {
    "id_huawei": 5,
    "id_unified": 1,
    "name": "RUNNING",
    "severity": "STABLE",
    "description": "Inverter running normally"
    },

    6: {
    "id_huawei": 6,
    "id_unified": 6,
    "name": "ALARM_RUNNING",
    "severity": "WARNING",
    "description": "Running with alarm"
    },

    7: {
    "id_huawei": 7,
    "id_unified": 7,
    "name": "DERATING",
    "severity": "WARNING",
    "description": "Running with power derating"
    },

    8: {
    "id_huawei": 8,
    "id_unified": 4,
    "name": "STOPPED",
    "severity": "ERROR",
    "description": "Inverter stopped"
    },

    9: {
    "id_huawei": 9,
    "id_unified": 5,
    "name": "FAULT",
    "severity": "ERROR",
    "description": "Fault condition detected"
    },

    10: {
    "id_huawei": 10,
    "id_unified": 18,
    "name": "UPGRADING",
    "severity": "WARNING",
    "description": "Firmware upgrading"
    },

    11: {
    "id_huawei": 11,
    "id_unified": 19,
    "name": "SHUTTING_DOWN",
    "severity": "WARNING",
    "description": "Shutdown in progress"
    },

    12: {
    "id_huawei": 12,
    "id_unified": 21,
    "name": "GRID_FAULT_WAIT",
    "severity": "WARNING",
    "description": "Waiting for grid recovery"
    },

    13: {
    "id_huawei": 13,
    "id_unified": 17,
    "name": "MAINTENANCE_MODE",
    "severity": "ERROR",
    "description": "Maintenance mode active"
    }

}
SUNGROW_STATE_MAP = {

    0: {
    "id_sungrow": 0,
    "id_unified": 2,
    "name": "STANDBY",
    "severity": "STABLE",
    "description": "Standby state waiting for solar input"
    },

    1: {
    "id_sungrow": 1,
    "id_unified": 3,
    "name": "STARTING",
    "severity": "WARNING",
    "description": "System starting"
    },

    2: {
    "id_sungrow": 2,
    "id_unified": 1,
    "name": "RUNNING",
    "severity": "STABLE",
    "description": "Inverter running normally"
    },

    3: {
    "id_sungrow": 3,
    "id_unified": 6,
    "name": "ALARM_RUNNING",
    "severity": "WARNING",
    "description": "Running with warning"
    },

    4: {
    "id_sungrow": 4,
    "id_unified": 7,
    "name": "DERATING",
    "severity": "WARNING",
    "description": "Power derating active"
    },

    5: {
    "id_sungrow": 5,
    "id_unified": 8,
    "name": "DISPATCH_RUNNING",
    "severity": "WARNING",
    "description": "Power dispatch or remote control"
    },

    6: {
    "id_sungrow": 6,
    "id_unified": 4,
    "name": "STOPPED",
    "severity": "ERROR",
    "description": "Inverter stopped"
    },

    7: {
    "id_sungrow": 7,
    "id_unified": 5,
    "name": "FAULT",
    "severity": "ERROR",
    "description": "Fault state"
    },

    8: {
    "id_sungrow": 8,
    "id_unified": 10,
    "name": "EMERGENCY_STOP",
    "severity": "ERROR",
    "description": "Emergency stop triggered"
    },

    9: {
    "id_sungrow": 9,
    "id_unified": 11,
    "name": "KEY_STOP",
    "severity": "ERROR",
    "description": "Manual stop via key"
    },

    10: {
    "id_sungrow": 10,
    "id_unified": 20,
    "name": "POWER_LIMITED",
    "severity": "WARNING",
    "description": "Power limited by grid dispatch"
    }
}


class FaultStateService:
    def __init__(self):
        self.state_maps = {
            "HUAWEI": HUAWEI_STATE_MAP,
            "SUNGROW": SUNGROW_STATE_MAP
            }
        self.fault_maps = {
            "HUAWEI": HUAWEI_FAULT_MAP,
            "SUNGROW": SUNGROW_FAULT_MAP
            }


# ============================================================
# ALIASES — dùng cho fault_service.py
# ============================================================

# Dict theo brand: FAULT_MAPS["HUAWEI"] -> HUAWEI_FAULT_MAP
FAULT_MAPS = {
    "HUAWEI": HUAWEI_FAULT_MAP,
    "SUNGROW": SUNGROW_FAULT_MAP,
}

# Dict theo brand: STATE_MAPS["HUAWEI"] -> HUAWEI_STATE_MAP
STATE_MAPS = {
    "HUAWEI": HUAWEI_STATE_MAP,
    "SUNGROW": SUNGROW_STATE_MAP,
}

# Huawei Modbus: map raw status_code từ thanh ghi Modbus 
# sang id_unified (state code trong HUAWEI_STATE_MAP)
# Với Huawei SUN2000, thanh ghi 32089 trả về integer state trực tiếp
# (0=Standby, 1=Grid-connected, 2=Grid-connected normally, ...)
# map này convert về id Huawei state map (0-13)
HUAWEI_MODBUS_MAP = {
    0: 0,    # INITIAL_STANDBY
    1: 5,    # RUNNING
    2: 5,    # RUNNING (grid connected normally)
    3: 6,    # ALARM_RUNNING
    4: 7,    # DERATING
    5: 8,    # STOPPED
    6: 9,    # FAULT
    7: 10,   # UPGRADING
    8: 11,   # SHUTTING_DOWN
    9: 1,    # GRID_DETECTING
    10: 2,   # INSULATION_CHECK
    11: 3,   # SELF_CHECK
    12: 4,   # STARTING
    13: 12,  # GRID_FAULT_WAIT
    14: 13,  # MAINTENANCE_MODE
}
