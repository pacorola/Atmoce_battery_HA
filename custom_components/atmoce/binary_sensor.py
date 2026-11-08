"""Binary sensor platform for Atmoce Battery."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AtmoceCoordinator
from .sensor import _device_info


class AtmoceBatteryProblem(CoordinatorEntity[AtmoceCoordinator], BinarySensorEntity):
    """Whether the battery looks stuck.

    The coordinator has computed this since the beginning but no platform ever
    exposed it, so the value was calculated on every poll and thrown away.

    Reported as a problem rather than as health, which is the Home Assistant
    convention and reads better in the UI: on means something is wrong. The
    underlying check is deliberately narrow — a state of charge pinned at zero
    while the panels are producing — so it stays off in normal operation,
    including overnight at a genuine zero.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "battery_problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AtmoceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_battery_problem"
        self._attr_device_info = _device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        healthy = self.coordinator.data.get("battery_healthy")
        return None if healthy is None else not healthy


class AtmoceGridOutage(CoordinatorEntity[AtmoceCoordinator], BinarySensorEntity):
    """On while the gateway reports Off Grid.

    The house then runs on the battery through the backup box. Unknown when the
    firmware is older than protocol V1.5 or the value is missing.

    Not diagnostic, unlike the battery problem: it describes the house's supply,
    something to automate on, not the health of the hardware.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "grid_outage"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: AtmoceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_grid_outage"
        self._attr_device_info = _device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        status = self.coordinator.data.get("grid_status")
        return None if status is None else status == 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AtmoceCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [AtmoceBatteryProblem(coordinator), AtmoceGridOutage(coordinator)]
    )
