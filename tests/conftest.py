"""Shared fixtures for Atmoce Battery tests."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.atmoce.coordinator import AtmoceCoordinator


@pytest.fixture
def mock_config_entry():
    """Minimal config entry with default values."""
    entry = MagicMock()
    entry.data = {
        "host": "192.168.1.100",
        "port": 502,
        "slave": 1,
        "battery_model": "MS-7K-U",
        "capacity_kwh": 7.0,
        "charge_kw": 3.75,
        "discharge_kw": 4.5,
        "cloud_enabled": False,
        "cloud_app_key": "",
        "cloud_app_secret": "",
        "modbus_retry_count": 3,
        "serial_number": "SN123456",
    }
    entry.options = {}
    return entry


@pytest.fixture
def mock_hass():
    """Minimal Home Assistant instance mock."""
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def coordinator(mock_hass, mock_config_entry):
    """AtmoceCoordinator with mocked Modbus client."""
    coord = AtmoceCoordinator(mock_hass, mock_config_entry)
    coord._modbus = MagicMock()
    coord._modbus.connected = True
    coord._modbus.async_fetch_all = AsyncMock()
    coord._modbus.async_set_remote_control = AsyncMock()
    coord._modbus.async_set_forced_command = AsyncMock()
    coord._modbus.async_set_forced_mode = AsyncMock()
    coord._modbus.async_set_forced_target_soc = AsyncMock()
    coord._modbus.async_set_forced_duration = AsyncMock()
    coord._modbus.async_set_forced_power = AsyncMock()
    coord._modbus.async_set_dispatch_power = AsyncMock()
    coord._modbus.async_reset_gateway = AsyncMock()
    coord._modbus.async_read_microinverters = AsyncMock(return_value=[])
    return coord
