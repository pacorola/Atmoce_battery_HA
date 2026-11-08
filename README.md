<p align="left">
  <img src="custom_components/atmoce/brand/logo.png" alt="Atmoce Battery" width="300">
</p>

# Atmoce Battery — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/default)
[![GitHub release](https://img.shields.io/github/release/pacorola/Atmoce_battery_HA.svg)](https://github.com/pacorola/Atmoce_battery_HA/releases)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-support-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/pacorola)

Full local control and monitoring of **Atmoce solar + battery systems** over **Modbus TCP**, plus the settings that only exist in the Atmoce portal.

Fully tested and working with the **Atmoce MS-7K-U** (7 kWh LFP battery). Should be compatible with MC100, MC100-T and MG100 gateways. Try it on your installation and please report back so anything broken can be fixed.

---

## Installation

**Requires Home Assistant 2024.12.0 or newer** — HACS will not offer the integration to older cores.

### HACS (recommended)

Atmoce Battery is in the **HACS default store**, so no custom repository is needed.

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=pacorola&repository=Atmoce_battery_HA&category=integration)

The button above opens this repository straight in your own HACS. To do it by hand:

1. Open **HACS** in Home Assistant and search for **Atmoce Battery**.
2. Press **Download**.
3. **Restart Home Assistant** — the integration is not offered in the Add Integration list until you do.
4. Continue with [Setup](#setup).

### Manual

Download the [latest release](https://github.com/pacorola/Atmoce_battery_HA/releases/latest), copy its `custom_components/atmoce` folder into your Home Assistant `config/custom_components/` directory, and restart Home Assistant.

---

## Features

- **24 sensors and two problem binary sensors** — grid, solar, battery, plus computed autonomy and self-consumption
- **Battery control over Modbus** — force charge or discharge with a target SOC, a duration, or both. Entirely local; no account needed
- **Battery limits** — end-of-charge, end-of-discharge and backup reserve, which Modbus does not expose. Needs your ordinary atmocecloud.com login
- **Standing policy** — self-powered or time-of-use, grid charging and export, each with its own power cap and SOC bound. Also from the portal
- **Battery count** in setup — say how many units you have and capacity and power limits follow, changeable later via **Reconfigure** without reinstalling
- **Cloud monitoring fallback** (optional, rarely needed) if the gateway stops answering over Modbus. Requires partner API keys that Atmoce issues to installers
- **Diagnostics** — full state export with credentials and site identity redacted
- **Trilingual** — English, Spanish and French, entity names and select options included

---

## Setup

1. Go to **Settings → Devices & Services → Add Integration** and search for **Atmoce Battery**.
2. **Gateway** — the local IP of your MC100 / MG100. Connectivity is verified before continuing.
3. **Batteries** — how many MS-7K-U units are installed. Capacity and power limits follow from that; tick **Enter specifications manually** for different hardware.
4. **atmocecloud.com account** (optional) — your ordinary portal login, the same one as the ATMOZEN app. Needed for the battery limits and the standing policy. Everything else works without it.
5. **Cloud monitoring fallback** (optional, advanced) — almost nobody needs this; submit it untouched. See the FAQ on `app_key`.

> The gateway must have **Modbus TCP enabled** on port 502 with no authentication. That is the factory default.

Modbus is polled every **10 seconds**. The portal is re-read every **15 minutes** and after every change, so edits made in the ATMOZEN app show up here too.

---

## Entities

**Entity IDs include the device name**, which is `Atmoce` plus your battery model — so with an MS-7K-U they all begin `atmoce_ms_7k_u_`. The tables below spell that out. If your device was renamed, or you set up manual specs, your prefix differs: check **Developer Tools → States** and filter by `atmoce`.

Entities are grouped by category on the device page. The operating controls sit at the top, settings collect under **Configuration**, and connection health under **Diagnostic**.

### Sensors

| Entity | Unit | Description |
|--------|------|-------------|
| `sensor.atmoce_ms_7k_u_grid_voltage` | V | Grid voltage |
| `sensor.atmoce_ms_7k_u_grid_current` | A | Grid current (signed) |
| `sensor.atmoce_ms_7k_u_grid_power` | W | Grid active power (positive = importing) |
| `sensor.atmoce_ms_7k_u_grid_energy_daily` | kWh | Imported today |
| `sensor.atmoce_ms_7k_u_grid_energy_total` | kWh | Imported, lifetime |
| `sensor.atmoce_ms_7k_u_electricity_sold_daily` | kWh | Exported today |
| `sensor.atmoce_ms_7k_u_electricity_sold_total` | kWh | Exported, lifetime |
| `sensor.atmoce_ms_7k_u_pv_power` | W | Solar generation now |
| `sensor.atmoce_ms_7k_u_pv_energy_daily` | kWh | Solar produced today |
| `sensor.atmoce_ms_7k_u_pv_energy_total` | kWh | Solar produced, lifetime |
| `sensor.atmoce_ms_7k_u_pv_self_consumption_rate` | % | Solar used on site (computed) |
| `sensor.atmoce_ms_7k_u_battery_soc` | % | State of charge |
| `sensor.atmoce_ms_7k_u_battery_power` | W | Signed: negative charges, positive discharges |
| `sensor.atmoce_ms_7k_u_battery_status` | — | `charging` / `discharging` / `idle` |
| `sensor.atmoce_ms_7k_u_battery_operating_mode` | — | `self_consumption` / `tou` / `remote_control` |
| `sensor.atmoce_ms_7k_u_battery_dispatch_power` | W | Dispatch setpoint readback |
| `sensor.atmoce_ms_7k_u_battery_charged_daily` | kWh | Charged today |
| `sensor.atmoce_ms_7k_u_battery_discharged_daily` | kWh | Discharged today |
| `sensor.atmoce_ms_7k_u_battery_charged_total` | kWh | Charged, lifetime |
| `sensor.atmoce_ms_7k_u_battery_discharged_total` | kWh | Discharged, lifetime |
| `sensor.atmoce_ms_7k_u_battery_autonomy` | h | Hours left at current draw (computed) |
| `sensor.atmoce_ms_7k_u_station_status` | — | `normal` / `fault` |
| `sensor.atmoce_ms_7k_u_active_data_source` | — | `Modbus` / `Cloud` *(diagnostic)* |
| `sensor.atmoce_ms_7k_u_connection_errors` | — | Cumulative Modbus failures *(diagnostic)* |
| `binary_sensor.atmoce_ms_7k_u_battery_problem` | — | On if the battery looks stuck: charge pinned at zero while the panels produce *(diagnostic)* |
| `binary_sensor.atmoce_ms_7k_u_grid_outage` | — | On while the house runs off grid on the battery; unknown on firmware older than 01.01.00.25 |

> The four `_total` counters come from the gateway itself, so they are the ones to feed the Energy dashboard — no Riemann sum over the power sensors needed.

### Battery control (Modbus, local)

| Entity | Description |
|--------|-------------|
| `select.atmoce_ms_7k_u_battery_command` | `forced_charge` / `forced_discharge` / `battery_managed`. Picking a forced option takes remote control and applies the parameters below; `battery_managed` exits forced mode and hands control back |
| `switch.atmoce_ms_7k_u_remote_control` | Whether the battery obeys Modbus at all. The command select turns it on and off for you; set it by hand only to use dispatch power |
| `number.atmoce_ms_7k_u_forced_target_soc` | Charge or discharge until this SOC *(config)* |
| `number.atmoce_ms_7k_u_forced_duration` | Run for this many minutes, 0–1440 *(config)* |
| `number.atmoce_ms_7k_u_forced_power` | Power to force with, up to the battery rating *(config)* |
| `select.atmoce_ms_7k_u_forced_mode_type` | `target_soc` / `duration` / `soc_duration` — which of the two above applies *(config)* |
| `number.atmoce_ms_7k_u_dispatch_power` | Direct power setpoint in kW, negative to charge. Only available while remote control is on, since that is the only mode the battery follows it in *(config)* |
| `button.atmoce_ms_7k_u_reset_gateway` | Restart the gateway *(config)* |

The three forced parameters are **arguments to the command, not controls of their own**. Setting one changes nothing on the battery: the value waits in Home Assistant and is written when you pick a forced command. So the order does not matter, and adjusting one never pulls a self-managing battery out of its mode.

### Battery limits and standing policy (atmocecloud.com login)

Not available over Modbus — the protocol exposes read-only power limits and no reserve register. These are read and written through the **same private portal API the ATMOZEN app uses**, signed in with your **ordinary email and password**; no partner API keys. Enter the login under **Settings → Devices & Services → Atmoce Battery → Configure**. Without it these entities stay unavailable and the rest works normally.

| Entity | Portal field | Description |
|--------|--------------|-------------|
| `number.atmoce_ms_7k_u_charge_limit_soc` | `storageChargeCutoffSoc` | Charging stops here (80–100 %) |
| `number.atmoce_ms_7k_u_discharge_limit_soc` | `storageDischargeCutoffSoc` | Discharging stops here (0–30 %) |
| `number.atmoce_ms_7k_u_backup_reserve_soc` | `backupSoc` | Kept back for outages; the battery stops here except on grid failure |
| `select.atmoce_ms_7k_u_self_managed_mode` | `workModel` | `self_powered` / `time_of_use` — what the battery does when left alone |
| `switch.atmoce_ms_7k_u_grid_charging` | `gridCharge` | Allow charging from the grid |
| `number.atmoce_ms_7k_u_grid_charge_power` | `gridChargeMaxPower` | Grid charge power cap, in watts |
| `number.atmoce_ms_7k_u_grid_charge_limit_soc` | `storageGridChargeCutoffSoc` | Charge from the grid up to this SOC |
| `switch.atmoce_ms_7k_u_export_to_grid` | `storageSellToGridStatus` | Allow exporting stored energy |
| `number.atmoce_ms_7k_u_export_power` | `storageSellToGridMaxPower` | Export power cap, in watts |
| `number.atmoce_ms_7k_u_export_above_soc` | `storageSellToGridUpSOC` | Export only above this SOC |

The four bounds are nested under their switch: with the behaviour off they show as unavailable, since there is nothing for them to apply to.

**Time-of-use schedules are not editable from here** — configure the time bands in the Atmoce portal. The select only chooses which policy is in force, and switching to `time_of_use` without any band configured leaves the battery in a mode with no schedule.

> This is an unofficial API and may change if Atmoce updates their portal.

### Select options are slugs

The value of a select is a slug; the label you see is translated. Automations must use the slug — `option: "forced_charge"`, not the visible text.

| Select | Values |
|--------|--------|
| `battery_command` | `forced_charge`, `forced_discharge`, `battery_managed` |
| `forced_mode_type` | `target_soc`, `duration`, `soc_duration` |
| `self_managed_mode` | `self_powered`, `time_of_use` |

---

## Example automation — charge to 80 % on the night rate

```yaml
automation:
  - alias: "Atmoce — Force charge at night rate"
    triggers:
      - trigger: time
        at: "01:00:00"
    actions:
      # No need to touch remote control, and no need to order these carefully:
      # the numbers wait in Home Assistant, and the command applies them after
      # taking control.
      - action: number.set_value
        target:
          entity_id: number.atmoce_ms_7k_u_forced_target_soc
        data:
          value: 80
      - action: number.set_value
        target:
          entity_id: number.atmoce_ms_7k_u_forced_power
        data:
          value: 3.5
      - action: select.select_option
        target:
          entity_id: select.atmoce_ms_7k_u_forced_mode_type
        data:
          option: "target_soc"
      - action: select.select_option
        target:
          entity_id: select.atmoce_ms_7k_u_battery_command
        data:
          option: "forced_charge"

  - alias: "Atmoce — Back to automatic once charged"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.atmoce_ms_7k_u_battery_soc
        above: 80
    actions:
      - action: select.select_option
        target:
          entity_id: select.atmoce_ms_7k_u_battery_command
        data:
          option: "battery_managed"
```

A standing policy is often the better tool: **grid charging with a cutoff SOC** survives a Home Assistant restart and needs no automation at all.

---

## FAQ

**Setup cannot connect to the gateway.**
Check that Modbus TCP is enabled on port 502 — the factory default. If you changed the port, enter it in the wizard.

**My entity IDs do not match the tables above.**
They are built from the device name, which includes your battery model. Filter by `atmoce` in **Developer Tools → States** to see yours.

**A battery command does nothing.**
The battery ignores Modbus writes in local mode. Since v1.3.5 this is handled for you: picking a forced command takes remote control first. On older versions turn `switch.…_remote_control` on by hand before sending anything.

**I set a target SOC and nothing happened.**
That is intended — it is a parameter, not a command. Pick a forced option in `select.…_battery_command` to apply it.

**I added a second battery.**
Use **⋮ → Reconfigure** on the integration and change the count. Capacity and power limits are recalculated; entity history is kept.

**Where do I get `app_key` and `app_secret`?**
You almost certainly do not need them — the battery limits use your ordinary portal login. These are partner Open API credentials for the monitoring fallback, meant for installers managing several sites, and per the Open API manual §3.1.2 they are requested by email from Atmoce support. No page generates them.

**Sensors go unavailable after a while.**
The gateway has stopped answering over Modbus. Check its network connection; `sensor.…_connection_errors` counts the failures and `sensor.…_active_data_source` tells you what is being read.

**Autonomy is unavailable.**
It needs a few minutes of readings to average consumption, and it hides when consumption is negligible.

---

## Contributing

Pull requests are welcome — no need to open an issue first. Atmoce's Modbus and Cloud API documentation is in the project wiki for reference.

## Support

This integration is free and always will be. If it saved you an afternoon of reverse-engineering Modbus registers, you can say thanks with a coffee.

<a href="https://buymeacoffee.com/pacorola" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="48" width="174"></a>

## License

MIT — see [LICENSE](LICENSE).
