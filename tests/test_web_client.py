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
    async def test_every_field_read_goes_back(self):
        """A real station carries far more than the SOC limits.

        Fields left out of the save are at the mercy of how the portal treats a
        missing key, so a write must never narrow the object. This model is a
        real diagnostics dump.
        """
        client = AtmoceWebClient("e", "p")
        client._token = "T"

        model = {
            "stationId": 16078,
            "workModel": 1,
            "gridCharge": False,
            "gridChargeMaxPower": 1000.0,
            "storageGridChargeCutoffSoc": 100,
            "storageChargeCutoffSoc": 100,
            "storageDischargeCutoffSoc": 10,
            "touTime": None,
            "thirdApi": False,
            "backupBoxExist": True,
            "stormWatch": False,
            "backupCapacity": 15,
            "backupSoc": 15,
            "peakShavingSoc": None,
            "supportAi": False,
            "workingStrategy": None,
            "powerCap": None,
            "storageSellToGridStatus": False,
            "storageSellToGridMaxPower": 0.0,
            "storageSellToGridUpSOC": 100,
            "energyStoragePhaseControl": None,
            "storageSellToGridMaxPowerLimitUp": 1000000,
            "gridChargeMaxPowerLimitUp": 1000000,
        }
        session = _session([
            _resp({"success": True, "data": model}),
            _resp({"success": True, "data": 16078}),
        ])

        with patch("aiohttp.ClientSession", return_value=session):
            await client.async_change_model(16078, {"backupSoc": 20})

        body = session.post.call_args_list[1].kwargs["json"]

        # Nothing the portal told us about may go missing.
        assert set(body) == set(model)
        # Including the settings the old hardcoded list dropped.
        assert body["gridChargeMaxPower"] == 1000.0
        assert body["storageGridChargeCutoffSoc"] == 100
        assert body["storageSellToGridMaxPower"] == 0.0
        assert body["storageSellToGridUpSOC"] == 100
        assert body["backupCapacity"] == 15
        # The requested change still lands, and workModel is still a string.
        assert body["backupSoc"] == 20
        assert body["workModel"] == "1"

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


class TestDebugLogsAreRedacted:
    """Debug logs get attached to public issues just like diagnostics do."""

    @pytest.mark.asyncio
    async def test_login_does_not_log_the_email(self, caplog):
        client = AtmoceWebClient("me@example.com", "secret12")
        login = _resp({"data": {"token": "TOKEN123", "prefix": "Bearer "}})

        with caplog.at_level("DEBUG", logger="custom_components.atmoce.web_client"):
            with patch("aiohttp.ClientSession", return_value=_session([login])):
                await client._async_login()

        assert "me@example.com" not in caplog.text

    @pytest.mark.asyncio
    async def test_read_model_redacts_the_payload(self, caplog):
        client = AtmoceWebClient("e", "p")
        client._token = "T"
        resp = _resp(
            {
                "success": True,
                "data": {
                    "storageChargeCutoffSoc": 90,
                    "stationName": "Casa de Pablo",
                    "ownerMail": "me@example.com",
                    "latitude": 40.41,
                },
            }
        )

        with caplog.at_level("DEBUG", logger="custom_components.atmoce.web_client"):
            with patch("aiohttp.ClientSession", return_value=_session([resp])):
                model = await client.async_read_model(16078)

        assert "Casa de Pablo" not in caplog.text
        assert "me@example.com" not in caplog.text
        assert "40.41" not in caplog.text
        # The settings themselves still make it to the log, and to the caller.
        assert "storageChargeCutoffSoc" in caplog.text
        assert model["stationName"] == "Casa de Pablo"

    @pytest.mark.asyncio
    async def test_change_model_redacts_both_payloads(self, caplog):
        client = AtmoceWebClient("e", "p")
        client._token = "T"
        model = {"workModel": 1, "ownerMail": "me@example.com"}
        session = _session([
            _resp({"success": True, "data": model}),
            _resp({"success": True, "data": 16078, "userAccount": "pablo"}),
        ])

        with caplog.at_level("DEBUG", logger="custom_components.atmoce.web_client"):
            with patch("aiohttp.ClientSession", return_value=session):
                await client.async_change_model(16078, {"backupSoc": 20})

        assert "me@example.com" not in caplog.text
        assert "pablo" not in caplog.text
        assert "backupSoc" in caplog.text
