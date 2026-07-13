"""Tests for AtmoceWebClient (web-portal private API)."""
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.atmoce.web_client import AtmoceWebClient


def _resp(json_data: dict, status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status = status
    r.json = AsyncMock(return_value=json_data)
    return r


def _session(posts) -> MagicMock:
    s = MagicMock()
    s.__aenter__ = AsyncMock(return_value=s)
    s.__aexit__ = AsyncMock(return_value=False)
    s.post = AsyncMock(side_effect=posts)
    return s


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_stores_token_and_base64_password(self):
        client = AtmoceWebClient("me@example.com", "secret12")
        login = _resp({"data": {"token": "TOKEN123", "prefix": "Bearer "}})
        session = _session([login])

        with patch("aiohttp.ClientSession", return_value=session):
            await client._async_login()

        assert client._token == "TOKEN123"
        assert client._prefix == "Bearer "
        body = session.post.call_args.kwargs["json"]
        assert body["username"] == "me@example.com"
        assert body["encrypted"] is True
        assert body["appType"] == "web"
        # password must be base64 of the plaintext
        assert base64.b64decode(body["password"]).decode() == "secret12"

    @pytest.mark.asyncio
    async def test_login_raises_without_token(self):
        client = AtmoceWebClient("me@example.com", "bad")
        fail = _resp({"code": 401, "msg": "wrong password"})
        with patch("aiohttp.ClientSession", return_value=_session([fail])):
            with pytest.raises(PermissionError, match="login failed"):
                await client._async_login()


class TestStationId:
    @pytest.mark.asyncio
    async def test_matches_serial_in_station_name(self):
        client = AtmoceWebClient("e", "p")
        client._token = "T"
        resp = _resp({"success": True, "data": {"data": [
            {"stationId": 111, "stationName": "OTHER", "businessId": "x"},
            {"stationId": 222, "stationName": "26BAT08646 Pablo", "businessId": "y"},
        ]}})
        with patch("aiohttp.ClientSession", return_value=_session([resp])):
            sid = await client.async_get_station_id("26BAT08646")
        assert sid == 222

    @pytest.mark.asyncio
    async def test_falls_back_to_first_station(self):
        client = AtmoceWebClient("e", "p")
        client._token = "T"
        resp = _resp({"success": True, "data": {"data": [
            {"stationId": 111, "stationName": "A", "businessId": "x"},
        ]}})
        with patch("aiohttp.ClientSession", return_value=_session([resp])):
            sid = await client.async_get_station_id("NOMATCH")
        assert sid == 111

    @pytest.mark.asyncio
    async def test_raises_when_no_stations(self):
        client = AtmoceWebClient("e", "p")
        client._token = "T"
        resp = _resp({"success": True, "data": {"data": []}})
        with patch("aiohttp.ClientSession", return_value=_session([resp])):
            with pytest.raises(ValueError, match="No stations"):
                await client.async_get_station_id("x")


class TestChangeModel:
    @pytest.mark.asyncio
    async def test_change_model_read_modify_write(self):
        client = AtmoceWebClient("e", "p")
        client._token = "T"

        current = _resp({"success": True, "code": 200, "data": {
            "stationId": 16078, "workModel": 1, "gridCharge": False,
            "stormWatch": False, "storageSellToGridStatus": False,
            "energyStoragePhaseControl": None, "backupBoxExist": True,
            "storageChargeCutoffSoc": 100, "storageDischargeCutoffSoc": 10,
            "backupSoc": 15,
        }})
        saved = _resp({"success": True, "code": 200, "data": 16078})
        session = _session([current, saved])

        with patch("aiohttp.ClientSession", return_value=session):
            await client.async_change_model(16078, {"backupSoc": 20})

        # Second POST is the changeModel with the merged body
        change_body = session.post.call_args_list[1].kwargs["json"]
        assert change_body["stationId"] == 16078
        assert change_body["backupSoc"] == 20            # our update
        assert change_body["storageChargeCutoffSoc"] == 100  # preserved
        assert change_body["storageDischargeCutoffSoc"] == 10
        assert change_body["workModel"] == "1"           # sent as string

    @pytest.mark.asyncio
    async def test_change_model_raises_on_failure(self):
        client = AtmoceWebClient("e", "p")
        client._token = "T"
        current = _resp({"success": True, "data": {"workModel": 1}})
        failed = _resp({"success": False, "msg": "denied"})
        with patch("aiohttp.ClientSession", return_value=_session([current, failed])):
            with pytest.raises(ValueError, match="changeModel failed"):
                await client.async_change_model(16078, {"backupSoc": 20})


class TestReadModel:
    @pytest.mark.asyncio
    async def test_read_model_returns_data(self):
        client = AtmoceWebClient("e", "p")
        client._token = "T"
        resp = _resp({"success": True, "data": {"storageChargeCutoffSoc": 90}})
        with patch("aiohttp.ClientSession", return_value=_session([resp])):
            model = await client.async_read_model(16078)
        assert model["storageChargeCutoffSoc"] == 90
