"""Config flow for Atmoce Battery integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from pymodbus.exceptions import ModbusException

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback

from .const import (
    BATTERY_MODELS,
    CONF_BATTERY_MODEL,
    CONF_CAPACITY_KWH,
    CONF_CHARGE_KW,
    CONF_CLOUD_APP_KEY,
    CONF_CLOUD_APP_SECRET,
    CONF_CLOUD_ENABLED,
    CONF_DISCHARGE_KW,
    CONF_RETRY_COUNT,
    CONF_SLAVE,
    DEFAULT_PORT,
    DEFAULT_SLAVE,
    DOMAIN,
    MODBUS_RETRY_COUNT,
)
from .modbus_client import AtmoceModbusClient

_LOGGER = logging.getLogger(__name__)

# ── Step 1: gateway connection ───────────────────────────────────────────────
def _gateway_schema(
    host: str = "",
    port: int = DEFAULT_PORT,
    slave: int = DEFAULT_SLAVE,
) -> vol.Schema:
    """Build the gateway connection schema."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): vol.All(
                int, vol.Range(min=1, max=65535)
            ),
            vol.Required(CONF_SLAVE, default=slave): vol.All(
                int, vol.Range(min=1, max=247)
            ),
        }
    )

# ── Step 2: battery model ────────────────────────────────────────────────────
STEP_BATTERY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BATTERY_MODEL, default="MS-7K-U"): vol.In(
            {k: v["label"] for k, v in BATTERY_MODELS.items()}
        ),
    }
)

# ── Step 2b: manual battery specs ───────────────────────────────────────────
STEP_MANUAL_BATTERY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CAPACITY_KWH, default=7.0): vol.All(
            float, vol.Range(min=0.5, max=500.0)
        ),
        vol.Required(CONF_CHARGE_KW, default=3.75): vol.All(
            float, vol.Range(min=0.1, max=100.0)
        ),
        vol.Required(CONF_DISCHARGE_KW, default=4.5): vol.All(
            float, vol.Range(min=0.1, max=100.0)
        ),
    }
)

# ── Step 3: cloud (optional) ─────────────────────────────────────────────────
STEP_CLOUD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLOUD_ENABLED, default=False): bool,
        vol.Optional(CONF_CLOUD_APP_KEY, default=""): str,
        vol.Optional(CONF_CLOUD_APP_SECRET, default=""): str,
        vol.Optional(CONF_RETRY_COUNT, default=MODBUS_RETRY_COUNT): vol.All(
            int, vol.Range(min=1, max=20)
        ),
    }
)


class AtmoceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Atmoce config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    # ── Step 1: gateway ──────────────────────────────────────────────────────
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        show_advanced = False

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            slave = user_input.get(CONF_SLAVE, DEFAULT_SLAVE)

            client = AtmoceModbusClient(host, port, slave)
            try:
                await client.async_connect()
                sn = await client.async_read_serial_number()
                await client.async_close()
            except (ConnectionError, ModbusException, OSError):
                errors["base"] = "cannot_connect"
                sn = None

            if not errors:
                await self.async_set_unique_id(sn or f"{host}:{port}")
                self._abort_if_unique_id_configured()
                self._data[CONF_HOST] = host
                self._data[CONF_PORT] = port
                self._data[CONF_SLAVE] = slave
                self._data["serial_number"] = sn
                return await self.async_step_battery()

        return self.async_show_form(
            step_id="user",
            data_schema=_gateway_schema(),
            errors=errors,
        )

    # ── Step 2: battery model ────────────────────────────────────────────────
    async def async_step_battery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data[CONF_BATTERY_MODEL] = user_input[CONF_BATTERY_MODEL]
            if user_input[CONF_BATTERY_MODEL] == "manual":
                return await self.async_step_manual_battery()
            # Pre-fill specs from catalogue
            model = BATTERY_MODELS[user_input[CONF_BATTERY_MODEL]]
            self._data[CONF_CAPACITY_KWH] = model["capacity_kwh"]
            self._data[CONF_CHARGE_KW] = model["charge_kw"]
            self._data[CONF_DISCHARGE_KW] = model["discharge_kw"]
            return await self.async_step_cloud()

        return self.async_show_form(
            step_id="battery",
            data_schema=STEP_BATTERY_SCHEMA,
        )

    # ── Step 2b: manual battery specs ────────────────────────────────────────
    async def async_step_manual_battery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_cloud()

        return self.async_show_form(
            step_id="manual_battery",
            data_schema=STEP_MANUAL_BATTERY_SCHEMA,
        )

    # ── Step 3: cloud (optional) ─────────────────────────────────────────────
    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            cloud_enabled = user_input.get(CONF_CLOUD_ENABLED, False)
            app_key = user_input.get(CONF_CLOUD_APP_KEY, "").strip()
            app_secret = user_input.get(CONF_CLOUD_APP_SECRET, "").strip()

            if cloud_enabled and (not app_key or not app_secret):
                errors["base"] = "cloud_credentials_required"

            if not errors:
                self._data.update(user_input)
                host = self._data[CONF_HOST]
                model = self._data.get(CONF_BATTERY_MODEL, "manual")
                title = f"Atmoce {model} @ {host}"
                return self.async_create_entry(title=title, data=self._data)

        return self.async_show_form(
            step_id="cloud",
            data_schema=STEP_CLOUD_SCHEMA,
            errors=errors,
        )

    # ── Reauth (IP changed) ──────────────────────────────────────────────────
    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)

            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
            slave = entry.data.get(CONF_SLAVE, DEFAULT_SLAVE)

            client = AtmoceModbusClient(host, port, slave)
            try:
                await client.async_connect()
                await client.async_close()
            except (ConnectionError, ModbusException, OSError):
                errors["base"] = "cannot_connect"

            if not errors:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_HOST: host, CONF_PORT: port},
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self.context.get("host", "")): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> AtmoceOptionsFlow:
        return AtmoceOptionsFlow()


class AtmoceOptionsFlow(config_entries.OptionsFlow):
    """Handle options (accessible from the integration card after setup)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            cloud_enabled = user_input.get(CONF_CLOUD_ENABLED, False)
            app_key = user_input.get(CONF_CLOUD_APP_KEY, "").strip()
            app_secret = user_input.get(CONF_CLOUD_APP_SECRET, "").strip()

            if cloud_enabled and (not app_key or not app_secret):
                errors["base"] = "cloud_credentials_required"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options or self.config_entry.data

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_RETRY_COUNT,
                    default=current.get(CONF_RETRY_COUNT, MODBUS_RETRY_COUNT),
                ): vol.All(int, vol.Range(min=1, max=20)),
                vol.Required(
                    CONF_CLOUD_ENABLED,
                    default=current.get(CONF_CLOUD_ENABLED, False),
                ): bool,
                vol.Optional(
                    CONF_CLOUD_APP_KEY,
                    default=current.get(CONF_CLOUD_APP_KEY, ""),
                ): str,
                vol.Optional(
                    CONF_CLOUD_APP_SECRET,
                    default=current.get(CONF_CLOUD_APP_SECRET, ""),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
