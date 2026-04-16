"""Atmoce Cloud API client — read-only monitoring fallback."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import CLOUD_BASE_URL

_LOGGER = logging.getLogger(__name__)

_TOKEN_URL = f"{CLOUD_BASE_URL}/auth/token"
_SITES_URL = f"{CLOUD_BASE_URL}/sites/getSitesLastPower"


class AtmoceCloudClient:
    """Minimal async Cloud client for monitoring fallback."""

    def __init__(self, app_key: str, app_secret: str) -> None:
        self._app_key = app_key
        self._app_secret = app_secret
        self._access_token: str | None = None

    async def _async_authenticate(self) -> None:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                _TOKEN_URL,
                json={
                    "app_key": self._app_key,
                    "app_secret": self._app_secret,
                    "grant_type": "system",
                },
            )
            data = await resp.json()
        if not data.get("success"):
            raise PermissionError(f"Cloud auth failed: {data.get('reason')}")
        self._access_token = data["data"]["access_token"]

    async def async_fetch_site_data(self, serial_number: str) -> dict[str, Any]:
        """Fetch latest site data and map to the same keys as Modbus fetch."""
        if not self._access_token:
            await self._async_authenticate()

        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with aiohttp.ClientSession(headers=headers) as session:
            resp = await session.get(
                _SITES_URL,
                params={"siteIds": serial_number},
            )
            payload = await resp.json()

        if not payload.get("success") or not payload.get("data"):
            raise ValueError(f"Cloud data fetch failed: {payload.get('reason')}")

        site = payload["data"][0]

        # Map Cloud fields → coordinator keys (subset — Cloud has 15-min latency)
        return {
            "grid_power":              site.get("gridPower"),
            "pv_power":                site.get("solarGenerationPower"),
            "pv_energy_daily":         site.get("dailySolarGeneration"),
            "pv_energy_total":         site.get("lifetimeSolarGeneration"),
            "grid_energy_daily":       site.get("dailyFromGrid"),
            "grid_energy_total":       site.get("lifetimeFromGrid"),
            "elec_sales_daily":        site.get("dailyToGrid"),
            "elec_sales_total":        site.get("lifetimeToGrid"),
            "battery_soc":             site.get("batterySOC"),
            "battery_power":           site.get("batteryPower"),
            "battery_status":          site.get("batteryStatus"),
            "battery_charged_daily":   site.get("dailyBatteryCharging"),
            "battery_discharged_daily":site.get("dailyBatteryDischarge"),
            "battery_charged_total":   site.get("lifetimeBatteryCharging"),
            "battery_discharged_total":site.get("lifetimeBatteryDischarge"),
            # Fields not available from Cloud
            "grid_voltage": None,
            "grid_current": None,
            "battery_dispatch_power": None,
            "comm_control_mode": None,
            "forced_cmd": None,
            "forced_mode": None,
            "forced_target_soc": None,
            "forced_duration": None,
            "forced_power": None,
            "station_status": None,
        }
