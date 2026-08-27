"""Constants for the Atmoce Battery integration."""

DOMAIN = "atmoce"
DEFAULT_PORT = 502
DEFAULT_SLAVE = 1
DEFAULT_SCAN_INTERVAL = 10  # seconds
MODBUS_TIMEOUT = 10
MODBUS_RETRY_COUNT = 3       # consecutive failures before Cloud fallback
# The Open API serves data that is already up to 15 minutes old, so asking it
# again on the Modbus cadence would only add load to someone else's service.
# Modbus keeps being retried every DEFAULT_SCAN_INTERVAL regardless, so the
# gateway coming back is still noticed within seconds.
CLOUD_FETCH_INTERVAL = 15 * 60  # seconds
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

# ── Battery SOC limits (web portal / private API) ────────────────────────────
# These battery SOC limits are not exposed over Modbus (60200/60202 are
# read-only power limits and there is no reserved-SOC register). They are the
# charge / discharge / backup-reserve limits editable in the ATMOZEN app, and are
# read/written through the same private API the web portal uses, authenticated
# with the owner's normal login (email + password) — not the partner Open API.
#
# Field names in the storageModel object (POST .../web/storageModel/changeModel):
WEB_FIELD_CHARGE_CUTOFF_SOC    = "storageChargeCutoffSoc"     # charge limit
WEB_FIELD_DISCHARGE_CUTOFF_SOC = "storageDischargeCutoffSoc"  # discharge limit
WEB_FIELD_BACKUP_SOC           = "backupSoc"                  # safety/backup reserve

# Coordinator data keys for the SOC limits
KEY_END_OF_CHARGE_SOC    = "end_of_charge_soc"
KEY_END_OF_DISCHARGE_SOC = "end_of_discharge_soc"
KEY_BATTERY_RESERVED_SOC = "battery_reserved_soc"

# SOC ranges (charge/discharge per the Modbus/Cloud docs; reserve is dynamic)
END_OF_CHARGE_SOC_MIN    = 80
END_OF_CHARGE_SOC_MAX    = 100
END_OF_DISCHARGE_SOC_MIN = 0
END_OF_DISCHARGE_SOC_MAX = 30

# ── Standing policy, also from the web portal ────────────────────────────────
# What the battery does when nobody is commanding it — the counterpart to the
# Modbus forced commands, which are momentary and need remote control. These
# settings persist in the portal and survive restarts of anything.
WEB_FIELD_WORK_MODEL             = "workModel"
WEB_FIELD_GRID_CHARGE            = "gridCharge"
WEB_FIELD_GRID_CHARGE_POWER      = "gridChargeMaxPower"
WEB_FIELD_GRID_CHARGE_CUTOFF_SOC = "storageGridChargeCutoffSoc"
WEB_FIELD_SELL_TO_GRID           = "storageSellToGridStatus"
WEB_FIELD_SELL_TO_GRID_POWER     = "storageSellToGridMaxPower"
WEB_FIELD_SELL_TO_GRID_UP_SOC    = "storageSellToGridUpSOC"
# Server-imposed ceilings for the two power fields, read-only.
WEB_FIELD_GRID_CHARGE_POWER_MAX  = "gridChargeMaxPowerLimitUp"
WEB_FIELD_SELL_TO_GRID_POWER_MAX = "storageSellToGridMaxPowerLimitUp"

KEY_WORK_MODE               = "work_mode"
KEY_GRID_CHARGE             = "grid_charge"
KEY_GRID_CHARGE_POWER       = "grid_charge_max_power"
KEY_GRID_CHARGE_CUTOFF_SOC  = "grid_charge_cutoff_soc"
KEY_SELL_TO_GRID            = "sell_to_grid"
KEY_SELL_TO_GRID_POWER      = "sell_to_grid_max_power"
KEY_SELL_TO_GRID_UP_SOC     = "sell_to_grid_up_soc"
KEY_GRID_CHARGE_POWER_MAX   = "grid_charge_max_power_limit"
KEY_SELL_TO_GRID_POWER_MAX  = "sell_to_grid_max_power_limit"

# workModel values. Inferred from a station reading 1 while the Modbus
# battery_mode register also read 1 (self_consumption); TOU is the only other
# mode the portal offers. Not seen written down in any Atmoce document.
WORK_MODE_SELF_POWERED = 1
WORK_MODE_TOU          = 2

# How often to re-read the portal. Settings can be changed from the ATMOZEN app
# and nothing tells us when that happens, so it has to be polled — but slowly:
# this is an undocumented API and the Modbus loop already runs every few seconds.
WEB_REFRESH_SECONDS = 15 * 60

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
CONF_BATTERY_COUNT    = "battery_count"   # stacked units of the same model
CONF_CAPACITY_KWH     = "capacity_kwh"
CONF_CHARGE_KW        = "charge_kw"
CONF_DISCHARGE_KW     = "discharge_kw"
CONF_CLOUD_ENABLED    = "cloud_enabled"
CONF_CLOUD_APP_KEY    = "cloud_app_key"
CONF_CLOUD_APP_SECRET = "cloud_app_secret"
CONF_CLOUD_WEB_EMAIL    = "cloud_web_email"     # atmocecloud.com login (for SOC limits)
CONF_CLOUD_WEB_PASSWORD = "cloud_web_password"
CONF_RETRY_COUNT      = "modbus_retry_count"

# Stacked batteries of the same model. Capacity adds up unit by unit; the power
# figures are multiplied too, which assumes the gateway is not the limiting
# factor. Anyone whose inverter caps total power can enter the real totals with
# the manual battery option instead.
DEFAULT_BATTERY_COUNT = 1
MAX_BATTERY_COUNT     = 16

# The only battery Atmoce actually ships as a unit. MS-14K-U is two of these in
# one box, so setup asks for a count instead of a model. The catalogue keeps
# both: entries created before the count existed still carry "MS-14K-U", and
# that string is the device model shown in Home Assistant.
UNIT_BATTERY_MODEL = "MS-7K-U"

# Routing flag on the battery step — never stored in the config entry.
CONF_MANUAL_SPECS = "manual_specs"

# Credentials live in entry.data only. The options flow edits them in place there
# instead of writing a second copy into entry.options, so a secret is never
# persisted twice on disk.
CREDENTIAL_KEYS = (
    CONF_CLOUD_APP_KEY,
    CONF_CLOUD_APP_SECRET,
    CONF_CLOUD_WEB_EMAIL,
    CONF_CLOUD_WEB_PASSWORD,
)

# Base host for the private web-portal API (login + storageModel)
CLOUD_WEB_BASE_URL = "https://www.atmocecloud.com"

# ── Active data source ───────────────────────────────────────────────────────
SOURCE_MODBUS = "Modbus"
SOURCE_CLOUD  = "Cloud"
