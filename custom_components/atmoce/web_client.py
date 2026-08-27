"""Atmoce web-portal client — uses the owner's normal login (email + password).

The battery SOC limits (charge / discharge / backup reserve) are not available
over Modbus and are not exposed by the partner Open API without special
credentials. The ATMOZEN app and the web portal edit them through a private API
on www.atmocecloud.com that authenticates with a normal user login. This client
replicates that flow: log in, discover the station, then read/write the
storageModel object.

Note: this is an unofficial/undocumented API and may change without notice.
"""
from __future__ import annotations

import base64
import logging
from typing import Any

import aiohttp

from .const import CLOUD_WEB_BASE_URL
from .redact import redact_model

_LOGGER = logging.getLogger(__name__)

_LOGIN_URL        = f"{CLOUD_WEB_BASE_URL}/permission-auth/api/login"
_STATION_LIST_URL = f"{CLOUD_WEB_BASE_URL}/energy-manage/multipleStation/getDropDownStationList"
_SELECT_MODEL_URL = f"{CLOUD_WEB_BASE_URL}/energy-manage/web/storageModel/selectModel"
_CHANGE_MODEL_URL = f"{CLOUD_WEB_BASE_URL}/energy-manage/web/storageModel/changeModel"

# changeModel is a read-modify-write of the whole storageModel object, so every
# field read has to go back. An earlier hardcoded list of nine covered barely
# half of a real station: a diagnostics dump showed 23 fields, with the grid
# charge power and cutoff, the sell-to-grid power and SOC, and touTime among the
# ones being left out of every save. Echoing whatever the portal returned is
# correct whichever way its backend treats a missing key, and if it ever objects
# to a field the write fails loudly instead of quietly dropping a setting.
#
# stationId is set by the caller and workModel is submitted as a string, so both
# are handled separately.
_MODEL_ID_FIELD = "stationId"


class AtmoceWebClient:
    """Minimal async client for the Atmoce web-portal private API."""

    def __init__(self, email: str, password: str) -> None:
        self._email = email
        self._password = password
        self._token: str | None = None
        self._prefix: str = "Bearer "

    async def _async_login(self) -> None:
        """Authenticate and cache the session token.

        The portal sends the password base64-encoded with ``encrypted: true``
        (this is encoding, not real encryption).
        """
        body = {
            "username": self._email,
            "encrypted": True,
            "password": base64.b64encode(self._password.encode("utf-8")).decode("ascii"),
            "appType": "web",
        }
        async with aiohttp.ClientSession() as session:
            resp = await session.post(_LOGIN_URL, json=body)
            payload = await resp.json()

        data = payload.get("data") or {}
        token = data.get("token")
        if not token:
            raise PermissionError(
                f"Atmoce web login failed: {payload.get('msg') or payload.get('code')}"
            )
        self._token = token
        self._prefix = data.get("prefix") or "Bearer "
        # No email here: debug logs get attached to public issues too, and the
        # portal login is the same credential diagnostics redacts.
        _LOGGER.debug("Atmoce web login OK")

    async def _async_post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST with the session token, re-logging in once on a 401."""
        payload: dict[str, Any] = {}
        for attempt in range(2):
            if not self._token:
                await self._async_login()
            headers = {"Authorization": f"{self._prefix}{self._token}"}
            async with aiohttp.ClientSession(headers=headers) as session:
                resp = await session.post(url, json=body)
                status = resp.status
                payload = await resp.json()
            if (status == 401 or payload.get("code") == 401) and attempt == 0:
                self._token = None  # expired → refresh and retry once
                continue
            break
        return payload

    async def async_get_station_id(self, serial_number: str | None = None) -> int:
        """Return the station id, matching the serial number when possible."""
        payload = await self._async_post(
            _STATION_LIST_URL, {"pageIndex": 1, "pageSize": 20}
        )
        if not payload.get("success"):
            raise ValueError(f"Station list failed: {payload.get('msg')}")
        stations = ((payload.get("data") or {}).get("data")) or []
        if not stations:
            raise ValueError("No stations found for this Atmoce account")
        if serial_number:
            for st in stations:
                if serial_number in (st.get("stationName") or "") or serial_number == str(
                    st.get("businessId")
                ):
                    return st["stationId"]
        return stations[0]["stationId"]

    async def async_read_model(self, station_id: int) -> dict[str, Any]:
        """Read the current storageModel for a station."""
        payload = await self._async_post(_SELECT_MODEL_URL, {"stationId": station_id})
        _LOGGER.debug("selectModel response: %s", redact_model(payload))
        if not payload.get("success"):
            raise ValueError(f"selectModel failed: {payload.get('msg')}")
        return payload.get("data") or {}

    async def async_change_model(
        self, station_id: int, updates: dict[str, Any]
    ) -> None:
        """Apply updates to the storageModel (read-modify-write of the object)."""
        model = await self.async_read_model(station_id)
        body: dict[str, Any] = dict(model)
        body[_MODEL_ID_FIELD] = station_id
        # The portal submits workModel as a string.
        if body.get("workModel") is not None:
            body["workModel"] = str(body["workModel"])
        body.update(updates)

        payload = await self._async_post(_CHANGE_MODEL_URL, body)
        _LOGGER.debug(
            "changeModel %s response: %s",
            redact_model(updates),
            redact_model(payload),
        )
        if not payload.get("success"):
            raise ValueError(f"changeModel failed: {payload.get('msg')}")
