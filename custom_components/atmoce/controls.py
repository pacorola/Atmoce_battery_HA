"""Switch, Number, Select and Button entities for Atmoce Battery."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.select import SelectEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import UnitOfPower, UnitOfTime, PERCENTAGE
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    FORCED_CMD_AUTO,
    FORCED_CMD_CHARGE,
    FORCED_CMD_DISCHARGE,
    FORCED_MODE_BOTH,
    FORCED_MODE_DURATION,
    FORCED_MODE_SOC,
)
from .coordinator import AtmoceCoordinator
from .sensor import _device_info

_LOGGER = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# SWITCH — Remote control mode
# ══════════════════════════════════════════════════════════════════════════════


class AtmoceRemoteControlSwitch(CoordinatorEntity[AtmoceCoordinator], SwitchEntity):
    """Switch to enable/disable remote Modbus control of the battery."""

    _attr_has_entity_name = True
    _attr_name = "Remote Control"
    _attr_icon = "mdi:remote"

    def __init__(self, coordinator: AtmoceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_remote_control"
        self._attr_device_info = _device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get("comm_control_mode") == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_remote_control(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_remote_control(False)
        await self.coordinator.async_request_refresh()


# ══════════════════════════════════════════════════════════════════════════════
# NUMBER entities
# ══════════════════════════════════════════════════════════════════════════════

class AtmoceNumber(CoordinatorEntity[AtmoceCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: AtmoceCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.serial_number}_{key}"
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get(self._key)


class AtmoceTargetSOC(AtmoceNumber):
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:battery-arrow-up"

    def __init__(self, coordinator: AtmoceCoordinator) -> None:
        super().__init__(coordinator, "forced_target_soc", "Forced Target SOC")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_forced_target_soc(int(value))
        await self.coordinator.async_request_refresh()


class AtmoceForcedDuration(AtmoceNumber):
    _attr_native_min_value = 0
    _attr_native_max_value = 1440
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: AtmoceCoordinator) -> None:
        super().__init__(coordinator, "forced_duration", "Forced Duration")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_forced_duration(int(value))
        await self.coordinator.async_request_refresh()


class AtmoceForcedPower(AtmoceNumber):
    _attr_native_min_value = 0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_icon = "mdi:flash"

    def __init__(self, coordinator: AtmoceCoordinator) -> None:
        super().__init__(coordinator, "forced_power", "Forced Power")
        # Max from battery catalogue
        self._attr_native_max_value = coordinator.max_charge_kw

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_forced_power(round(value, 2))
        await self.coordinator.async_request_refresh()


class AtmoceDispatchPower(AtmoceNumber):
    _attr_native_step = 0.05
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_icon = "mdi:battery-arrow-down-outline"

    def __init__(self, coordinator: AtmoceCoordinator) -> None:
        super().__init__(coordinator, "battery_dispatch_power", "Dispatch Power")
        self._attr_native_min_value = -coordinator.max_charge_kw
        self._attr_native_max_value = coordinator.max_discharge_kw

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.data.get("battery_dispatch_power")
        return round(raw / 1000, 2) if raw is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_dispatch_power(int(value * 1000))
        await self.coordinator.async_request_refresh()


# ══════════════════════════════════════════════════════════════════════════════
# SELECT entities
# ══════════════════════════════════════════════════════════════════════════════

class AtmoceForcedCommandSelect(CoordinatorEntity[AtmoceCoordinator], SelectEntity):
    """Select forced charge / discharge / auto mode."""

    _attr_has_entity_name = True
    _attr_name = "Battery Command"
    _attr_icon = "mdi:battery-sync"
    _attr_options = ["Forced charge", "Forced discharge", "Battery managed"]

    _CMD_TO_OPTION = {
        FORCED_CMD_CHARGE:    "Forced charge",
        FORCED_CMD_DISCHARGE: "Forced discharge",
        FORCED_CMD_AUTO:      "Battery managed",
    }
    _OPTION_TO_CMD = {v: k for k, v in _CMD_TO_OPTION.items()}

    def __init__(self, coordinator: AtmoceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_forced_command"
        self._attr_device_info = _device_info(coordinator)

    @property
    def current_option(self) -> str | None:
        raw = self.coordinator.data.get("forced_cmd")
        return self._CMD_TO_OPTION.get(raw) if raw is not None else None

    async def async_select_option(self, option: str) -> None:
        cmd = self._OPTION_TO_CMD[option]
        await self.coordinator.async_set_forced_command(cmd)
        await self.coordinator.async_request_refresh()


class AtmoceForcedModeSelect(CoordinatorEntity[AtmoceCoordinator], SelectEntity):
    """Select how forced mode is measured: SOC, duration, or both."""

    _attr_has_entity_name = True
    _attr_name = "Forced Mode Type"
    _attr_icon = "mdi:tune"
    _attr_options = ["Target SOC", "Duration", "SOC + Duration"]

    _MODE_TO_OPTION = {
        FORCED_MODE_SOC:      "Target SOC",
        FORCED_MODE_DURATION: "Duration",
        FORCED_MODE_BOTH:     "SOC + Duration",
    }
    _OPTION_TO_MODE = {v: k for k, v in _MODE_TO_OPTION.items()}

    def __init__(self, coordinator: AtmoceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_forced_mode"
        self._attr_device_info = _device_info(coordinator)

    @property
    def current_option(self) -> str | None:
        raw = self.coordinator.data.get("forced_mode")
        return self._MODE_TO_OPTION.get(raw) if raw is not None else None

    async def async_select_option(self, option: str) -> None:
        mode = self._OPTION_TO_MODE[option]
        await self.coordinator.async_set_forced_mode(mode)
        await self.coordinator.async_request_refresh()


# ══════════════════════════════════════════════════════════════════════════════
# BUTTON entities
# ══════════════════════════════════════════════════════════════════════════════

class AtmoceResetButton(CoordinatorEntity[AtmoceCoordinator], ButtonEntity):
    """Button to reset the Atmoce gateway."""

    _attr_has_entity_name = True
    _attr_name = "Reset Gateway"
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator: AtmoceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_reset"
        self._attr_device_info = _device_info(coordinator)

    async def async_press(self) -> None:
        await self.coordinator.async_reset_gateway()


class AtmoceAutoModeButton(CoordinatorEntity[AtmoceCoordinator], ButtonEntity):
    """Shortcut button: immediately return battery to self-managed mode."""

    _attr_has_entity_name = True
    _attr_name = "Administrado por batería"
    _attr_icon = "mdi:battery-heart-variant"

    def __init__(self, coordinator: AtmoceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_auto_mode"
        self._attr_device_info = _device_info(coordinator)

    async def async_press(self) -> None:
        await self.coordinator.async_set_forced_command(FORCED_CMD_AUTO)
        await self.coordinator.async_set_remote_control(False)
        await self.coordinator.async_request_refresh()
