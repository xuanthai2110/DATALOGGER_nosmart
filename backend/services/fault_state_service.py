UNIFIED_STATES = {
    1: "RUNNING",
    2: "STANDBY",
    3: "STARTING",
    4: "STOPPED",
    5: "FAULT",
    6: "ALARM_RUNNING",
    7: "DERATING",
    8: "DISPATCH_RUNNING",
    9: "COMMUNICATION_FAULT",
    10: "EMERGENCY_STOP",
    11: "KEY_STOP",
    12: "INITIAL_STANDBY",
    13: "GRID_DETECTING",
    14: "INSULATION_CHECK",
    15: "SELF_CHECK",
    16: "OFF_GRID_RUNNING",
    17: "MAINTENANCE_MODE",
    18: "UPGRADING",
    19: "SHUTTING_DOWN",
    20: "POWER_LIMITED",
    21: "GRID_FAULT_WAIT",
    22: "SLEEP"
}
UNIFIED_FAULTS = {

    # GRID
    1001: "GRID_OVERVOLTAGE",
    1002: "GRID_TRANSIENT_OVERVOLTAGE",
    1003: "GRID_UNDERVOLTAGE",
    1004: "GRID_OVERCURRENT",
    1005: "GRID_OVER_FREQUENCY",
    1006: "GRID_UNDER_FREQUENCY",
    1007: "GRID_POWER_OUTAGE",
    1008: "GRID_VOLTAGE_UNBALANCE",
    1009: "GRID_PHASE_LOSS",
    1010: "GRID_ABNORMAL",
    1011: "GRID_10MIN_OVERVOLTAGE",
    1012: "GRID_IMPEDANCE_ABNORMAL",
    1013: "GRID_REVERSE_POWER",
    1014: "GRID_CONNECTION_LOST",
    1015: "GRID_PROTECTION_TRIGGERED",

    # PV
    1101: "PV_REVERSE_CONNECTION",
    1102: "PV_OVERVOLTAGE",
    1103: "PV_CONFIGURATION_ERROR",
    1104: "PV_INPUT_ABNORMAL",
    1105: "PV_STRING_FAULT",
    1106: "PV_STRING_LOSS",
    1107: "PV_STRING_IMBALANCE",
    1108: "PV_LOW_VOLTAGE",
    1109: "PV_DC_BUS_OVERVOLTAGE",
    1110: "PV_DC_BUS_UNDERVOLTAGE",

    # ELECTRICAL
    1201: "LEAKAGE_CURRENT",
    1202: "LOW_INSULATION_RESISTANCE",
    1203: "AC_OVERLOAD",
    1204: "AC_SHORT_CIRCUIT",
    1205: "DC_OVER_CURRENT",
    1206: "GROUND_FAULT",
    1207: "RESIDUAL_CURRENT_FAULT",
    1208: "DC_COMPONENT_HIGH",
    1209: "DC_INJECTION_HIGH",

    # TEMPERATURE
    1301: "DEVICE_OVER_TEMPERATURE",
    1302: "AMBIENT_OVER_TEMPERATURE",
    1303: "AMBIENT_LOW_TEMPERATURE",
    1304: "HEATSINK_OVER_TEMPERATURE",
    1305: "MODULE_OVER_TEMPERATURE",

    # HARDWARE
    1401: "FAN_FAULT",
    1402: "AC_SPD_FAULT",
    1403: "DC_SPD_FAULT",
    1404: "RELAY_FAULT",
    1405: "CONTACTOR_FAULT",
    1406: "SENSOR_FAULT",
    1407: "EEPROM_FAULT",
    1408: "INTERNAL_COMMUNICATION_FAULT",
    1409: "CONTROL_BOARD_FAULT",
    1410: "POWER_MODULE_FAULT",

    # COMMUNICATION
    1501: "COMMUNICATION_FAULT",
    1502: "METER_COMMUNICATION_FAULT",
    1503: "RS485_COMMUNICATION_FAULT",
    1504: "MODBUS_COMMUNICATION_FAULT",
    1505: "ETHERNET_COMMUNICATION_FAULT",
    1506: "CLOUD_COMMUNICATION_FAULT",

    # SAFETY
    1601: "ARC_FAULT",
    1602: "ARC_DETECTION_DISABLED",
    1603: "RAPID_SHUTDOWN_TRIGGERED",
    1604: "FIRE_PROTECTION_TRIGGERED",
    1605: "EMERGENCY_STOP_TRIGGERED",

    # SYSTEM
    1701: "DEVICE_ABNORMAL",
    1702: "GRID_PROTECTION_SELF_CHECK_FAILURE",
    1703: "SYSTEM_SELF_CHECK_FAILURE",
    1704: "SOFTWARE_EXCEPTION",
    1705: "FIRMWARE_UPGRADE_FAILURE",
    1706: "CONFIGURATION_ERROR",

    # DERATING
    1801: "POWER_DERATING",
    1802: "TEMPERATURE_DERATING",
    1803: "GRID_LIMIT_DERATING",
    1804: "FREQUENCY_DERATING",
    1805: "POWER_LIMIT_CONTROL",
}
# Sungrow inverter fault map
# ASCII comments only for Linux compatibility

SUNGROW_FAULT_MAP = {

    # -------------------------
    # GRID PROTECTION
    # -------------------------

    1: {
        "id_sungrow": 1,
        "id_unified": 1,
        "name": "GRID_OVERVOLTAGE",
        "severity": "ERROR",
        "repair_instruction": "Check grid voltage and transformer tap setting."
    },

    2: {
        "id_sungrow": 2,
        "id_unified": 2,
        "name": "GRID_UNDERVOLTAGE",
        "severity": "ERROR",
        "repair_instruction": "Check grid voltage level and cable connection."
    },

    3: {
        "id_sungrow": 3,
        "id_unified": 4,
        "name": "GRID_OVERFREQUENCY",
        "severity": "ERROR",
        "repair_instruction": "Check grid frequency stability."
    },

    4: {
        "id_sungrow": 4,
        "id_unified": 5,
        "name": "GRID_UNDERFREQUENCY",
        "severity": "ERROR",
        "repair_instruction": "Check utility grid frequency."
    },

    5: {
        "id_sungrow": 5,
        "id_unified": 6,
        "name": "GRID_LOSS",
        "severity": "ERROR",
        "repair_instruction": "Check AC breaker and grid cable."
    },

    6: {
        "id_sungrow": 6,
        "id_unified": 38,
        "name": "GRID_PHASE_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Check phase sequence and wiring."
    },

    # -------------------------
    # DC SIDE
    # -------------------------

    10: {
        "id_sungrow": 10,
        "id_unified": 7,
        "name": "DC_OVERVOLTAGE",
        "severity": "ERROR",
        "repair_instruction": "Check PV string voltage."
    },

    11: {
        "id_sungrow": 11,
        "id_unified": 9,
        "name": "DC_INSULATION_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Check insulation resistance between PV and ground."
    },

    12: {
        "id_sungrow": 12,
        "id_unified": 19,
        "name": "GROUND_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Inspect grounding system."
    },

    13: {
        "id_sungrow": 13,
        "id_unified": 20,
        "name": "LEAKAGE_CURRENT",
        "severity": "ERROR",
        "repair_instruction": "Check residual current leakage."
    },

    14: {
        "id_sungrow": 14,
        "id_unified": 11,
        "name": "STRING_FAULT",
        "severity": "WARNING",
        "repair_instruction": "Inspect PV string current and connectors."
    },

    # -------------------------
    # TEMPERATURE
    # -------------------------

    20: {
        "id_sungrow": 20,
        "id_unified": 12,
        "name": "OVER_TEMPERATURE",
        "severity": "ERROR",
        "repair_instruction": "Check inverter cooling and ambient temperature."
    },

    21: {
        "id_sungrow": 21,
        "id_unified": 13,
        "name": "FAN_FAULT",
        "severity": "WARNING",
        "repair_instruction": "Inspect cooling fan."
    },

    22: {
        "id_sungrow": 22,
        "id_unified": 14,
        "name": "HEATSINK_OVER_TEMP",
        "severity": "ERROR",
        "repair_instruction": "Check heat sink airflow."
    },

    # -------------------------
    # INTERNAL HARDWARE
    # -------------------------

    30: {
        "id_sungrow": 30,
        "id_unified": 33,
        "name": "HARDWARE_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Inspect inverter internal modules."
    },

    31: {
        "id_sungrow": 31,
        "id_unified": 34,
        "name": "SOFTWARE_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Restart inverter or update firmware."
    },

    32: {
        "id_sungrow": 32,
        "id_unified": 15,
        "name": "POWER_MODULE_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Check internal power module."
    },

    33: {
        "id_sungrow": 33,
        "id_unified": 16,
        "name": "BUS_OVERVOLTAGE",
        "severity": "ERROR",
        "repair_instruction": "Check DC bus voltage."
    },

    34: {
        "id_sungrow": 34,
        "id_unified": 17,
        "name": "BUS_UNDERVOLTAGE",
        "severity": "ERROR",
        "repair_instruction": "Inspect DC bus system."
    },

    35: {
        "id_sungrow": 35,
        "id_unified": 18,
        "name": "RELAY_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Inspect AC relay."
    },

    # -------------------------
    # COMMUNICATION
    # -------------------------

    40: {
        "id_sungrow": 40,
        "id_unified": 24,
        "name": "COMMUNICATION_FAULT",
        "severity": "DISCONNECT",
        "repair_instruction": "Check communication module and cable."
    },

    41: {
        "id_sungrow": 41,
        "id_unified": 25,
        "name": "RS485_FAULT",
        "severity": "DISCONNECT",
        "repair_instruction": "Check RS485 wiring."
    },

    42: {
        "id_sungrow": 42,
        "id_unified": 26,
        "name": "WIFI_FAULT",
        "severity": "DISCONNECT",
        "repair_instruction": "Inspect WiFi module."
    },

    43: {
        "id_sungrow": 43,
        "id_unified": 27,
        "name": "PLC_FAULT",
        "severity": "DISCONNECT",
        "repair_instruction": "Check PLC communication."
    },

    44: {
        "id_sungrow": 44,
        "id_unified": 28,
        "name": "METER_COMM_FAULT",
        "severity": "DISCONNECT",
        "repair_instruction": "Check smart meter communication."
    },

    # -------------------------
    # PROTECTION
    # -------------------------

    50: {
        "id_sungrow": 50,
        "id_unified": 29,
        "name": "ARC_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Inspect PV cables for arc fault."
    },

    51: {
        "id_sungrow": 51,
        "id_unified": 30,
        "name": "SPD_FAULT",
        "severity": "WARNING",
        "repair_instruction": "Check surge protection device."
    },

    52: {
        "id_sungrow": 52,
        "id_unified": 32,
        "name": "ANTI_ISLANDING_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Check grid protection settings."
    },

    # -------------------------
    # SYSTEM
    # -------------------------

    60: {
        "id_sungrow": 60,
        "id_unified": 36,
        "name": "STARTUP_FAIL",
        "severity": "ERROR",
        "repair_instruction": "Restart inverter and verify parameters."
    },

    61: {
        "id_sungrow": 61,
        "id_unified": 37,
        "name": "SHUTDOWN_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Check shutdown cause."
    },

    62: {
        "id_sungrow": 62,
        "id_unified": 35,
        "name": "CONFIGURATION_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Verify inverter configuration."
    },

    # -------------------------
    # SENSOR
    # -------------------------

    70: {
        "id_sungrow": 70,
        "id_unified": 39,
        "name": "CURRENT_SENSOR_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Inspect current sensor."
    },

    71: {
        "id_sungrow": 71,
        "id_unified": 40,
        "name": "VOLTAGE_SENSOR_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Inspect voltage sensing circuit."
    },

    72: {
        "id_sungrow": 72,
        "id_unified": 41,
        "name": "TEMPERATURE_SENSOR_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Inspect temperature sensor."
    }
}
# Huawei SUN2000 fault mapping to unified faults
# ASCII comments only to avoid UTF-8 issues on Linux

HUAWEI_FAULT_MAP = {

# -------------------------
# GRID FAULTS
# -------------------------

    2001: {
        "id_huawei": 2001,
        "id_unified": 1,
        "name": "GRID_OVERVOLTAGE",
        "severity": "ERROR",
        "repair_instruction": "Check grid voltage and transformer tap setting."
    },

    2002: {
        "id_huawei": 2002,
        "id_unified": 2,
        "name": "GRID_UNDERVOLTAGE",
        "severity": "ERROR",
        "repair_instruction": "Check grid voltage and grid connection."
    },

    2003: {
        "id_huawei": 2003,
        "id_unified": 4,
        "name": "GRID_OVERFREQUENCY",
        "severity": "ERROR",
        "repair_instruction": "Verify grid frequency stability."
    },

    2004: {
        "id_huawei": 2004,
        "id_unified": 5,
        "name": "GRID_UNDERFREQUENCY",
        "severity": "ERROR",
        "repair_instruction": "Check grid frequency and utility stability."
    },

    2005: {
        "id_huawei": 2005,
        "id_unified": 6,
        "name": "GRID_LOSS",
        "severity": "ERROR",
        "repair_instruction": "Check AC breaker, grid cable, and grid availability."
    },

    2006: {
        "id_huawei": 2006,
        "id_unified": 38,
        "name": "GRID_PHASE_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Check phase sequence and AC wiring."
    },

    # -------------------------
    # DC SIDE
    # -------------------------

    2011: {
        "id_huawei": 2011,
        "id_unified": 7,
        "name": "DC_OVERVOLTAGE",
        "severity": "ERROR",
        "repair_instruction": "Check PV string voltage and configuration."
    },

    2012: {
        "id_huawei": 2012,
        "id_unified": 9,
        "name": "DC_INSULATION_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Check insulation resistance between PV and ground."
    },

    2013: {
        "id_huawei": 2013,
        "id_unified": 19,
        "name": "GROUND_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Inspect grounding system and PV wiring."
    },

    2014: {
        "id_huawei": 2014,
        "id_unified": 20,
        "name": "LEAKAGE_CURRENT",
        "severity": "ERROR",
        "repair_instruction": "Check leakage current and grounding."
    },

    2015: {
        "id_huawei": 2015,
        "id_unified": 11,
        "name": "STRING_FAULT",
        "severity": "WARNING",
        "repair_instruction": "Inspect PV string current and connectors."
    },

    # -------------------------
    # TEMPERATURE
    # -------------------------

    2021: {
        "id_huawei": 2021,
        "id_unified": 12,
        "name": "OVER_TEMPERATURE",
        "severity": "ERROR",
        "repair_instruction": "Check ventilation and ambient temperature."
    },

    2022: {
        "id_huawei": 2022,
        "id_unified": 13,
        "name": "FAN_FAULT",
        "severity": "WARNING",
        "repair_instruction": "Check cooling fan operation."
    },

    2023: {
        "id_huawei": 2023,
        "id_unified": 14,
        "name": "HEATSINK_OVER_TEMP",
        "severity": "ERROR",
        "repair_instruction": "Check heat sink cooling and airflow."
    },

    # -------------------------
    # INTERNAL HARDWARE
    # -------------------------

    2031: {
        "id_huawei": 2031,
        "id_unified": 33,
        "name": "HARDWARE_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Inspect inverter hardware modules."
    },

    2032: {
        "id_huawei": 2032,
        "id_unified": 34,
        "name": "SOFTWARE_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Restart inverter or update firmware."
    },

    2033: {
        "id_huawei": 2033,
        "id_unified": 15,
        "name": "POWER_MODULE_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Check internal power module."
    },

    2034: {
        "id_huawei": 2034,
        "id_unified": 16,
        "name": "BUS_OVERVOLTAGE",
        "severity": "ERROR",
        "repair_instruction": "Check DC bus voltage."
    },

    2035: {
        "id_huawei": 2035,
        "id_unified": 17,
        "name": "BUS_UNDERVOLTAGE",
        "severity": "ERROR",
        "repair_instruction": "Check internal DC bus system."
    },

    2036: {
        "id_huawei": 2036,
        "id_unified": 18,
        "name": "RELAY_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Inspect AC relay or contactor."
    },

    # -------------------------
    # COMMUNICATION
    # -------------------------

    2041: {
        "id_huawei": 2041,
        "id_unified": 24,
        "name": "COMMUNICATION_FAULT",
        "severity": "DISCONNECT",
        "repair_instruction": "Check RS485 cable and communication module."
    },

    2042: {
        "id_huawei": 2042,
        "id_unified": 25,
        "name": "RS485_FAULT",
        "severity": "DISCONNECT",
        "repair_instruction": "Verify RS485 wiring and termination."
    },

    2043: {
        "id_huawei": 2043,
        "id_unified": 26,
        "name": "WIFI_FAULT",
        "severity": "DISCONNECT",
        "repair_instruction": "Check WiFi module and signal."
    },

    2044: {
        "id_huawei": 2044,
        "id_unified": 27,
        "name": "PLC_FAULT",
        "severity": "DISCONNECT",
        "repair_instruction": "Check PLC communication link."
    },

    2045: {
        "id_huawei": 2045,
        "id_unified": 28,
        "name": "METER_COMM_FAULT",
        "severity": "DISCONNECT",
        "repair_instruction": "Check smart meter communication."
    },

    # -------------------------
    # PROTECTION
    # -------------------------

    2051: {
        "id_huawei": 2051,
        "id_unified": 29,
        "name": "AFCI_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Inspect PV wiring for arc fault."
    },

    2052: {
        "id_huawei": 2052,
        "id_unified": 30,
        "name": "SPD_FAULT",
        "severity": "WARNING",
        "repair_instruction": "Check surge protection device."
    },

    2053: {
        "id_huawei": 2053,
        "id_unified": 31,
        "name": "PID_PROTECTION",
        "severity": "WARNING",
        "repair_instruction": "Check PID protection status."
    },

    2054: {
        "id_huawei": 2054,
        "id_unified": 32,
        "name": "ANTI_ISLANDING_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Check grid stability and protection."
    },

    # -------------------------
    # SYSTEM
    # -------------------------

    2061: {
        "id_huawei": 2061,
        "id_unified": 36,
        "name": "STARTUP_FAIL",
        "severity": "ERROR",
        "repair_instruction": "Restart inverter and check parameters."
    },

    2062: {
        "id_huawei": 2062,
        "id_unified": 37,
        "name": "SHUTDOWN_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Check shutdown cause and restart."
    },

    2063: {
        "id_huawei": 2063,
        "id_unified": 35,
        "name": "CONFIGURATION_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Verify inverter configuration parameters."
    },

    # -------------------------
    # SENSOR
    # -------------------------

    2071: {
        "id_huawei": 2071,
        "id_unified": 39,
        "name": "CURRENT_SENSOR_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Inspect current sensor hardware."
    },

    2072: {
        "id_huawei": 2072,
        "id_unified": 40,
        "name": "VOLTAGE_SENSOR_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Inspect voltage sensing circuit."
    },

    2073: {
        "id_huawei": 2073,
        "id_unified": 41,
        "name": "TEMPERATURE_SENSOR_FAULT",
        "severity": "ERROR",
        "repair_instruction": "Inspect temperature sensor."
    }
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

def create_unified_fault_payload(fault_code: int = 0, fault_description: str = None, repair_instruction: str = None, severity: str = "STABLE", state_id: int = None, state_name: str = None) -> dict:
    """
    Tạo JSON chuẩn cho state và fault để gửi lên server/cloud theo định dạng yêu cầu.
    Nếu trạng thái không có lỗi thì fault_code = id của state, fault_description = state name, repair_instruction = null.
    
    Returns:
        dict: Chứa thông tin đã chuẩn hóa
    """
    import datetime

    if fault_code == 0 or fault_code is None:
        return {
            "fault_code": state_id if state_id is not None else 0,
            "fault_description": state_name if state_name is not None else "Unknown State",
            "repair_instruction": None,
            "severity": severity,
            "created_at": datetime.datetime.now().isoformat()
        }
    else:
        return {
            "fault_code": fault_code,
            "fault_description": fault_description if fault_description is not None else "Unknown Fault",
            "repair_instruction": repair_instruction,
            "severity": severity,
            "created_at": datetime.datetime.now().isoformat()
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
        
        # Mapping từ thanh ghi Modbus 32089 của Huawei sang ID nội bộ trong HUAWEI_STATE_MAP
        self.huawei_modbus_state_map = {
            0x0000: 0,  # INITIAL_STANDBY
            0x0001: 2,  # INSULATION_CHECK
            0x0002: 1,  # GRID_DETECTING
            0x0003: 1,  # GRID_DETECTING
            0x0100: 4,  # STARTING
            0x0200: 5,  # RUNNING
            0x0201: 7,  # DERATING
            0x0202: 7,  # DERATING
            0x0203: 5,  # RUNNING (Off-grid)
            0x0300: 9,  # FAULT
            0x0301: 8,  # STOPPED
            0x0302: 9,  # FAULT (OVGR)
            0x0303: 9,  # FAULT (Comm disconnect)
            0x0304: 8,  # STOPPED (Power limited)
            0x0305: 8,  # STOPPED (Manual startup req)
            0x0306: 8,  # STOPPED (DC disconnect)
            0x0307: 8,  # STOPPED (Rapid cutoff)
            0x0308: 8,  # STOPPED (Input underpower)
        }

    def map_state(self, brand: str, state_id: int) -> dict:
        brand = brand.upper()
        
        # Đặc biệt cho Huawei: state_id truyền vào là mã Modbus thô (32089)
        if brand == "HUAWEI":
            state_id = self.huawei_modbus_state_map.get(state_id, 5) # Default là ID 5 (RUNNING)
            
        mapping = self.state_maps.get(brand, {})
        state_info = mapping.get(state_id)
        
        if state_info:
            return {
                "name": state_info["name"],
                "severity": state_info["severity"],
                "description": state_info.get("description", "")
            }
        return {
            "name": f"UNKNOWN_STATE_{state_id}",
            "severity": "STABLE",
            "description": "Unknown inverter state"
        }

    def map_fault(self, brand: str, fault_code: int) -> dict:
        brand = brand.upper()
        mapping = self.fault_maps.get(brand, {})
        fault_info = mapping.get(fault_code)
        
        if fault_info:
            return {
                "name": fault_info["name"],
                "severity": fault_info["severity"],
                "repair_instruction": fault_info.get("repair_instruction", "No instructions available.")
            }
        return {
            "name": f"UNKNOWN_FAULT_{fault_code}",
            "severity": "WARNING",
            "repair_instruction": "Contact technical support."
        }
