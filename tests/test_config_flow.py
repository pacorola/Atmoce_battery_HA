"""Tests for Atmoce config flow validation logic."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.atmoce.config_flow import AtmoceConfigFlow
from custom_components.atmoce.const import (
    CONF_BATTERY_COUNT,
    CONF_BATTERY_MODEL,
    CONF_CAPACITY_KWH,
    CONF_CHARGE_KW,
    CONF_CLOUD_APP_KEY,
    CONF_CLOUD_APP_SECRET,
    CONF_CLOUD_ENABLED,
    CONF_CLOUD_WEB_EMAIL,
    CONF_CLOUD_WEB_PASSWORD,
    CONF_DISCHARGE_KW,
    CONF_SLAVE,
)
from homeassistant.const import CONF_HOST, CONF_PORT


GATEWAY_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 502,
    CONF_SLAVE: 1,
}

BATTERY_INPUT = {
    CONF_BATTERY_MODEL: "MS-7K-U",
}

CLOUD_INPUT_DISABLED = {
    CONF_CLOUD_ENABLED: False,
    CONF_CLOUD_APP_KEY: "",
    CONF_CLOUD_APP_SECRET: "",
}

CLOUD_INPUT_ENABLED = {
    CONF_CLOUD_ENABLED: True,
    CONF_CLOUD_APP_KEY: "mykey",
    CONF_CLOUD_APP_SECRET: "mysecret",
}


class TestFallbackStepValidation:
    """Test monitoring-fallback step validation (no network required).

    The Open API keys live in their own step, apart from the atmocecloud.com
    login, so an owner without partner keys never sees these fields.
    """

    def _make_flow(self):
        flow = AtmoceConfigFlow()
        flow._data = {
            CONF_HOST: "192.168.1.100",
            CONF_BATTERY_MODEL: "MS-7K-U",
            CONF_CAPACITY_KWH: 7.0,
            CONF_CHARGE_KW: 3.75,
            CONF_DISCHARGE_KW: 4.5,
        }
        flow.hass = MagicMock()
        flow.context = {}
        # Stub async_set_unique_id and async_create_entry
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        return flow

    @pytest.mark.asyncio
    async def test_cloud_disabled_no_credentials_ok(self):
        flow = self._make_flow()
        result = await flow.async_step_fallback(CLOUD_INPUT_DISABLED)
        flow.async_create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_cloud_enabled_with_credentials_ok(self):
        flow = self._make_flow()
        result = await flow.async_step_fallback(CLOUD_INPUT_ENABLED)
        flow.async_create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_cloud_enabled_missing_key_fails(self):
        flow = self._make_flow()
        result = await flow.async_step_fallback({
            CONF_CLOUD_ENABLED: True,
            CONF_CLOUD_APP_KEY: "",
            CONF_CLOUD_APP_SECRET: "secret",
        })
        # Should show form again with error, not create entry
        flow.async_create_entry.assert_not_called()
        flow.async_show_form.assert_called_once()
        _, kwargs = flow.async_show_form.call_args
        assert kwargs["errors"]["base"] == "cloud_credentials_required"

    @pytest.mark.asyncio
    async def test_cloud_enabled_missing_secret_fails(self):
        flow = self._make_flow()
        result = await flow.async_step_fallback({
            CONF_CLOUD_ENABLED: True,
            CONF_CLOUD_APP_KEY: "mykey",
            CONF_CLOUD_APP_SECRET: "",
        })
        flow.async_create_entry.assert_not_called()
        flow.async_show_form.assert_called_once()

    @pytest.mark.asyncio
    async def test_cloud_enabled_both_missing_fails(self):
        flow = self._make_flow()
        result = await flow.async_step_fallback({
            CONF_CLOUD_ENABLED: True,
            CONF_CLOUD_APP_KEY: "",
            CONF_CLOUD_APP_SECRET: "",
        })
        flow.async_create_entry.assert_not_called()


class TestCloudLoginStep:
    """The atmocecloud.com login step: no partner keys, no validation gate."""

    def _make_flow(self):
        flow = AtmoceConfigFlow()
        flow._data = {CONF_HOST: "192.168.1.100"}
        flow.hass = MagicMock()
        flow.context = {}
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        flow.async_step_fallback = AsyncMock(return_value={"type": "form"})
        return flow

    @pytest.mark.asyncio
    async def test_login_is_stored_and_flow_continues_to_fallback(self):
        flow = self._make_flow()
        await flow.async_step_cloud({
            CONF_CLOUD_WEB_EMAIL: "me@example.com",
            CONF_CLOUD_WEB_PASSWORD: "hunter2",
        })

        assert flow._data[CONF_CLOUD_WEB_EMAIL] == "me@example.com"
        assert flow._data[CONF_CLOUD_WEB_PASSWORD] == "hunter2"
        flow.async_step_fallback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_blank_login_is_allowed(self):
        """Skipping the login must not block setup — it only drops SOC limits."""
        flow = self._make_flow()
        await flow.async_step_cloud({
            CONF_CLOUD_WEB_EMAIL: "",
            CONF_CLOUD_WEB_PASSWORD: "",
        })

        flow.async_step_fallback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_step_offers_no_partner_key_fields(self):
        """The Open API keys belong to the next step, not this one."""
        from custom_components.atmoce.config_flow import STEP_CLOUD_SCHEMA

        fields = {str(k) for k in STEP_CLOUD_SCHEMA.schema}
        assert fields == {CONF_CLOUD_WEB_EMAIL, CONF_CLOUD_WEB_PASSWORD}


class TestBatteryCount:
    """Stacked batteries scale capacity and power."""

    def _make_flow(self):
        flow = AtmoceConfigFlow()
        flow._data = {CONF_HOST: "192.168.1.100"}
        flow.hass = MagicMock()
        flow.context = {}
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        flow.async_step_cloud = AsyncMock(return_value={"type": "form"})
        return flow

    @pytest.mark.asyncio
    async def test_single_battery_matches_the_catalogue(self):
        flow = self._make_flow()
        await flow.async_step_battery({CONF_BATTERY_COUNT: 1})

        assert flow._data[CONF_CAPACITY_KWH] == 7.0
        assert flow._data[CONF_CHARGE_KW] == 3.75
        assert flow._data[CONF_DISCHARGE_KW] == 4.5
        assert flow._data[CONF_BATTERY_MODEL] == "MS-7K-U"

    @pytest.mark.asyncio
    async def test_two_batteries_double_capacity_and_power(self):
        flow = self._make_flow()
        await flow.async_step_battery({CONF_BATTERY_COUNT: 2})

        assert flow._data[CONF_CAPACITY_KWH] == 14.0
        assert flow._data[CONF_CHARGE_KW] == 7.5
        assert flow._data[CONF_DISCHARGE_KW] == 9.0
        assert flow._data[CONF_BATTERY_COUNT] == 2

    @pytest.mark.asyncio
    async def test_count_is_a_typed_box_not_a_slider(self):
        flow = self._make_flow()
        await flow.async_step_battery(None)

        _, kwargs = flow.async_show_form.call_args
        field = next(
            k for k in kwargs["data_schema"].schema
            if str(k) == CONF_BATTERY_COUNT
        )
        validators = kwargs["data_schema"].schema[field].validators
        config = validators[0].config
        assert config["mode"] == "box"
        assert config["max"] == 16

    @pytest.mark.asyncio
    async def test_count_from_the_selector_is_stored_as_an_int(self):
        """NumberSelector returns a float; 2.0 units would be wrong on disk."""
        from custom_components.atmoce.config_flow import STEP_BATTERY_SCHEMA

        validated = STEP_BATTERY_SCHEMA({CONF_BATTERY_COUNT: 2.0})
        assert validated[CONF_BATTERY_COUNT] == 2
        assert isinstance(validated[CONF_BATTERY_COUNT], int)

    @pytest.mark.asyncio
    async def test_no_model_is_asked_for(self):
        """Atmoce ships one unit, so setup asks a count, not a model."""
        flow = self._make_flow()
        await flow.async_step_battery(None)

        _, kwargs = flow.async_show_form.call_args
        fields = {str(k) for k in kwargs["data_schema"].schema}
        assert CONF_BATTERY_MODEL not in fields
        assert CONF_BATTERY_COUNT in fields

    @pytest.mark.asyncio
    async def test_manual_checkbox_routes_to_manual_specs(self):
        flow = self._make_flow()
        flow.async_step_manual_battery = AsyncMock(return_value={"type": "form"})

        await flow.async_step_battery({
            CONF_BATTERY_COUNT: 1,
            "manual_specs": True,
        })

        flow.async_step_manual_battery.assert_awaited_once()
        assert flow._data[CONF_BATTERY_MODEL] == "manual"

    def test_three_batteries_avoid_float_drift(self):
        """3 * 3.75 must not land on 11.249999999999998."""
        from custom_components.atmoce.config_flow import _specs_for

        specs = _specs_for(3)
        assert specs[CONF_CHARGE_KW] == 11.25
        assert specs[CONF_CAPACITY_KWH] == 21.0

    @pytest.mark.asyncio
    async def test_zero_batteries_is_a_gateway_without_storage(self):
        """MC100 with only microinverters: no capacity, named after the gateway."""
        flow = self._make_flow()
        await flow.async_step_battery({CONF_BATTERY_COUNT: 0})

        assert flow._data[CONF_BATTERY_COUNT] == 0
        assert flow._data[CONF_CAPACITY_KWH] == 0.0
        assert flow._data[CONF_CHARGE_KW] == 0.0
        assert flow._data[CONF_BATTERY_MODEL] == "MC100"
        flow.async_step_cloud.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_zero_batteries_ignores_the_manual_checkbox(self):
        flow = self._make_flow()
        flow.async_step_manual_battery = AsyncMock(return_value={"type": "form"})

        await flow.async_step_battery({CONF_BATTERY_COUNT: 0, "manual_specs": True})

        flow.async_step_manual_battery.assert_not_awaited()
        assert flow._data[CONF_BATTERY_COUNT] == 0

    def test_count_accepts_zero(self):
        from custom_components.atmoce.config_flow import STEP_BATTERY_SCHEMA

        assert STEP_BATTERY_SCHEMA({CONF_BATTERY_COUNT: 0.0})[CONF_BATTERY_COUNT] == 0


class TestReconfigure:
    """Adding a battery must not require deleting the integration."""

    def _make_flow(self, entry_data):
        flow = AtmoceConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}
        entry = MagicMock()
        entry.data = entry_data
        flow._get_reconfigure_entry = MagicMock(return_value=entry)
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": "abort"}
        )
        return flow, entry

    @pytest.mark.asyncio
    async def test_submitting_rewrites_the_specs(self):
        flow, entry = self._make_flow({
            CONF_BATTERY_MODEL: "MS-7K-U",
            CONF_BATTERY_COUNT: 1,
            CONF_CAPACITY_KWH: 7.0,
        })

        await flow.async_step_reconfigure({
            CONF_BATTERY_MODEL: "MS-7K-U",
            CONF_BATTERY_COUNT: 2,
        })

        _, kwargs = flow.async_update_reload_and_abort.call_args
        assert kwargs["data_updates"][CONF_CAPACITY_KWH] == 14.0
        assert kwargs["data_updates"][CONF_CHARGE_KW] == 7.5
        assert kwargs["data_updates"][CONF_BATTERY_COUNT] == 2

    @pytest.mark.asyncio
    async def test_form_prefills_the_stored_count(self):
        flow, _ = self._make_flow({
            CONF_BATTERY_MODEL: "MS-7K-U",
            CONF_BATTERY_COUNT: 3,
        })

        await flow.async_step_reconfigure(None)

        _, kwargs = flow.async_show_form.call_args
        defaults = {
            str(k): k.default() for k in kwargs["data_schema"].schema
        }
        assert defaults[CONF_BATTERY_COUNT] == 3

    @pytest.mark.asyncio
    async def test_legacy_14k_entry_counts_as_two_units(self):
        """Entries predating the count key must not read as a single unit."""
        flow, _ = self._make_flow({
            CONF_BATTERY_MODEL: "MS-14K-U",
            CONF_CAPACITY_KWH: 14.0,
        })

        await flow.async_step_reconfigure(None)

        _, kwargs = flow.async_show_form.call_args
        defaults = {
            str(k): k.default() for k in kwargs["data_schema"].schema
        }
        assert defaults[CONF_BATTERY_COUNT] == 2

    @pytest.mark.asyncio
    async def test_unchanged_14k_stack_keeps_its_device_name(self):
        """battery_model is the HA device model — do not rename it silently."""
        flow, _ = self._make_flow({
            CONF_BATTERY_MODEL: "MS-14K-U",
            CONF_CAPACITY_KWH: 14.0,
        })

        await flow.async_step_reconfigure({CONF_BATTERY_COUNT: 2})

        _, kwargs = flow.async_update_reload_and_abort.call_args
        assert kwargs["data_updates"][CONF_BATTERY_MODEL] == "MS-14K-U"
        assert kwargs["data_updates"][CONF_CAPACITY_KWH] == 14.0

    @pytest.mark.asyncio
    async def test_growing_a_14k_stack_switches_to_units(self):
        """Once the numbers outgrow the label, express the stack in units."""
        flow, _ = self._make_flow({
            CONF_BATTERY_MODEL: "MS-14K-U",
            CONF_CAPACITY_KWH: 14.0,
        })

        await flow.async_step_reconfigure({CONF_BATTERY_COUNT: 3})

        _, kwargs = flow.async_update_reload_and_abort.call_args
        assert kwargs["data_updates"][CONF_BATTERY_MODEL] == "MS-7K-U"
        assert kwargs["data_updates"][CONF_CAPACITY_KWH] == 21.0

    @pytest.mark.asyncio
    async def test_manual_entry_does_not_break_the_form(self):
        """A manual entry has no count and no catalogue capacity to derive one."""
        flow, _ = self._make_flow({CONF_BATTERY_MODEL: "manual"})

        await flow.async_step_reconfigure(None)

        _, kwargs = flow.async_show_form.call_args
        defaults = {
            str(k): k.default() for k in kwargs["data_schema"].schema
        }
        assert defaults[CONF_BATTERY_COUNT] == 1


class TestGatewayStepConnectivity:
    """Test gateway step — mocking the Modbus connection."""

    def _make_flow(self):
        flow = AtmoceConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()
        flow.async_show_form = MagicMock(return_value={"type": "form"})
        return flow

    @pytest.mark.asyncio
    async def test_connection_success_proceeds_to_battery(self):
        flow = self._make_flow()
        flow.async_step_battery = AsyncMock(return_value={"type": "form", "step_id": "battery"})

        with patch(
            "custom_components.atmoce.config_flow.AtmoceModbusClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.async_connect = AsyncMock()
            mock_client.async_read_serial_number = AsyncMock(return_value="SN123456")
            mock_client.async_close = AsyncMock()
            mock_client_cls.return_value = mock_client

            result = await flow.async_step_user(GATEWAY_INPUT)

        flow.async_step_battery.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connection_failure_shows_error(self):
        flow = self._make_flow()

        with patch(
            "custom_components.atmoce.config_flow.AtmoceModbusClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.async_connect = AsyncMock(side_effect=ConnectionError("refused"))
            mock_client_cls.return_value = mock_client

            result = await flow.async_step_user(GATEWAY_INPUT)

        flow.async_show_form.assert_called_once()
        _, kwargs = flow.async_show_form.call_args
        assert kwargs["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_empty_form_shows_form(self):
        flow = self._make_flow()
        result = await flow.async_step_user(None)
        flow.async_show_form.assert_called_once()


class TestReconfigureToAndFromZero:
    def test_stored_zero_is_kept(self):
        from custom_components.atmoce.config_flow import _stored_count

        assert _stored_count({CONF_BATTERY_COUNT: 0}) == 0

    def test_adding_a_battery_to_a_gateway_names_it_after_the_unit(self):
        from custom_components.atmoce.config_flow import _specs_for

        specs = _specs_for(1, stored_model="MC100")
        assert specs[CONF_BATTERY_MODEL] == "MS-7K-U"
        assert specs[CONF_CAPACITY_KWH] == 7.0
