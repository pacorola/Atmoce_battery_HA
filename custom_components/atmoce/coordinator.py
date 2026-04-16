"""Data coordinator for Atmoce Battery integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BATTERY_MODEL,
    CONF_CAPACITY_KWH,
    CONF_CHARGE_KW,
    CONF_CLOUD_APP_KEY,
    CONF_CLOUD_APP_SECRET,
    CONF_CLOUD_ENABLED,
    CONF_DISCHARGE_KW,
    CONF_HOST,
    CONF_PORT,
    CONF_RETRY_COUNT,
    CONF_SLAVE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MODBUS_RETRY_COUNT,
    SOURCE_CLOUD,
    SOURCE_MODBUS,
)
from .modbus_client import AtmoceModbusClient

_LOGGER = logging.getLogger(__name__)

# Rolling window for autonomy calculation (last N data points ≈ last 2h at 10s)
_CONSUMPTION_WINDOW = 720


class AtmoceCoordinator(DataUpdateCoordinator):
    """Manages polling, fallback logic, and computed sensors."""

    def __init__(self, hass: HomeAssistant, config_entry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.config_entry = config_entry
        cfg = config_entry.data

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

        # Cloud fallback
        self._cloud_enabled: bool = cfg.get(CONF_CLOUD_ENABLED, False)
        self._cloud_app_key: str = cfg.get(CONF_CLOUD_APP_KEY, "")
        self._cloud_app_secret: str = cfg.get(CONF_CLOUD_APP_SECRET, "")
        self._retry_count: int = cfg.get(CONF_RETRY_COUNT, MODBUS_RETRY_COUNT)

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

    # ── Main update loop ──────────────────────────────────────────────────────
    async def _async_update_data(self) -> dict[str, Any]:
        raw: dict[str, Any] | None = None

        # Always try Modbus first
        try:
            raw = await self._fetch_modbus()
            self._modbus_failures = 0
            self._active_source = SOURCE_MODBUS
        except Exception as exc:  # noqa: BLE001
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
            except Exception as exc:  # noqa: BLE001
                _LOGGER.error("Cloud fallback also failed: %s", exc)

        if raw is None:
            raise UpdateFailed("Both Modbus and Cloud data sources unavailable")

        # Enrich with computed sensors
        raw["active_source"] = self._active_source
        raw["connection_errors"] = self._connection_errors
        raw = self._compute_derived(raw)

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
            except Exception:  # noqa: BLE001
                pass

        return data

    # ── Cloud fetch ───────────────────────────────────────────────────────────
    async def _fetch_cloud(self) -> dict[str, Any]:
        """Fetch data from Atmoce Cloud API (read-only monitoring fallback)."""
        # Lazy import to avoid dependency when Cloud is disabled
        from .cloud_client import AtmoceCloudClient  # noqa: PLC0415

        client = AtmoceCloudClient(self._cloud_app_key, self._cloud_app_secret)
        return await client.async_fetch_site_data(self.serial_number)

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
