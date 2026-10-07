"""Tests for the binary sensors."""
from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.atmoce.binary_sensor import (
    AtmoceBatteryProblem,
    AtmoceGridOutage,
)


def _entity(data: dict, cls=AtmoceBatteryProblem):
    coord = MagicMock()
    coord.data = data
    coord.serial_number = "SN123456"
    entity = cls.__new__(cls)
    entity.coordinator = coord
    return entity


class TestBatteryProblem:
    """The coordinator computes health; the sensor reports the inverse."""

    def test_healthy_battery_reports_no_problem(self):
        assert _entity({"battery_healthy": True}).is_on is False

    def test_unhealthy_battery_reports_a_problem(self):
        assert _entity({"battery_healthy": False}).is_on is True

    def test_missing_value_is_unknown_not_a_problem(self):
        """Absent data must not raise an alarm on its own."""
        assert _entity({}).is_on is None

    def test_device_class_makes_on_mean_trouble(self):
        entity = _entity({"battery_healthy": True})
        assert entity.device_class == BinarySensorDeviceClass.PROBLEM


class TestGridOutage:
    """On means the gateway reports Off Grid (register 60096 = 1)."""

    def test_off_grid_reports_an_outage(self):
        assert _entity({"grid_status": 1}, AtmoceGridOutage).is_on is True

    def test_on_grid_reports_no_outage(self):
        assert _entity({"grid_status": 0}, AtmoceGridOutage).is_on is False

    def test_missing_value_is_unknown(self):
        """Older firmware has no such register: unknown, not an outage."""
        assert _entity({}, AtmoceGridOutage).is_on is None
        assert _entity({"grid_status": None}, AtmoceGridOutage).is_on is None

    def test_device_class_and_category(self):
        entity = _entity({"grid_status": 0}, AtmoceGridOutage)
        assert entity.device_class == BinarySensorDeviceClass.PROBLEM
        assert entity.entity_category is None
