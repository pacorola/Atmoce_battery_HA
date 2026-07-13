"""Data coordinator for Atmoce Battery integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BATTERY_MODEL,
    CONF_CAPACITY_KWH,
    CONF_CHARGE_KW,
    CONF_CLOUD_APP_KEY,
    CONF_CLOUD_APP_SECRET,
    CONF_CLOUD_ENABLED,
    CONF_CLOUD_WEB_EMAIL,
    CONF_CLOUD_WEB_PASSWORD,
    CONF_DISCHARGE_KW,
    CONF_HOST,
    CONF_PORT,
    CONF_RETRY_COUNT,
    CONF_SLAVE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    KEY_BATTERY_RESERVED_SOC,
    KEY_END_OF_CHARGE_SOC,
    KEY_END_OF_DISCHARGE_SOC,
    MODBUS_RETRY_COUNT,
    SOURCE_CLOUD,
    SOURCE_MODBUS,
    WEB_FIELD_BACKUP_SOC,
    WEB_FIELD_CHARGE_CUTOFF_SOC,
    WEB_FIELD_DISCHARGE_CUTOFF_SOC,
)
from pymodbus.exceptions import ModbusException

from .modbus_client import AtmoceModbusClient

_LOGGER = logging.getLogger(__name__)

# Rolling window for autonomy calculation (last N data points ≈ last 2h at 10s)
_CONSUMPTION_WINDOW = 720

# Battery SOC limits: coordinator data key -> storageModel field on the web API.
# Not available over Modbus, so read/written via the web-portal private API.
_SOC_WEB_FIELDS: dict[str, str] = {
    KEY_END_OF_CHARGE_SOC:    WEB_FIELD_CHARGE_CUTOFF_SOC,
    KEY_END_OF_DISCHARGE_SOC: WEB_FIELD_DISCHARGE_CUTOFF_SOC,
    KEY_BATTERY_RESERVED_SOC: WEB_FIELD_BACKUP_SOC,
}


class AtmoceCoordinator(DataUpdateCoordinator):
    """Manages polling, fallback logic, and computed sensors."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.config_entry = config_entry
        # Options (set via the "Configure" dialog) override the initial setup data,
        # so Cloud credentials/toggles edited after setup take effect.
        cfg = {**config_entry.data, **(config_entry.options or {})}

        # Battery specs (from catalogue or manual)
        self.battery_model: str = cfg.get(CONF_BATTERY_MODEL, "manual")
        self.capacity_kwh: float = cfg.get(CONF_CAPACITY_KWH, 7.0)
        self.max_charge_kw: float = cfg.get(CONF_CHARGE_KW, 3.75)
        self.max_discharge_kw: float = cfg.get(CONF_DISCHARGE_KW, 4.5)

        # Modbus client
        self._modbus = AtmoceModbusClient(
            cfg[CONF_HOST],
            cfg.get(CONF_PORT, 502),
            cfg.get(CONF_SLAVE, 1),
        )

        # Cloud monitoring fallback (partner Open API)
        self._cloud_enabled: bool = cfg.get(CONF_CLOUD_ENABLED, False)
        self._cloud_app_key: str = (cfg.get(CONF_CLOUD_APP_KEY) or "").strip()
        self._cloud_app_secret: str = (cfg.get(CONF_CLOUD_APP_SECRET) or "").strip()
        self._retry_count: int = cfg.get(CONF_RETRY_COUNT, MODBUS_RETRY_COUNT)

        # Web-portal login (email + password) for the battery SOC limits
        self._web_email: str = (cfg.get(CONF_CLOUD_WEB_EMAIL) or "").strip()
        self._web_password: str = cfg.get(CONF_CLOUD_WEB_PASSWORD) or ""

        # Lazily created clients
        self._cloud_client: Any = None   # Open API monitoring fallback
        self._web_client: Any = None     # web-portal private API (SOC limits)
        self._station_id: int | None = None
        # SOC limits, kept across Modbus polls (Modbus can't provide them)
        self._cloud_params: dict[str, Any] = {}

        # State tracking
        self._modbus_failures: int = 0
        self._active_source: str = SOURCE_MODBUS
        self._connection_errors: int = 0

        # Device info (populated on first successful poll)
        self.serial_number: str = cfg.get("serial_number", "unknown")
        self.firmware_version: str = "unknown"
        self.hw_version: int = 0

        # Rolling consumption buffer for autonomy calculation
        self._consumption_history: list[float] = []

    # ── Properties ────────────────────────────────────────────────────────────
    @property
    def active_source(self) -> str:
        return self._active_source

    @property
    def connection_errors(self) -> int:
        return self._connection_errors

    @property
    def cloud_enabled(self) -> bool:
        """Whether the Open API monitoring fallback is configured."""
        return self._cloud_enabled

    @property
    def soc_control_available(self) -> bool:
        """Whether the battery SOC limits can be read/written (web login set)."""
        return bool(self._web_email and self._web_password)

    # ── Main update loop ──────────────────────────────────────────────────────
    async def _async_update_data(self) -> dict[str, Any]:
        raw: dict[str, Any] | None = None

        # Always try Modbus first
        try:
            raw = await self._fetch_modbus()
            self._modbus_failures = 0
            self._active_source = SOURCE_MODBUS
        except (ConnectionError, ModbusException, OSError, asyncio.TimeoutError) as exc:
            self._modbus_failures += 1
            self._connection_errors += 1
            _LOGGER.warning(
                "Modbus poll failed (%d/%d): %s",
                self._modbus_failures,
                self._retry_count,
                exc,
            )

        # Fallback to Cloud after N consecutive Modbus failures
        if raw is None and self._cloud_enabled and self._modbus_failures >= self._retry_count:
            try:
                raw = await self._fetch_cloud()
                self._active_source = SOURCE_CLOUD
                _LOGGER.info("Using Cloud API as data source (Modbus unavailable)")
            except (ConnectionError, OSError, asyncio.TimeoutError) as exc:
                _LOGGER.error("Cloud fallback also failed: %s", exc)

        if raw is None:
            raise UpdateFailed("Both Modbus and Cloud data sources unavailable")

        # Enrich with computed sensors
        raw["active_source"] = self._active_source
        raw["connection_errors"] = self._connection_errors
        raw = self._compute_derived(raw)

        # Re-inject Cloud-only SOC limits (Modbus polls never carry these keys).
        raw.update(self._cloud_params)

        return raw

    # ── Modbus fetch ──────────────────────────────────────────────────────────
    async def _fetch_modbus(self) -> dict[str, Any]:
        if not self._modbus.connected:
            await self._modbus.async_connect()

        data = await self._modbus.async_fetch_all()

        # Read firmware version on first successful poll
        if self.firmware_version == "unknown":
            try:
                self.firmware_version = await self._modbus.async_read_firmware_version()
                self.hw_version = await self._modbus.async_read_hw_version()
            except (ModbusException, ConnectionError, OSError):
                pass

        return data

    # ── Cloud client ──────────────────────────────────────────────────────────
    def _get_cloud_client(self) -> Any:
        """Return a persistent Cloud client, creating it on first use."""
        if self._cloud_client is None:
            # Lazy import to avoid the dependency when Cloud is disabled
            from .cloud_client import AtmoceCloudClient  # noqa: PLC0415

            self._cloud_client = AtmoceCloudClient(
                self._cloud_app_key, self._cloud_app_secret
            )
        return self._cloud_client

    async def _fetch_cloud(self) -> dict[str, Any]:
        """Fetch data from Atmoce Cloud API (read-only monitoring fallback)."""
        return await self._get_cloud_client().async_fetch_site_data(self.serial_number)

    # ── Computed / derived sensors ────────────────────────────────────────────
    def _compute_derived(self, data: dict[str, Any]) -> dict[str, Any]:
        # 1. Autonomy hours — based on rolling average consumption
        grid_power = data.get("grid_power") or 0.0
        pv_power = data.get("pv_power") or 0.0
        battery_power = data.get("battery_power") or 0.0
        # Estimated home consumption (positive = consuming)
        consumption_w = pv_power + max(0, -battery_power) - max(0, grid_power)
        self._consumption_history.append(max(0.0, consumption_w))
        if len(self._consumption_history) > _CONSUMPTION_WINDOW:
            self._consumption_history.pop(0)

        avg_consumption_w = (
            sum(self._consumption_history) / len(self._consumption_history)
            if self._consumption_history
            else 0.0
        )
        soc = data.get("battery_soc") or 0
        if avg_consumption_w > 10:
            available_kwh = (soc / 100.0) * self.capacity_kwh
            data["autonomy_hours"] = round(available_kwh / (avg_consumption_w / 1000.0), 1)
        else:
            data["autonomy_hours"] = None

        # 2. PV self-consumption rate
        if pv_power > 10:
            exported = max(0, -grid_power)
            data["pv_self_consumption_rate"] = round(
                max(0, (pv_power - exported) / pv_power * 100), 1
            )
        else:
            data["pv_self_consumption_rate"] = None

        # 3. Battery healthy binary sensor
        # Returns False if SOC hasn't changed meaningfully in the last 4h of data
        # (simplified: flag if SOC == 0 when pv_power > 100 W)
        data["battery_healthy"] = not (soc == 0 and pv_power > 100)

        return data

    # ── Control proxy methods (delegate to Modbus) ────────────────────────────
    async def async_set_remote_control(self, enabled: bool) -> None:
        await self._ensure_modbus()
        await self._modbus.async_set_remote_control(enabled)

    async def async_set_forced_command(self, cmd: int) -> None:
        await self._ensure_modbus()
        await self._modbus.async_set_forced_command(cmd)

    async def async_set_forced_mode(self, mode: int) -> None:
        await self._ensure_modbus()
        await self._modbus.async_set_forced_mode(mode)

    async def async_set_forced_target_soc(self, soc: int) -> None:
        await self._ensure_modbus()
        await self._modbus.async_set_forced_target_soc(soc)

    async def async_set_forced_duration(self, minutes: int) -> None:
        await self._ensure_modbus()
        await self._modbus.async_set_forced_duration(minutes)

    async def async_set_forced_power(self, power_kw: float) -> None:
        await self._ensure_modbus()
        await self._modbus.async_set_forced_power(power_kw)

    async def async_set_dispatch_power(self, power_w: int) -> None:
        await self._ensure_modbus()
        await self._modbus.async_set_dispatch_power(power_w)

    async def async_reset_gateway(self) -> None:
        await self._ensure_modbus()
        await self._modbus.async_reset_gateway()

    async def _ensure_modbus(self) -> None:
        if not self._modbus.connected:
            await self._modbus.async_connect()

    # ── Battery SOC limits (via web-portal login) ───────────────────────────────
    def _get_web_client(self) -> Any:
        """Return a persistent web-portal client, creating it on first use."""
        if self._web_client is None:
            from .web_client import AtmoceWebClient  # noqa: PLC0415

            self._web_client = AtmoceWebClient(self._web_email, self._web_password)
        return self._web_client

    async def _async_station_id(self) -> int:
        if self._station_id is None:
            self._station_id = await self._get_web_client().async_get_station_id(
                self.serial_number
            )
        return self._station_id

    async def async_load_cloud_soc_limits(self) -> None:
        """Read the battery SOC limits from the web portal and cache them.

        Best-effort: called once at setup (and after a write). Failures are logged
        and leave the values unknown rather than breaking the integration.
        """
        if not self.soc_control_available:
            return
        try:
            station_id = await self._async_station_id()
            model = await self._get_web_client().async_read_model(station_id)
        except Exception as exc:  # noqa: BLE001 — best-effort background load
            _LOGGER.warning("Could not read battery SOC limits: %s", exc, exc_info=True)
            return

        for key, field in _SOC_WEB_FIELDS.items():
            raw = model.get(field)
            if raw is not None and raw != "":
                try:
                    self._cloud_params[key] = int(float(raw))
                except (TypeError, ValueError):
                    self._cloud_params[key] = raw

        _LOGGER.debug("Loaded battery SOC limits: %s", self._cloud_params)

        # Push the cached limits to entities without triggering a Modbus poll.
        if self.data is not None:
            self.async_set_updated_data({**self.data, **self._cloud_params})

    async def async_set_cloud_soc_limit(self, key: str, value: int) -> None:
        """Write a battery SOC limit via the web portal (read-modify-write).

        Requires the web-portal login (email + password). Updates the cached value
        optimistically on success so the entity reflects the change immediately.
        """
        if not self.soc_control_available:
            raise HomeAssistantError(
                "This setting needs your Atmoce Cloud login (email + password) "
                "configured in the integration options (Configure)."
            )
        field = _SOC_WEB_FIELDS[key]
        try:
            station_id = await self._async_station_id()
            await self._get_web_client().async_change_model(station_id, {field: int(value)})
        except Exception as exc:  # noqa: BLE001 — surfaced to the user below
            raise HomeAssistantError(f"Cloud write failed for {key}: {exc}") from exc

        # Optimistic update; the next load reconciles with the portal.
        self._cloud_params[key] = int(value)
        if self.data is not None:
            self.async_set_updated_data({**self.data, **self._cloud_params})
