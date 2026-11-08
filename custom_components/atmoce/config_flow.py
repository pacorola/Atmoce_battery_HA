"""Config flow for Atmoce Battery integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector
from pymodbus.exceptions import ModbusException

from .const import (
    BATTERY_MODELS,
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
    CONF_MANUAL_SPECS,
    CONF_RETRY_COUNT,
    CONF_SLAVE,
    CREDENTIAL_KEYS,
    DEFAULT_BATTERY_COUNT,
    DEFAULT_PORT,
    DEFAULT_SLAVE,
    DOMAIN,
    MAX_BATTERY_COUNT,
    MODBUS_RETRY_COUNT,
    NO_BATTERY_MODEL,
    UNIT_BATTERY_MODEL,
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
            vol.Required(CONF_SLAVE, default=slave): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=247,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )

# ── Step 2: how many batteries ───────────────────────────────────────────────
# A plain int with a Range renders as a slider, which is a poor fit for "how
# many batteries do you own" — a typed box is. NumberSelector hands back a
# float, so coerce it: the count is stored in the config entry and read back as
# a unit multiplier.
_COUNT_SELECTOR = vol.All(
    selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=MAX_BATTERY_COUNT,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
        )
    ),
    vol.Coerce(int),
)

STEP_BATTERY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BATTERY_COUNT, default=DEFAULT_BATTERY_COUNT): _COUNT_SELECTOR,
        vol.Optional(CONF_MANUAL_SPECS, default=False): bool,
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
_PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)

# The owner's own atmocecloud.com login — all that the battery SOC limits need.
STEP_CLOUD_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CLOUD_WEB_EMAIL, default=""): str,
        vol.Optional(CONF_CLOUD_WEB_PASSWORD, default=""): _PASSWORD_SELECTOR,
    }
)

# ── Step 4: monitoring fallback (rarely needed) ──────────────────────────────
# Kept apart from the login above because it is a different feature backed by a
# different API: the partner Open API, whose app_key/app_secret are issued by
# Atmoce support to installers and do not ship with the hardware. Owners who
# only want the battery limits should never have to look at these fields.
STEP_FALLBACK_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLOUD_ENABLED, default=False): bool,
        vol.Optional(CONF_CLOUD_APP_KEY, default=""): str,
        vol.Optional(CONF_CLOUD_APP_SECRET, default=""): _PASSWORD_SELECTOR,
        vol.Optional(CONF_RETRY_COUNT, default=MODBUS_RETRY_COUNT): vol.All(
            int, vol.Range(min=1, max=20)
        ),
    }
)


def _specs_for(count: int, stored_model: str | None = None) -> dict[str, Any]:
    """Return the config keys for `count` stacked MS-7K-U units.

    Capacity and power scale with the number of units. Rounded because floats
    like 3.75 * 3 land on values such as 11.249999999999998.

    `stored_model` keeps an existing entry's label when it still describes the
    same stack — an MS-14K-U left at two units stays an MS-14K-U, so the device
    is not renamed in Home Assistant behind the owner's back. Once the numbers
    no longer match the label, the stack is expressed in units instead.
    """
    if count == 0:
        return {
            CONF_BATTERY_MODEL: NO_BATTERY_MODEL,
            CONF_BATTERY_COUNT: 0,
            CONF_CAPACITY_KWH: 0.0,
            CONF_CHARGE_KW: 0.0,
            CONF_DISCHARGE_KW: 0.0,
        }

    unit = BATTERY_MODELS[UNIT_BATTERY_MODEL]
    capacity = round(unit["capacity_kwh"] * count, 2)

    legacy = BATTERY_MODELS.get(stored_model or "", {})
    keeps_label = legacy.get("capacity_kwh") == capacity

    return {
        CONF_BATTERY_MODEL: stored_model if keeps_label else UNIT_BATTERY_MODEL,
        CONF_BATTERY_COUNT: count,
        CONF_CAPACITY_KWH: capacity,
        CONF_CHARGE_KW: round(unit["charge_kw"] * count, 2),
        CONF_DISCHARGE_KW: round(unit["discharge_kw"] * count, 2),
    }


def _stored_count(entry_data: dict[str, Any]) -> int:
    """Best guess at how many units an existing entry represents.

    Entries created before the count existed have no such key, so derive it
    from the stored capacity: an MS-14K-U comes out as the two units it is.
    """
    if (count := entry_data.get(CONF_BATTERY_COUNT)) is not None:
        return max(0, min(MAX_BATTERY_COUNT, int(count)))

    capacity = entry_data.get(CONF_CAPACITY_KWH)
    unit_capacity = BATTERY_MODELS[UNIT_BATTERY_MODEL]["capacity_kwh"]
    if capacity:
        return max(1, min(MAX_BATTERY_COUNT, round(capacity / unit_capacity)))

    return DEFAULT_BATTERY_COUNT


class AtmoceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Atmoce config flow."""

    VERSION = 2

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    # ── Step 1: gateway ──────────────────────────────────────────────────────
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

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

    # ── Step 2: how many batteries ───────────────────────────────────────────
    async def async_step_battery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            count = user_input.get(CONF_BATTERY_COUNT, DEFAULT_BATTERY_COUNT)
            if count and user_input.get(CONF_MANUAL_SPECS):
                self._data[CONF_BATTERY_MODEL] = "manual"
                return await self.async_step_manual_battery()
            self._data.update(_specs_for(count))
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

    # ── Step 3: atmocecloud.com login (optional) ─────────────────────────────
    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_fallback()

        return self.async_show_form(
            step_id="cloud",
            data_schema=STEP_CLOUD_SCHEMA,
        )

    # ── Step 4: monitoring fallback (optional) ───────────────────────────────
    async def async_step_fallback(
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
            step_id="fallback",
            data_schema=STEP_FALLBACK_SCHEMA,
            errors=errors,
        )

    # ── Reconfigure (batteries added or removed) ─────────────────────────────
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-state the battery stack without deleting the integration.

        Capacity and power limits are fixed at setup and feed the autonomy
        sensor and the forced-power sliders, so adding a second battery used to
        mean removing and re-adding the entry.
        """
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data_updates=_specs_for(
                    user_input[CONF_BATTERY_COUNT],
                    stored_model=entry.data.get(CONF_BATTERY_MODEL),
                ),
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BATTERY_COUNT,
                    default=_stored_count(entry.data),
                ): _COUNT_SELECTOR,
            }
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema)

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
                # Credentials belong in entry.data. Update them in place rather
                # than storing a second copy in entry.options, so the password
                # only ever exists once on disk.
                tunables = {k: v for k, v in user_input.items() if k not in CREDENTIAL_KEYS}
                credentials = {
                    k: user_input[k] for k in CREDENTIAL_KEYS if k in user_input
                }
                if credentials:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data={**self.config_entry.data, **credentials},
                    )
                return self.async_create_entry(title="", data=tunables)

        # entry.data holds the credentials, entry.options the tunables — the form
        # needs both to pre-fill correctly.
        current = {**self.config_entry.data, **self.config_entry.options}

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
                ): _PASSWORD_SELECTOR,
                vol.Optional(
                    CONF_CLOUD_WEB_EMAIL,
                    default=current.get(CONF_CLOUD_WEB_EMAIL, ""),
                ): str,
                vol.Optional(
                    CONF_CLOUD_WEB_PASSWORD,
                    default=current.get(CONF_CLOUD_WEB_PASSWORD, ""),
                ): _PASSWORD_SELECTOR,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
