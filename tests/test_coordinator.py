"""Tests for AtmoceCoordinator computed sensors and control methods."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.atmoce.cloud_client import AtmoceCloudAuthError, AtmoceCloudError
from custom_components.atmoce.const import (
    CLOUD_FETCH_INTERVAL,
    KEY_BATTERY_RESERVED_SOC,
    KEY_END_OF_CHARGE_SOC,
    KEY_END_OF_DISCHARGE_SOC,
    SOURCE_CLOUD,
    SOURCE_MODBUS,
)
from custom_components.atmoce.coordinator import AtmoceCoordinator


class TestComputedAutonomy:
    """Tests for the autonomy_hours derived sensor."""

    def test_autonomy_calculated_when_consuming(self, coordinator):
        data = {
            "battery_soc": 80,
            "pv_power": 0,
            "battery_power": -500,   # discharging 500 W
            "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        # 80% of 7 kWh = 5.6 kWh available; consumption ≈ 500 W → ~11.2 h
        assert result["autonomy_hours"] is not None
        assert result["autonomy_hours"] > 0

    def test_autonomy_none_when_consumption_too_low(self, coordinator):
        data = {
            "battery_soc": 80,
            "pv_power": 5,
            "battery_power": 0,
            "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        # avg consumption < 10 W → sensor unavailable
        assert result["autonomy_hours"] is None

    def test_autonomy_none_when_soc_zero(self, coordinator):
        data = {
            "battery_soc": 0,
            "pv_power": 0,
            "battery_power": -500,
            "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        assert result["autonomy_hours"] == 0.0

    def test_autonomy_uses_rolling_average(self, coordinator):
        # Feed several data points to build the rolling window
        for _ in range(10):
            coordinator._compute_derived({
                "battery_soc": 100,
                "pv_power": 0,
                "battery_power": -1000,
                "grid_power": 0,
            })
        result = coordinator._compute_derived({
            "battery_soc": 50,
            "pv_power": 0,
            "battery_power": -1000,
            "grid_power": 0,
        })
        # 50% of 7 kWh = 3.5 kWh; avg consumption ≈ 1000 W → 3.5 h
        assert result["autonomy_hours"] == pytest.approx(3.5, abs=0.5)


class TestComputedPvSelfConsumption:
    """Tests for the pv_self_consumption_rate derived sensor."""

    def test_full_self_consumption(self, coordinator):
        # All PV consumed locally, importing from grid (no export)
        # grid_power positive = importing, so exported = max(0, -positive) = 0
        data = {
            "battery_soc": 50, "battery_power": -1000,
            "pv_power": 2000, "grid_power": 500,
        }
        result = coordinator._compute_derived(data)
        assert result["pv_self_consumption_rate"] == 100.0

    def test_partial_export(self, coordinator):
        # 1000 W PV, exporting 400 W → 60% self-consumed
        # grid_power negative = exporting to grid
        data = {
            "battery_soc": 50, "battery_power": 0,
            "pv_power": 1000, "grid_power": -400,
        }
        result = coordinator._compute_derived(data)
        assert result["pv_self_consumption_rate"] == pytest.approx(60.0, abs=0.1)

    def test_full_export(self, coordinator):
        # All PV exported to grid (grid_power negative = exporting)
        data = {
            "battery_soc": 50, "battery_power": 0,
            "pv_power": 1000, "grid_power": -1000,
        }
        result = coordinator._compute_derived(data)
        assert result["pv_self_consumption_rate"] == pytest.approx(0.0, abs=0.1)

    def test_none_when_pv_too_low(self, coordinator):
        data = {
            "battery_soc": 50, "battery_power": 0,
            "pv_power": 5, "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        assert result["pv_self_consumption_rate"] is None


class TestComputedBatteryHealthy:
    """Tests for the battery_healthy binary sensor."""

    def test_healthy_normal_operation(self, coordinator):
        data = {
            "battery_soc": 50, "pv_power": 500,
            "battery_power": 0, "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        assert result["battery_healthy"] is True

    def test_unhealthy_soc_zero_with_pv(self, coordinator):
        # SOC stuck at 0 while PV > 100 W → likely a fault
        data = {
            "battery_soc": 0, "pv_power": 500,
            "battery_power": 0, "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        assert result["battery_healthy"] is False

    def test_healthy_soc_zero_no_pv(self, coordinator):
        # SOC at 0 at night → normal (fully discharged)
        data = {
            "battery_soc": 0, "pv_power": 0,
            "battery_power": 0, "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        assert result["battery_healthy"] is True

    def test_healthy_soc_100(self, coordinator):
        data = {
            "battery_soc": 100, "pv_power": 2000,
            "battery_power": 0, "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        assert result["battery_healthy"] is True


class TestComputedNoneValues:
    """Tests that None sensor values don't crash the coordinator."""

    def test_all_none_values(self, coordinator):
        data = {
            "battery_soc": None,
            "pv_power": None,
            "battery_power": None,
            "grid_power": None,
        }
        result = coordinator._compute_derived(data)
        assert result["autonomy_hours"] is None
        assert result["pv_self_consumption_rate"] is None
        assert result["battery_healthy"] is True  # None soc → 0, None pv → 0


class TestControlMethods:
    """Tests that control methods delegate correctly to the Modbus client."""

    @pytest.mark.asyncio
    async def test_set_remote_control_on(self, coordinator):
        await coordinator.async_set_remote_control(True)
        coordinator._modbus.async_set_remote_control.assert_awaited_once_with(True)

    @pytest.mark.asyncio
    async def test_set_remote_control_off(self, coordinator):
        await coordinator.async_set_remote_control(False)
        coordinator._modbus.async_set_remote_control.assert_awaited_once_with(False)

    @pytest.mark.asyncio
    async def test_set_forced_command(self, coordinator):
        await coordinator.async_set_forced_command(2)
        coordinator._modbus.async_set_forced_command.assert_awaited_once_with(2)

    @pytest.mark.asyncio
    async def test_set_forced_target_soc(self, coordinator):
        await coordinator.async_set_forced_target_soc(80)
        coordinator._modbus.async_set_forced_target_soc.assert_awaited_once_with(80)

    @pytest.mark.asyncio
    async def test_set_forced_duration(self, coordinator):
        await coordinator.async_set_forced_duration(120)
        coordinator._modbus.async_set_forced_duration.assert_awaited_once_with(120)

    @pytest.mark.asyncio
    async def test_reset_gateway(self, coordinator):
        await coordinator.async_reset_gateway()
        coordinator._modbus.async_reset_gateway.assert_awaited_once()


class TestCloudConfigResolution:
    """Cloud credentials from the options flow must override the initial setup data."""

    def test_options_override_data(self, mock_hass, mock_config_entry):
        mock_config_entry.data = {
            **mock_config_entry.data,
            "cloud_enabled": False,
            "cloud_app_key": "",
            "cloud_app_secret": "",
        }
        mock_config_entry.options = {
            "cloud_enabled": True,
            "cloud_app_key": "  real-key  ",   # whitespace should be stripped
            "cloud_app_secret": "real-secret",
        }
        coord = AtmoceCoordinator(mock_hass, mock_config_entry)
        assert coord.cloud_enabled is True
        assert coord._cloud_app_key == "real-key"
        assert coord._cloud_app_secret == "real-secret"

    def test_data_used_when_no_options(self, mock_hass, mock_config_entry):
        mock_config_entry.data = {
            **mock_config_entry.data,
            "cloud_enabled": True,
            "cloud_app_key": "data-key",
            "cloud_app_secret": "data-secret",
        }
        mock_config_entry.options = {}
        coord = AtmoceCoordinator(mock_hass, mock_config_entry)
        assert coord._cloud_app_key == "data-key"


class TestCloudFallbackErrorHandling:
    """A failing Cloud fallback must degrade to UpdateFailed, never propagate raw."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc",
        [
            AtmoceCloudError("data fetch failed"),
            AtmoceCloudAuthError("auth failed"),
            aiohttp.ClientError("connection reset"),
            asyncio.TimeoutError(),
            OSError("network down"),
        ],
    )
    async def test_cloud_failure_becomes_update_failed(self, coordinator, exc):
        coordinator._cloud_enabled = True
        coordinator._retry_count = 1
        coordinator._modbus.async_fetch_all = AsyncMock(
            side_effect=ConnectionError("modbus down")
        )
        coordinator._fetch_cloud = AsyncMock(side_effect=exc)

        # Must surface as UpdateFailed, not as the underlying exception type.
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


class TestStagedForcedParams:
    """Parameters wait in Home Assistant until a forced command applies them."""

    def test_staging_does_not_write_to_modbus(self, coordinator):
        coordinator.async_set_updated_data = MagicMock()
        coordinator.stage_forced_param("forced_target_soc", 80)

        assert coordinator.staged_params == {"forced_target_soc": 80}
        coordinator._modbus.async_set_forced_target_soc.assert_not_called()

    def test_staged_value_survives_a_poll(self, coordinator):
        """The register still holds the old value, so a poll would undo it."""
        coordinator.async_set_updated_data = MagicMock()
        coordinator.stage_forced_param("forced_target_soc", 80)

        polled = coordinator._compute_derived({"forced_target_soc": 50})
        polled.update(coordinator.staged_params)

        assert polled["forced_target_soc"] == 80

    @pytest.mark.asyncio
    async def test_applying_writes_each_one_and_clears(self, coordinator):
        coordinator.async_set_updated_data = MagicMock()
        coordinator.async_set_forced_target_soc = AsyncMock()
        coordinator.async_set_forced_duration = AsyncMock()
        coordinator.async_set_forced_power = AsyncMock()

        coordinator.stage_forced_param("forced_target_soc", 80.0)
        coordinator.stage_forced_param("forced_duration", 60.0)
        coordinator.stage_forced_param("forced_power", 3.456)

        await coordinator.async_apply_staged_params()

        # Each register gets the type it expects.
        coordinator.async_set_forced_target_soc.assert_awaited_once_with(80)
        coordinator.async_set_forced_duration.assert_awaited_once_with(60)
        coordinator.async_set_forced_power.assert_awaited_once_with(3.46)
        # Cleared, so the next poll shows what the gateway actually holds.
        assert coordinator.staged_params == {}

    @pytest.mark.asyncio
    async def test_applying_nothing_is_harmless(self, coordinator):
        await coordinator.async_apply_staged_params()
        assert coordinator.staged_params == {}


def _web_enable(coordinator, client):
    """Configure a coordinator with a mocked web client and known station id."""
    coordinator._web_email = "me@example.com"
    coordinator._web_password = "secret"
    coordinator._web_client = client
    coordinator._station_id = 16078


class TestWebSOCLimits:
    """Tests for the battery SOC limit read/write methods (web portal)."""

    @pytest.mark.asyncio
    async def test_set_requires_web_login(self, coordinator):
        # No web credentials in the default fixture.
        assert coordinator.soc_control_available is False
        with pytest.raises(HomeAssistantError, match="login"):
            await coordinator.async_set_web_soc_limit(KEY_END_OF_CHARGE_SOC, 90)

    @pytest.mark.asyncio
    async def test_set_delegates_to_web_client(self, coordinator):
        web = MagicMock()
        web.async_change_model = AsyncMock()
        _web_enable(coordinator, web)

        await coordinator.async_set_web_soc_limit(KEY_END_OF_CHARGE_SOC, 90)

        web.async_change_model.assert_awaited_once_with(
            16078, {"storageChargeCutoffSoc": 90}
        )
        assert coordinator._web_params[KEY_END_OF_CHARGE_SOC] == 90

    @pytest.mark.asyncio
    async def test_set_maps_backup_reserve_field(self, coordinator):
        web = MagicMock()
        web.async_change_model = AsyncMock()
        _web_enable(coordinator, web)

        await coordinator.async_set_web_soc_limit(KEY_BATTERY_RESERVED_SOC, 20)

        web.async_change_model.assert_awaited_once_with(16078, {"backupSoc": 20})

    @pytest.mark.asyncio
    async def test_set_wraps_client_errors(self, coordinator):
        web = MagicMock()
        web.async_change_model = AsyncMock(side_effect=ValueError("denied"))
        _web_enable(coordinator, web)

        with pytest.raises(HomeAssistantError, match="Portal write failed"):
            await coordinator.async_set_web_soc_limit(KEY_END_OF_DISCHARGE_SOC, 10)

    @pytest.mark.asyncio
    async def test_load_populates_cached_limits(self, coordinator):
        web = MagicMock()
        web.async_read_model = AsyncMock(return_value={
            "storageChargeCutoffSoc": "90",
            "storageDischargeCutoffSoc": "10",
            "backupSoc": "20",
        })
        _web_enable(coordinator, web)

        await coordinator.async_load_web_settings()

        assert coordinator._web_params[KEY_END_OF_CHARGE_SOC] == 90
        assert coordinator._web_params[KEY_END_OF_DISCHARGE_SOC] == 10
        assert coordinator._web_params[KEY_BATTERY_RESERVED_SOC] == 20

    @pytest.mark.asyncio
    async def test_load_noop_without_web_login(self, coordinator):
        await coordinator.async_load_web_settings()
        assert coordinator._web_params == {}

    @pytest.mark.asyncio
    async def test_load_tolerates_client_errors(self, coordinator):
        web = MagicMock()
        web.async_read_model = AsyncMock(side_effect=ValueError("boom"))
        _web_enable(coordinator, web)

        # Must not raise — best-effort load.
        await coordinator.async_load_web_settings()
        assert coordinator._web_params == {}


class TestCloudFallbackThrottle:
    """The Open API is a third party's service, and its data is 15 min old."""

    @staticmethod
    def _prepare(coordinator, clock):
        coordinator._cloud_enabled = True
        coordinator._retry_count = 1
        coordinator._modbus.async_fetch_all = AsyncMock(
            side_effect=ConnectionError("modbus down")
        )
        coordinator._fetch_cloud = AsyncMock(return_value={"battery_soc": 55})
        # Already known, so a recovering Modbus poll does not read it again.
        coordinator.firmware_version = "1.2.3"
        coordinator.hass.loop.time = MagicMock(side_effect=clock)

    @pytest.mark.asyncio
    async def test_repeated_polls_ask_the_api_once(self, coordinator):
        # Three polls ten seconds apart, well inside the fetch interval.
        self._prepare(coordinator, [0.0, 10.0, 20.0])

        for _ in range(3):
            data = await coordinator._async_update_data()
            assert data["battery_soc"] == 55
            assert data["active_source"] == SOURCE_CLOUD

        coordinator._fetch_cloud.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_api_is_asked_again_after_the_interval(self, coordinator):
        self._prepare(coordinator, [0.0, float(CLOUD_FETCH_INTERVAL) + 1.0])

        await coordinator._async_update_data()
        await coordinator._async_update_data()

        assert coordinator._fetch_cloud.await_count == 2

    @pytest.mark.asyncio
    async def test_a_failed_call_is_not_retried_inside_the_interval(self, coordinator):
        self._prepare(coordinator, [0.0, 10.0])
        coordinator._fetch_cloud = AsyncMock(side_effect=AtmoceCloudError("boom"))

        for _ in range(2):
            with pytest.raises(UpdateFailed):
                await coordinator._async_update_data()

        coordinator._fetch_cloud.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_modbus_recovers_without_waiting_for_the_interval(self, coordinator):
        """Modbus is still tried on every poll while the cloud is throttled."""
        self._prepare(coordinator, [0.0, 10.0])

        await coordinator._async_update_data()

        coordinator._modbus.async_fetch_all = AsyncMock(return_value={"battery_soc": 61})
        data = await coordinator._async_update_data()

        assert data["battery_soc"] == 61
        assert data["active_source"] == SOURCE_MODBUS
        coordinator._fetch_cloud.assert_awaited_once()
