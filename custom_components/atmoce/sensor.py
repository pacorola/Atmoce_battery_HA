"""Sensor entities for Atmoce Battery integration."""
from __future__ import annotations

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
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
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
    ),
    AtmoceeSensorDescription(
        key="connection_errors",
        data_key="connection_errors",
        name="Connection Errors",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:alert-network",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AtmoceCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AtmoceSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


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
