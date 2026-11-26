"""Sensor entities for Atmoce Battery integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AtmoceCoordinator


@dataclass(frozen=True, kw_only=True)
class AtmoceeSensorDescription(SensorEntityDescription):
    data_key: str
    value_map: dict[int, str] | None = None  # for status enums


SENSOR_DESCRIPTIONS: tuple[AtmoceeSensorDescription, ...] = (
    # ── Grid ──────────────────────────────────────────────────────────────────
    AtmoceeSensorDescription(
        key="grid_voltage",
        data_key="grid_voltage",
        name="Grid Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
    ),
    AtmoceeSensorDescription(
        key="grid_current",
        data_key="grid_current",
        name="Grid Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
    ),
    AtmoceeSensorDescription(
        key="grid_power",
        data_key="grid_power",
        name="Grid Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
    ),
    AtmoceeSensorDescription(
        key="grid_energy_daily",
        data_key="grid_energy_daily",
        name="Grid Energy Daily",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    AtmoceeSensorDescription(
        key="grid_energy_total",
        data_key="grid_energy_total",
        name="Grid Energy Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    AtmoceeSensorDescription(
        key="elec_sales_daily",
        data_key="elec_sales_daily",
        name="Electricity Sold Daily",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    AtmoceeSensorDescription(
        key="elec_sales_total",
        data_key="elec_sales_total",
        name="Electricity Sold Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    # ── PV ────────────────────────────────────────────────────────────────────
    AtmoceeSensorDescription(
        key="pv_power",
        data_key="pv_power",
        name="PV Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
    ),
    AtmoceeSensorDescription(
        key="pv_energy_daily",
        data_key="pv_energy_daily",
        name="PV Energy Daily",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    AtmoceeSensorDescription(
        key="pv_energy_total",
        data_key="pv_energy_total",
        name="PV Energy Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    AtmoceeSensorDescription(
        key="pv_self_consumption_rate",
        data_key="pv_self_consumption_rate",
        name="PV Self Consumption Rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        icon="mdi:solar-power",
    ),
    # ── Battery ───────────────────────────────────────────────────────────────
    AtmoceeSensorDescription(
        key="battery_soc",
        data_key="battery_soc",
        name="Battery SOC",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    AtmoceeSensorDescription(
        key="battery_power",
        data_key="battery_power",
        name="Battery Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
    ),
    AtmoceeSensorDescription(
        key="battery_status",
        data_key="battery_status",
        name="Battery Status",
        icon="mdi:battery-charging",
        value_map={1: "charging", 2: "discharging", 99: "idle"},
    ),
    AtmoceeSensorDescription(
        key="battery_mode",
        data_key="battery_mode",
        name="Battery Operating Mode",
        icon="mdi:battery-sync",
        value_map={1: "self_consumption", 2: "tou", 10: "remote_control"},
    ),
    AtmoceeSensorDescription(
        key="battery_dispatch_power",
        data_key="battery_dispatch_power",
        name="Battery Dispatch Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
    ),
    AtmoceeSensorDescription(
        key="battery_charged_daily",
        data_key="battery_charged_daily",
        name="Battery Charged Daily",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    AtmoceeSensorDescription(
        key="battery_discharged_daily",
        data_key="battery_discharged_daily",
        name="Battery Discharged Daily",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    AtmoceeSensorDescription(
        key="battery_charged_total",
        data_key="battery_charged_total",
        name="Battery Charged Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    AtmoceeSensorDescription(
        key="battery_discharged_total",
        data_key="battery_discharged_total",
        name="Battery Discharged Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
    ),
    AtmoceeSensorDescription(
        key="autonomy_hours",
        data_key="autonomy_hours",
        name="Battery Autonomy",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        icon="mdi:battery-clock",
    ),
    # ── System ────────────────────────────────────────────────────────────────
    AtmoceeSensorDescription(
        key="station_status",
        data_key="station_status",
        name="Station Status",
        icon="mdi:solar-power-variant",
        value_map={0: "normal", 1: "fault"},
    ),
    AtmoceeSensorDescription(
        key="active_source",
        data_key="active_source",
        name="Active Data Source",
        icon="mdi:connection",
        # About the integration's health, not the energy system's behaviour.
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AtmoceeSensorDescription(
        key="connection_errors",
        data_key="connection_errors",
        name="Connection Errors",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:alert-network",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


# Left out on a gateway set up with zero batteries.
BATTERY_SENSOR_KEYS = frozenset(
    d.key for d in SENSOR_DESCRIPTIONS if d.key.startswith("battery_")
) | {"autonomy_hours"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AtmoceCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AtmoceSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if coordinator.has_battery or description.key not in BATTERY_SENSOR_KEYS
    )

    # Microinverters: one device each, added as the gateway reports them (a
    # failed first read, or a microinverter added later, shows up on a later
    # poll without a reload).
    known: set[str] = set()

    @callback
    def _add_new_microinverters() -> None:
        new_entities: list[SensorEntity] = []
        for mi in coordinator.microinverters:
            serial = mi["serial_number"]
            if serial in known:
                continue
            known.add(serial)
            new_entities.extend(
                AtmoceMicroinverterSensor(coordinator, serial, description, None)
                for description in MI_SENSOR_DESCRIPTIONS
            )
            for channel in range(len(mi["channels"])):
                new_entities.extend(
                    AtmoceMicroinverterSensor(coordinator, serial, description, channel)
                    for description in MI_CHANNEL_SENSOR_DESCRIPTIONS
                )
        if new_entities:
            async_add_entities(new_entities)

    _add_new_microinverters()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_microinverters))


class AtmoceSensor(CoordinatorEntity[AtmoceCoordinator], SensorEntity):
    """A single Atmoce sensor entity."""

    entity_description: AtmoceeSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AtmoceCoordinator,
        description: AtmoceeSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        # Every sensor key has a matching entry under `entity.sensor` in the
        # translation files, so the name comes from there. The `name` on the
        # description stays as the fallback for a key without a translation.
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> Any:
        raw = self.coordinator.data.get(self.entity_description.data_key)
        if raw is None:
            return None
        value_map = self.entity_description.value_map
        if value_map and isinstance(raw, int):
            return value_map.get(raw, str(raw))
        return raw


def _device_info(coordinator: AtmoceCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.serial_number)},
        name=f"Atmoce {coordinator.battery_model}",
        manufacturer="Atmoce",
        model=coordinator.battery_model,
        sw_version=coordinator.firmware_version,
        hw_version=str(coordinator.hw_version),
        configuration_url=f"http://{coordinator.config_entry.data['host']}",
    )


# ── Microinverters ────────────────────────────────────────────────────────────
# Read from undocumented per-microinverter register blocks (see const.MI_*).

@dataclass(frozen=True, kw_only=True)
class AtmoceMicroinverterSensorDescription(SensorEntityDescription):
    """A value of one microinverter, or of one of its PV inputs (panels)."""
    value_fn: Callable[[dict[str, Any]], Any]


def _mi_energy(key: str, name: str) -> AtmoceMicroinverterSensorDescription:
    data_key = key.removeprefix("mi_").removeprefix("panel_")
    return AtmoceMicroinverterSensorDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda d: d.get(data_key),
    )


MI_SENSOR_DESCRIPTIONS: tuple[AtmoceMicroinverterSensorDescription, ...] = (
    AtmoceMicroinverterSensorDescription(
        key="mi_ac_power",
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda d: d.get("ac_power"),
    ),
    _mi_energy("mi_energy_daily", "Energy Daily"),
    _mi_energy("mi_energy_total", "Energy Total"),
    AtmoceMicroinverterSensorDescription(
        key="mi_ac_voltage",
        name="AC Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("ac_voltage"),
    ),
    AtmoceMicroinverterSensorDescription(
        key="mi_ac_frequency",
        name="AC Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("ac_frequency"),
    ),
    AtmoceMicroinverterSensorDescription(
        key="mi_temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("temperature"),
    ),
)

MI_CHANNEL_SENSOR_DESCRIPTIONS: tuple[AtmoceMicroinverterSensorDescription, ...] = (
    AtmoceMicroinverterSensorDescription(
        key="panel_power",
        name="Panel {channel} Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda d: d.get("power"),
    ),
    _mi_energy("panel_energy_daily", "Panel {channel} Energy Daily"),
    _mi_energy("panel_energy_total", "Panel {channel} Energy Total"),
    AtmoceMicroinverterSensorDescription(
        key="panel_dc_voltage",
        name="Panel {channel} DC Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("dc_voltage"),
    ),
    AtmoceMicroinverterSensorDescription(
        key="panel_dc_current",
        name="Panel {channel} DC Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("dc_current"),
    ),
)


class AtmoceMicroinverterSensor(CoordinatorEntity[AtmoceCoordinator], SensorEntity):
    """A sensor of one microinverter (channel None) or of one of its panels."""

    entity_description: AtmoceMicroinverterSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AtmoceCoordinator,
        serial: str,
        description: AtmoceMicroinverterSensorDescription,
        channel: int | None,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._serial = serial
        self._channel = channel
        self._attr_translation_key = description.key
        if channel is None:
            self._attr_unique_id = f"{serial}_{description.key}"
        else:
            self._attr_unique_id = f"{serial}_ch{channel + 1}_{description.key}"
            self._attr_translation_placeholders = {"channel": str(channel + 1)}
        mi = self._mi or {}
        channels = mi.get("channel_count") or len(mi.get("channels", []))
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=f"Atmoce MI {serial}",
            manufacturer="Atmoce",
            model=f"Microinverter {channels}-in-1" if channels else "Microinverter",
            serial_number=serial,
            sw_version=mi.get("firmware") or None,
            via_device=(DOMAIN, coordinator.serial_number),
        )

    @property
    def _mi(self) -> dict[str, Any] | None:
        for mi in self.coordinator.microinverters:
            if mi["serial_number"] == self._serial:
                return mi
        return None

    @property
    def _source(self) -> dict[str, Any] | None:
        mi = self._mi
        if mi is None or self._channel is None:
            return mi
        channels = mi.get("channels", [])
        return channels[self._channel] if self._channel < len(channels) else None

    @property
    def available(self) -> bool:
        return super().available and self._source is not None

    @property
    def native_value(self) -> Any:
        source = self._source
        return None if source is None else self.entity_description.value_fn(source)
