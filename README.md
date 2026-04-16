<p align="left">
  <img src="custom_components/atmoce/icon.png" alt="Atmoce Battery" width="300">
</p>

# Atmoce Battery — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/pacorola/Atmoce_battery_HA.svg)](https://github.com/pacorola/Atmoce_battery_HA/releases)

Full local control and monitoring of **Atmoce solar + battery systems** via **Modbus TCP**, with an optional read-only Cloud API fallback.

Still under testing with the **Atmoce MS-7K-U** (7 kWh LFP battery). Should be compatible with MC100, MC100-T and MG100 gateways. Try on your installation and please report so any needed fix can be done.

---

## Features

- **27 sensor entities** — grid, PV, battery, system and computed metrics
- **Full battery control** — force charge/discharge, set target SOC, duration and power
- **"Administrado por batería" button** — one-tap return to automatic self-managed mode
- **Battery model selector** in setup — MS-7K-U pre-configured, manual entry for other models
- **Automatic Modbus→Cloud fallback** (optional) if the gateway is temporarily unreachable
- **Active data source sensor** — always know whether you are reading Modbus or Cloud
- **Computed sensors** — autonomy hours, PV self-consumption rate, battery health
- **Diagnostics support** — exportable debug info with sensitive fields redacted
- **Bilingual** — English and Spanish UI out of the box

---

## Installation via HACS

1. In Home Assistant go to **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/pacorola/Atmoce_battery_HA` as an **Integration**.
3. Search for **Atmoce Battery** and install.
4. Restart Home Assistant.

---

## Setup

1. Go to **Settings → Devices & Services → Add Integration** and search for **Atmoce Battery**.
2. **Step 1 — Gateway**: enter the local IP address of your gateway (MC100 / MG100). The integration will verify connectivity before continuing.
3. **Step 2 — Battery model**: select your model from the list or choose **Manual** to enter the capacity and power limits yourself.
4. **Step 3 — Cloud (optional)**: leave disabled for pure local operation. Enable only if you want read-only Cloud fallback when Modbus is unavailable.

> **Note**: The Atmoce Gateway must have **Modbus TCP enabled** (port 502, no authentication). This is the default factory setting.

---

## Entities

### Sensors

| Entity | Unit | Description |
|--------|------|-------------|
| `sensor.atmoce_grid_voltage` | V | Grid voltage |
| `sensor.atmoce_grid_current` | A | Grid current (signed) |
| `sensor.atmoce_grid_power` | W | Grid active power (positive = import) |
| `sensor.atmoce_grid_energy_daily` | kWh | Energy imported today |
| `sensor.atmoce_grid_energy_total` | kWh | Cumulative energy imported |
| `sensor.atmoce_electricity_sold_daily` | kWh | Energy exported today |
| `sensor.atmoce_electricity_sold_total` | kWh | Cumulative energy exported |
| `sensor.atmoce_pv_power` | W | Current solar generation |
| `sensor.atmoce_pv_energy_daily` | kWh | Solar produced today |
| `sensor.atmoce_pv_energy_total` | kWh | Cumulative solar produced |
| `sensor.atmoce_pv_self_consumption_rate` | % | Solar consumed directly (computed) |
| `sensor.atmoce_battery_soc` | % | State of charge |
| `sensor.atmoce_battery_power` | W | Charge/discharge power |
| `sensor.atmoce_battery_status` | — | charging / discharging / idle |
| `sensor.atmoce_battery_operating_mode` | — | self_consumption / tou / remote_control |
| `sensor.atmoce_battery_dispatch_power` | W | Dispatch setpoint readback |
| `sensor.atmoce_battery_charged_daily` | kWh | Charged today |
| `sensor.atmoce_battery_discharged_daily` | kWh | Discharged today |
| `sensor.atmoce_battery_charged_total` | kWh | Cumulative charged |
| `sensor.atmoce_battery_discharged_total` | kWh | Cumulative discharged |
| `sensor.atmoce_battery_autonomy` | h | Estimated hours of autonomy (computed) |
| `sensor.atmoce_station_status` | — | normal / fault |
| `sensor.atmoce_active_data_source` | — | Modbus / Cloud |
| `sensor.atmoce_connection_errors` | — | Cumulative Modbus failures |
| `binary_sensor.atmoce_battery_healthy` | — | False if battery appears stuck |

### Controls

| Entity | Description |
|--------|-------------|
| `switch.atmoce_remote_control` | Enable/disable remote Modbus control. **Must be ON before sending commands.** |
| `number.atmoce_forced_target_soc` | Target SOC for forced charge/discharge (0–100 %) |
| `number.atmoce_forced_duration` | Duration for forced operation (0–1440 min) |
| `number.atmoce_forced_power` | Power for forced charge (0–max charge kW) |
| `number.atmoce_dispatch_power` | Dispatch power setpoint in kW (negative = charge) |
| `select.atmoce_battery_command` | Carga forzada / Descarga forzada / Administrado por batería |
| `select.atmoce_forced_mode_type` | SOC objetivo / Duración / SOC + Duración |
| `button.atmoce_administrado_por_bateria` | One-tap return to automatic mode |
| `button.atmoce_reset_gateway` | Reset the Atmoce gateway |

---

## Example automation — charge to 80 % at cheap-rate hours

```yaml
automation:
  - alias: "Atmoce — Force charge at night rate"
    trigger:
      - platform: time
        at: "01:00:00"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.atmoce_remote_control
      - delay: "00:00:02"
      - service: number.set_value
        target:
          entity_id: number.atmoce_forced_target_soc
        data:
          value: 80
      - service: number.set_value
        target:
          entity_id: number.atmoce_forced_power
        data:
          value: 3.5
      - service: select.select_option
        target:
          entity_id: select.atmoce_forced_mode_type
        data:
          option: "SOC objetivo"
      - service: select.select_option
        target:
          entity_id: select.atmoce_battery_command
        data:
          option: "Carga forzada"

  - alias: "Atmoce — Return to auto when SOC reached"
    trigger:
      - platform: numeric_state
        entity_id: sensor.atmoce_battery_soc
        above: 80
    action:
      - service: button.press
        target:
          entity_id: button.atmoce_administrado_por_bateria
```

---

## FAQ

**The integration fails to connect during setup.**
Make sure the gateway (MC100 / MG100) has Modbus TCP enabled on port 502. This is the default factory setting. If you changed the port, enter it in the setup wizard.

**Buttons / controls don't appear in Home Assistant.**
Reload the integration from Settings → Devices & Services → Atmoce Battery → ⋮ → Reload. If the problem persists, restart Home Assistant.

**The battery commands have no effect.**
The `switch.atmoce_remote_control` must be turned **ON** before sending any charge/discharge command. The battery ignores Modbus write commands when in local mode.

**Sensors show "unavailable" after a few hours.**
Enable the Cloud fallback in the integration options (Settings → Devices & Services → Atmoce Battery → Configure) and enter your Atmoce Cloud API credentials. The integration will switch automatically when Modbus is unreachable.

**How do I know if data is coming from Modbus or Cloud?**
Check `sensor.atmoce_active_data_source` — it shows `Modbus` or `Cloud`.

**Autonomy hours sensor is unavailable.**
The sensor needs at least a few minutes of data to calculate a rolling average consumption. It will appear automatically after the first valid readings.

---

## Contributing

Pull requests are welcome. No need to open an issue first — just submit the PR. ATMOCE technical documentation on Cloud API and MODBUS protocol are uploaded in the project wiki for reference.

## License

Public domain — see [LICENSE](LICENSE). No rights reserved.
