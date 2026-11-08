"""Tests for AtmoceSensor entity."""
from unittest.mock import MagicMock

import pytest

from custom_components.atmoce.sensor import AtmoceSensor, SENSOR_DESCRIPTIONS, _device_info
from custom_components.atmoce.const import DOMAIN


def _make_coordinator(data: dict):
    coord = MagicMock()
    coord.data = data
    coord.serial_number = "SN123456"
    coord.battery_model = "MS-7K-U"
    coord.firmware_version = "1.0.0"
    coord.hw_version = 1
    coord.config_entry.data = {"host": "192.168.1.100"}
    return coord


class TestAtmoceSensorNativeValue:
    def _make_sensor(self, key: str, data: dict) -> AtmoceSensor:
        description = next(d for d in SENSOR_DESCRIPTIONS if d.key == key)
        coordinator = _make_coordinator(data)
        sensor = AtmoceSensor.__new__(AtmoceSensor)
        sensor.coordinator = coordinator
        sensor.entity_description = description
        return sensor

    def test_numeric_value_returned(self):
        sensor = self._make_sensor("grid_power", {"grid_power": 1500})
        assert sensor.native_value == 1500

    def test_none_when_key_missing(self):
        sensor = self._make_sensor("grid_power", {})
        assert sensor.native_value is None

    def test_none_when_value_is_none(self):
        sensor = self._make_sensor("pv_power", {"pv_power": None})
        assert sensor.native_value is None

    def test_battery_status_charging(self):
        sensor = self._make_sensor("battery_status", {"battery_status": 1})
        assert sensor.native_value == "charging"

    def test_battery_status_discharging(self):
        sensor = self._make_sensor("battery_status", {"battery_status": 2})
        assert sensor.native_value == "discharging"

    def test_battery_status_idle(self):
        sensor = self._make_sensor("battery_status", {"battery_status": 99})
        assert sensor.native_value == "idle"

    def test_battery_status_unknown_code(self):
        # Unknown status code → returned as string
        sensor = self._make_sensor("battery_status", {"battery_status": 42})
        assert sensor.native_value == "42"

    def test_battery_mode_self_consumption(self):
        sensor = self._make_sensor("battery_mode", {"battery_mode": 1})
        assert sensor.native_value == "self_consumption"

    def test_battery_mode_tou(self):
        sensor = self._make_sensor("battery_mode", {"battery_mode": 2})
        assert sensor.native_value == "tou"

    def test_battery_mode_remote_control(self):
        sensor = self._make_sensor("battery_mode", {"battery_mode": 10})
        assert sensor.native_value == "remote_control"

    def test_station_status_normal(self):
        sensor = self._make_sensor("station_status", {"station_status": 0})
        assert sensor.native_value == "normal"

    def test_station_status_fault(self):
        sensor = self._make_sensor("station_status", {"station_status": 1})
        assert sensor.native_value == "fault"

    def test_float_value(self):
        sensor = self._make_sensor("grid_voltage", {"grid_voltage": 230.4})
        assert sensor.native_value == 230.4

    def test_active_source(self):
        sensor = self._make_sensor("active_source", {"active_source": "Modbus"})
        assert sensor.native_value == "Modbus"


class TestSensorDescriptions:
    def test_all_descriptions_have_data_key(self):
        for desc in SENSOR_DESCRIPTIONS:
            assert desc.data_key, f"Sensor {desc.key} is missing data_key"

    def test_all_descriptions_have_unique_keys(self):
        keys = [d.key for d in SENSOR_DESCRIPTIONS]
        assert len(keys) == len(set(keys)), "Duplicate sensor keys found"

    def test_expected_sensor_count(self):
        # 24 sensors defined in SENSOR_DESCRIPTIONS
        assert len(SENSOR_DESCRIPTIONS) == 24


class TestDeviceInfo:
    def test_device_info_fields(self):
        coordinator = _make_coordinator({})
        info = _device_info(coordinator)
        assert (DOMAIN, "SN123456") in info["identifiers"]
        assert info["manufacturer"] == "Atmoce"
        assert info["model"] == "MS-7K-U"
        assert "192.168.1.100" in info["configuration_url"]


class TestGatewayWithoutBattery:
    """A gateway set up with zero batteries gets no battery entities."""

    @staticmethod
    async def _setup(has_battery: bool) -> list:
        from custom_components.atmoce.sensor import async_setup_entry

        coord = _make_coordinator({})
        coord.has_battery = has_battery
        hass = MagicMock()
        hass.data = {DOMAIN: {"entry": coord}}
        entry = MagicMock()
        entry.entry_id = "entry"
        added: list = []
        await async_setup_entry(hass, entry, lambda ents: added.extend(ents))
        return [e.entity_description.key for e in added]

    @pytest.mark.asyncio
    async def test_battery_sensors_are_left_out(self):
        keys = await self._setup(has_battery=False)
        assert not any(k.startswith("battery_") for k in keys)
        assert "autonomy_hours" not in keys
        assert {"grid_power", "pv_power", "station_status"} <= set(keys)

    @pytest.mark.asyncio
    async def test_with_a_battery_everything_is_there(self):
        keys = await self._setup(has_battery=True)
        assert len(keys) == len(SENSOR_DESCRIPTIONS)
