SUNGROW_FAULT_MAP = {

    # ================= GRID =================
    1001: {
        "id_unified": 1001,
        "name": "GRID_OVERVOLTAGE",
        "severity": "ERROR",
        "id_sungrow": [2, 3, 14, 15],
        "repair_instruction": "Check grid voltage, protection settings, transformer tap"
    },

    1003: {
        "id_unified": 1003,
        "name": "GRID_UNDERVOLTAGE",
        "severity": "ERROR",
        "id_sungrow": [4, 5],
        "repair_instruction": "Check grid voltage and connection"
    },

    1005: {
        "id_unified": 1005,
        "name": "GRID_OVER_FREQUENCY",
        "severity": "ERROR",
        "id_sungrow": [8],
        "repair_instruction": "Check grid frequency"
    },

    1006: {
        "id_unified": 1006,
        "name": "GRID_UNDER_FREQUENCY",
        "severity": "ERROR",
        "id_sungrow": [9],
        "repair_instruction": "Check grid frequency"
    },

    1007: {
        "id_unified": 1007,
        "name": "GRID_POWER_OUTAGE",
        "severity": "CRITICAL",
        "id_sungrow": [10],
        "repair_instruction": "Check grid connection and breaker"
    },

    1010: {
        "id_unified": 1010,
        "name": "GRID_ABNORMAL",
        "severity": "ERROR",
        "id_sungrow": [13],
        "repair_instruction": "Check grid quality"
    },

    1008: {
        "id_unified": 1008,
        "name": "GRID_VOLTAGE_UNBALANCE",
        "severity": "ERROR",
        "id_sungrow": [17],
        "repair_instruction": "Check phase balance"
    },

    # ================= PV =================
    1101: {
        "id_unified": 1101,
        "name": "PV_REVERSE_CONNECTION",
        "severity": "ERROR",
        "id_sungrow": [
            28, 29, 208,
            (448, 479),
            (532, 547),
            (564, 579)
        ],
        "repair_instruction": "Check PV polarity and wiring"
    },

    1104: {
        "id_unified": 1104,
        "name": "PV_INPUT_ABNORMAL",
        "severity": "WARNING",
        "id_sungrow": [
            (548, 563),
            (580, 595)
        ],
        "repair_instruction": "Check PV strings and MPPT input"
    },

    1107: {
        "id_unified": 1107,
        "name": "PV_STRING_IMBALANCE",
        "severity": "WARNING",
        "id_sungrow": [(264, 283)],
        "repair_instruction": "Check string mismatch"
    },

    1111: {
        "id_unified": 1111,
        "name": "STRING_CURRENT_REFLUX",
        "severity": "WARNING",
        "id_sungrow": [(1548, 1579)],
        "repair_instruction": "Check reverse current in strings"
    },

    1206: {
        "id_unified": 1206,
        "name": "GROUND_FAULT",
        "severity": "CRITICAL",
        "id_sungrow": [(1600, 1611)],
        "repair_instruction": "Check grounding and insulation"
    },

    # ================= ELECTRICAL =================
    1201: {
        "id_unified": 1201,
        "name": "LEAKAGE_CURRENT",
        "severity": "CRITICAL",
        "id_sungrow": [12],
        "repair_instruction": "Check leakage current protection"
    },

    1202: {
        "id_unified": 1202,
        "name": "LOW_INSULATION_RESISTANCE",
        "severity": "CRITICAL",
        "id_sungrow": [39],
        "repair_instruction": "Check insulation resistance"
    },

    1206: {
        "id_unified": 1206,
        "name": "GROUND_FAULT",
        "severity": "CRITICAL",
        "id_sungrow": [106],
        "repair_instruction": "Check grounding cable"
    },

    # ================= TEMPERATURE =================
    1302: {
        "id_unified": 1302,
        "name": "AMBIENT_OVER_TEMPERATURE",
        "severity": "WARNING",
        "id_sungrow": [37],
        "repair_instruction": "Check cooling and airflow"
    },

    1303: {
        "id_unified": 1303,
        "name": "AMBIENT_LOW_TEMPERATURE",
        "severity": "WARNING",
        "id_sungrow": [43],
        "repair_instruction": "Check environment"
    },

    # ================= SAFETY =================
    1601: {
        "id_unified": 1601,
        "name": "ARC_FAULT",
        "severity": "CRITICAL",
        "id_sungrow": [88],
        "repair_instruction": "Check DC arc fault"
    },

    # ================= COMM =================
    1502: {
        "id_unified": 1502,
        "name": "METER_COMMUNICATION_FAULT",
        "severity": "ERROR",
        "id_sungrow": [514],
        "repair_instruction": "Check meter communication"
    },

    1501: {
        "id_unified": 1501,
        "name": "COMMUNICATION_FAULT",
        "severity": "ERROR",
        "id_sungrow": [75],
        "repair_instruction": "Check RS485 / network"
    },

    # ================= SYSTEM =================
    1701: {
        "id_unified": 1701,
        "name": "DEVICE_ABNORMAL",
        "severity": "ERROR",
        "id_sungrow": [323],
        "repair_instruction": "Check inverter status"
    },

    1409: {
        "id_unified": 1409,
        "name": "CONTROL_BOARD_FAULT",
        "severity": "CRITICAL",
        "id_sungrow": [1616],
        "repair_instruction": "Check control board hardware"
    },

    # ================= PID =================
    2001: {
        "id_unified": 2001,
        "name": "PID_IMPEDANCE_ABNORMAL",
        "severity": "WARNING",
        "id_sungrow": [432],
        "repair_instruction": "Check insulation and PID config"
    },

    2002: {
        "id_unified": 2002,
        "name": "PID_FUNCTION_ABNORMAL",
        "severity": "WARNING",
        "id_sungrow": [433],
        "repair_instruction": "Check PID module"
    },

    2003: {
        "id_unified": 2003,
        "name": "PID_OVERCURRENT_PROTECTION",
        "severity": "WARNING",
        "id_sungrow": [434],
        "repair_instruction": "Check PID settings"
    },

    # ================= SYSTEM MASS (RANGE) =================
    1702: {
        "id_unified": 1702,
        "name": "SYSTEM_FAULT",
        "severity": "CRITICAL",
        "id_sungrow": [
            (7, 7), (11, 11), (16, 16),
            (19, 25), (30, 34),
            (36, 36), (38, 38),
            (40, 42), (44, 50),
            (52, 58), (60, 68),
            (85, 85), (87, 87),
            (92, 93),
            (100, 124),
            (200, 211),
            (248, 255),
            (300, 326),
            (401, 412),
            (600, 624),
            (800, 807),
            (1096, 1122)
        ],
        "repair_instruction": "Check inverter internal system"
    },

    1703: {
        "id_unified": 1703,
        "name": "SYSTEM_ALARM",
        "severity": "WARNING",
        "id_sungrow": [
            (59, 59),
            (70, 72),
            (74, 74),
            (76, 83),
            (89, 89),
            (216, 231),
            (432, 434),
            (500, 518),
            (635, 638),
            (900, 911)
        ],
        "repair_instruction": "Check warning details"
    },
}
SUNGROW_STATE_MAP = {

    # ===== RUNNING =====
    0x0000: {
        "id_sungrow": 0x0000,
        "id_unified": 1,
        "name": "RUNNING",
        "severity": "NORMAL",
        "description": "Inverter is running normally"
    },

    # ===== STOP =====
    0x8000: {
        "id_sungrow": 0x8000,
        "id_unified": 4,
        "name": "STOPPED",
        "severity": "STOP",
        "description": "Inverter stopped"
    },

    0x1300: {
        "id_sungrow": 0x1300,
        "id_unified": 11,
        "name": "KEY_STOP",
        "severity": "STOP",
        "description": "Stopped manually via LCD or remote command"
    },

    0x1500: {
        "id_sungrow": 0x1500,
        "id_unified": 10,
        "name": "EMERGENCY_STOP",
        "severity": "CRITICAL",
        "description": "Emergency stop triggered"
    },

    # ===== STANDBY =====
    0x1400: {
        "id_sungrow": 0x1400,
        "id_unified": 2,
        "name": "STANDBY",
        "severity": "IDLE",
        "description": "Standby due to insufficient DC input"
    },

    0x1200: {
        "id_sungrow": 0x1200,
        "id_unified": 12,
        "name": "INITIAL_STANDBY",
        "severity": "IDLE",
        "description": "Initial standby after startup"
    },

    # ===== TRANSIENT =====
    0x1600: {
        "id_sungrow": 0x1600,
        "id_unified": 3,
        "name": "STARTING",
        "severity": "TRANSIENT",
        "description": "Starting and synchronizing with grid"
    },

    # ===== RUN WITH CONDITION =====
    0x9100: {
        "id_sungrow": 0x9100,
        "id_unified": 6,
        "name": "ALARM_RUNNING",
        "severity": "WARNING",
        "description": "Running with active alarm"
    },

    0x8100: {
        "id_sungrow": 0x8100,
        "id_unified": 7,
        "name": "DERATING",
        "severity": "WARNING",
        "description": "Running with reduced power (derating)"
    },

    0x8200: {
        "id_sungrow": 0x8200,
        "id_unified": 8,
        "name": "DISPATCH_RUNNING",
        "severity": "NORMAL",
        "description": "Running under dispatch control"
    },

    # ===== FAULT =====
    0x5500: {
        "id_sungrow": 0x5500,
        "id_unified": 5,
        "name": "FAULT",
        "severity": "CRITICAL",
        "description": "Fault occurred, inverter stopped"
    },

    0x2500: {
        "id_sungrow": 0x2500,
        "id_unified": 9,
        "name": "COMMUNICATION_FAULT",
        "severity": "ERROR",
        "description": "Communication fault detected"
    },

    # ===== SPECIAL =====
    0x1111: {
        "id_sungrow": 0x1111,
        "id_unified": 15,
        "name": "SELF_CHECK",
        "severity": "TRANSIENT",
        "description": "System self-check or uninitialized"
    },

    # =========================================================
    # ===== EXTENDED STATES (NOT DIRECT FROM 5038 - ADDED) =====
    # =========================================================

    2001: {
        "id_sungrow": 2001,
        "id_unified": 13,
        "name": "GRID_DETECTING",
        "severity": "TRANSIENT",
        "description": "Detecting grid condition"
    },

    2002: {
        "id_sungrow": 2002,
        "id_unified": 14,
        "name": "INSULATION_CHECK",
        "severity": "TRANSIENT",
        "description": "Performing insulation resistance check"
    },

    2003: {
        "id_sungrow": 2003,
        "id_unified": 15,
        "name": "SELF_CHECK",
        "severity": "TRANSIENT",
        "description": "Performing internal self check"
    },

    2004: {
        "id_sungrow": 2004,
        "id_unified": 19,
        "name": "SHUTTING_DOWN",
        "severity": "TRANSIENT",
        "description": "Inverter shutting down"
    },

    2005: {
        "id_sungrow": 2005,
        "id_unified": 20,
        "name": "POWER_LIMITED",
        "severity": "WARNING",
        "description": "Power output limited"
    },

    2006: {
        "id_sungrow": 2006,
        "id_unified": 21,
        "name": "GRID_FAULT_WAIT",
        "severity": "WARNING",
        "description": "Waiting for grid recovery"
    },

    2007: {
        "id_sungrow": 2007,
        "id_unified": 22,
        "name": "SLEEP",
        "severity": "IDLE",
        "description": "Sleep mode (night or no PV input)"
    },

    2008: {
        "id_sungrow": 2008,
        "id_unified": 17,
        "name": "MAINTENANCE_MODE",
        "severity": "INFO",
        "description": "Maintenance or service mode"
    },

    2009: {
        "id_sungrow": 2009,
        "id_unified": 18,
        "name": "UPGRADING",
        "severity": "INFO",
        "description": "Firmware upgrading"
    },

    2010: {
        "id_sungrow": 2010,
        "id_unified": 16,
        "name": "OFF_GRID_RUNNING",
        "severity": "NORMAL",
        "description": "Running in off-grid mode"
    }
}