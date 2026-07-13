"""Atmoce Cloud API client — monitoring fallback and battery parameter control."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import CLOUD_BASE_URL

_LOGGER = logging.getLogger(__name__)

_TOKEN_URL = f"{CLOUD_BASE_URL}/auth/token"
_SITES_URL = f"{CLOUD_BASE_URL}/sites/getSitesLastPower"

# Control APIs (Cloud API Ref. §6) — task-based, asynchronous
_PARAM_SET_URL       = f"{CLOUD_BASE_URL}/device/paramSet"
_PARAM_SET_TASK_URL  = f"{CLOUD_BASE_URL}/device/getParamSettingTask"
_PARAM_READ_URL      = f"{CLOUD_BASE_URL}/device/paramRead"
_PARAM_READ_TASK_URL = f"{CLOUD_BASE_URL}/device/getParamReadingTask"

# Task polling — control tasks are executed asynchronously by the gateway, so we
# submit a task and then poll for its result. Kept small to respect QPS limits
# (10,000 calls/month, 5 concurrent).
_TASK_POLL_ATTEMPTS = 6
_TASK_POLL_DELAY = 1.5  # seconds between polls


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

    # ── Control APIs (battery parameter set / read) ─────────────────────────────
    async def _auth_headers(self) -> dict[str, str]:
        """Return authorization headers, authenticating first if needed."""
        if not self._access_token:
            await self._async_authenticate()
        return {"Authorization": f"Bearer {self._access_token}"}

    async def async_set_param(
        self, serial_number: str, param_code: str, value: Any
    ) -> bool:
        """Set a single battery control parameter via the Cloud paramSet task API.

        Returns True if the task executed successfully, False if it is still
        pending after polling. Raises on request/API errors.
        """
        headers = await self._auth_headers()
        # paramValue is echoed back as a string by the API (§6.2.5); send it as one.
        body = {
            "SNs": [
                {
                    "SN": serial_number,
                    "params": [{"paramCode": param_code, "paramValue": str(value)}],
                }
            ]
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            resp = await session.post(_PARAM_SET_URL, json=body)
            payload = await resp.json()
            if not payload.get("success"):
                raise ValueError(f"Cloud paramSet failed: {payload.get('reason')}")

            data = payload.get("data") or {}
            request_id = data.get("requestId")
            _LOGGER.debug(
                "paramSet %s=%s submitted (requestId=%s)", param_code, value, request_id
            )
            if not request_id:
                return False

            # Poll the task result to confirm the gateway applied the value.
            for _ in range(_TASK_POLL_ATTEMPTS):
                await asyncio.sleep(_TASK_POLL_DELAY)
                task = await session.get(
                    _PARAM_SET_TASK_URL, params={"requestId": request_id}
                )
                task_payload = await task.json()
                status = _first_param_status(task_payload, "PSitStatus")
                if status == 1:
                    return True
                if status == 2:
                    raise ValueError(
                        f"Cloud paramSet rejected for {param_code} "
                        f"(requestId={request_id})"
                    )
            _LOGGER.warning(
                "paramSet %s=%s still pending after polling (requestId=%s)",
                param_code, value, request_id,
            )
            return False

    async def async_read_params(
        self, serial_number: str, param_codes: list[str]
    ) -> dict[str, str]:
        """Read battery control parameters via the Cloud paramRead task API.

        Returns a dict mapping paramCode -> value (string) for the parameters
        that resolved successfully. Raises on request/API errors.
        """
        headers = await self._auth_headers()
        body = {
            "SNs": [
                {
                    "SN": serial_number,
                    "params": [{"paramCode": code} for code in param_codes],
                }
            ]
        }
        values: dict[str, str] = {}
        async with aiohttp.ClientSession(headers=headers) as session:
            resp = await session.post(_PARAM_READ_URL, json=body)
            payload = await resp.json()
            if not payload.get("success"):
                raise ValueError(f"Cloud paramRead failed: {payload.get('reason')}")

            data = payload.get("data") or {}
            request_id = data.get("requestId")
            if not request_id:
                return values

            for _ in range(_TASK_POLL_ATTEMPTS):
                await asyncio.sleep(_TASK_POLL_DELAY)
                task = await session.get(
                    _PARAM_READ_TASK_URL, params={"requestId": request_id}
                )
                task_payload = await task.json()
                pending = False
                for entry in task_payload.get("data") or []:
                    for pr in entry.get("paramResults") or []:
                        code = pr.get("paramCode")
                        status = pr.get("PReadStatus")
                        if status == 1 and code:
                            values[code] = pr.get("paramValue")
                        elif status == 0:
                            pending = True
                if values and not pending:
                    break
        return values


def _first_param_status(task_payload: dict[str, Any], status_key: str) -> int | None:
    """Extract the first parameter execution status from a task-result payload."""
    for entry in task_payload.get("data") or []:
        for pr in entry.get("paramResults") or []:
            if status_key in pr:
                return pr.get(status_key)
    return None
