"""Diagnostics support for Atmoce Battery."""
from __future__ import annotations
from typing import Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import CONF_CLOUD_APP_KEY, CONF_CLOUD_APP_SECRET, DOMAIN
from .coordinator import AtmoceCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: AtmoceCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Redact sensitive fields
    safe_data = dict(entry.data)
    for key in (CONF_CLOUD_APP_KEY, CONF_CLOUD_APP_SECRET):
        if key in safe_data:
            safe_data[key] = "**REDACTED**"

    return {
        "config_entry": safe_data,
        "coordinator": {
            "active_source": coordinator.active_source,
            "connection_errors": coordinator.connection_errors,
            "serial_number": coordinator.serial_number,
            "firmware_version": coordinator.firmware_version,
            "hw_version": coordinator.hw_version,
            "battery_model": coordinator.battery_model,
            "capacity_kwh": coordinator.capacity_kwh,
            "max_charge_kw": coordinator.max_charge_kw,
            "max_discharge_kw": coordinator.max_discharge_kw,
        },
        "last_data": coordinator.data,
    }
