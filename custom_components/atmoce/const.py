"""Constants for the Atmoce Battery integration."""

DOMAIN = "atmoce"
DEFAULT_PORT = 502
DEFAULT_SLAVE = 1
DEFAULT_SCAN_INTERVAL = 10  # seconds
MODBUS_TIMEOUT = 10
MODBUS_RETRY_COUNT = 3       # consecutive failures before Cloud fallback
CLOUD_BASE_URL = "https://www.atmocecloud.com/openapi/v1"

# ── Battery model catalogue ──────────────────────────────────────────────────
# Keys are shown in the config flow selector.
# charge_kw  : max continuous charge power (kW)
# discharge_kw: max continuous discharge power (kW)
# peak_kw    : max peak discharge power (kW)
# capacity_kwh: usable battery capacity (kWh)
BATTERY_MODELS: dict[str, dict] = {
    "MS-7K-U": {
        "label": "Atmoce MS-7K-U (7 kWh)",
        "capacity_kwh": 7.0,
        "charge_kw": 3.75,
        "discharge_kw": 4.5,
        "peak_kw": 5.0,
    },
    "MS-14K-U": {
        "label": "Atmoce MS-14K-U (14 kWh — 2×MS-7K-U)",
        "capacity_kwh": 14.0,
        "charge_kw": 7.5,
        "discharge_kw": 9.0,
        "peak_kw": 10.0,
    },
    "manual": {
        "label": "Manual — enter battery specs",
        "capacity_kwh": None,
        "charge_kw": None,
        "discharge_kw": None,
        "peak_kw": None,
    },
}

# ── Modbus register map ──────────────────────────────────────────────────────
# (address, data_type, scale, unit, description)
# data_type: "uint16" | "int16" | "uint32" | "int32" | "uint64"
REG_SN                        = (60000, "str10", 1,      None,  "Serial number")
REG_HW_VERSION                = (60010, "uint16", 1,     None,  "Hardware version")
REG_FW_VERSION                = (60011, "str15", 1,      None,  "Firmware version")
REG_PV_RATED_POWER            = (60027, "uint32", 0.001, "kW",  "Rated PV power (all MIs)")
REG_BATTERY_RATED_POWER       = (60029, "uint32", 0.001, "kW",  "Rated battery power")
REG_BATTERY_RATED_ENERGY      = (60031, "uint32", 0.001, "kWh", "Rated battery energy")
REG_STATION_STATUS            = (60066, "uint16", 1,     None,  "Power station status 0=Normal 1=Fault")
REG_BATTERY_STATUS            = (60067, "uint16", 1,     None,  "Battery status 1=Chg 2=Dischg 99=Idle")
REG_BATTERY_MODE              = (60068, "uint16", 1,     None,  "Operating mode 1=SelfUse 2=TOU 10=Remote")
REG_PV_POWER                  = (60069, "uint32", 1,     "W",   "PV generation power")
REG_BATTERY_POWER             = (60071, "int32",  1,     "W",   "Battery charge/discharge power")
REG_GRID_POWER                = (60073, "int32",  1,     "W",   "Grid active power")
REG_GRID_VOLTAGE              = (60089, "uint16", 0.1,   "V",   "Grid voltage (single-phase)")
REG_GRID_CURRENT              = (60090, "int16",  0.01,  "A",   "Grid current (single-phase)")
REG_BATTERY_SOC               = (60095, "uint16", 1,     "%",   "Battery SOC")
REG_PV_ENERGY_TOTAL           = (60160, "uint64", 0.01,  "kWh", "Cumulative PV generation")
REG_PV_ENERGY_DAILY           = (60164, "uint32", 0.01,  "kWh", "Daily PV generation")
REG_BATTERY_CHARGED_TOTAL     = (60166, "uint64", 0.01,  "kWh", "Cumulative battery charged")
REG_BATTERY_CHARGED_DAILY     = (60170, "uint32", 0.01,  "kWh", "Daily battery charged")
REG_BATTERY_DISCHARGED_TOTAL  = (60172, "uint64", 0.01,  "kWh", "Cumulative battery discharged")
REG_BATTERY_DISCHARGED_DAILY  = (60176, "uint32", 0.01,  "kWh", "Daily battery discharged")
REG_ELECTRICITY_SALES_TOTAL   = (60178, "uint64", 0.01,  "kWh", "Cumulative electricity sold")
REG_ELECTRICITY_SALES_DAILY   = (60182, "uint32", 0.01,  "kWh", "Daily electricity sold")
REG_GRID_ENERGY_TOTAL         = (60184, "uint64", 0.01,  "kWh", "Cumulative grid purchase")
REG_GRID_ENERGY_DAILY         = (60188, "uint32", 0.01,  "kWh", "Daily grid purchase")
REG_BATTERY_MAX_CHARGE        = (60200, "uint32", 0.01,  "kW",  "Max charging power limit")
REG_BATTERY_MAX_DISCHARGE     = (60202, "uint32", 0.01,  "kW",  "Max discharging power limit")

# Writable registers
REG_COMM_CONTROL_MODE         = (60301, "uint16", 1,     None,  "0=Local 1=Remote")
REG_ACTIVE_POWER_FIXED        = (60302, "uint32", 0.001, "kW",  "Active power fixed setpoint")
REG_ACTIVE_POWER_PCT          = (60304, "uint16", 0.1,   "%",   "Active power percentage [0,100]")
REG_FORCED_CMD                = (60310, "uint16", 1,     None,  "0=ForceCharge 1=ForceDischarge 2=Exit")
REG_FORCED_MODE               = (60311, "uint16", 1,     None,  "0=TargetSOC 1=Duration 2=Both")
REG_FORCED_TARGET_SOC         = (60312, "uint16", 1,     "%",   "Forced charge/discharge target SOC")
REG_FORCED_DURATION           = (60313, "uint16", 1,     "min", "Forced charge/discharge duration [0,1440]")
REG_FORCED_POWER              = (60314, "uint32", 0.001, "kW",  "Forced charge/discharge power")
REG_DISPATCH_POWER            = (60316, "int32",  1,     "W",   "<0=charge >0=discharge")
REG_RESET                     = (60400, "uint16", 1,     None,  "Write 0 to reset gateway")

# ── Forced command option values ─────────────────────────────────────────────
FORCED_CMD_CHARGE    = 0
FORCED_CMD_DISCHARGE = 1
FORCED_CMD_AUTO      = 2   # "Administrado por batería"

FORCED_MODE_SOC      = 0
FORCED_MODE_DURATION = 1
FORCED_MODE_BOTH     = 2

# ── Config entry keys ────────────────────────────────────────────────────────
CONF_HOST             = "host"
CONF_PORT             = "port"
CONF_SLAVE            = "slave"
CONF_BATTERY_MODEL    = "battery_model"
CONF_CAPACITY_KWH     = "capacity_kwh"
CONF_CHARGE_KW        = "charge_kw"
CONF_DISCHARGE_KW     = "discharge_kw"
CONF_CLOUD_ENABLED    = "cloud_enabled"
CONF_CLOUD_APP_KEY    = "cloud_app_key"
CONF_CLOUD_APP_SECRET = "cloud_app_secret"
CONF_RETRY_COUNT      = "modbus_retry_count"

# ── Active data source ───────────────────────────────────────────────────────
SOURCE_MODBUS = "Modbus"
SOURCE_CLOUD  = "Cloud"
