"""Tests for AtmoceCloudClient."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.atmoce import cloud_client
from custom_components.atmoce.cloud_client import AtmoceCloudClient


def _session_with(post=None, gets=None) -> MagicMock:
    """Build an async-context-manager session mock with post/get responses."""
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    if post is not None:
        session.post = AsyncMock(return_value=post)
    if gets is not None:
        session.get = AsyncMock(side_effect=gets)
    return session


def _mock_response(json_data: dict, status: int = 200) -> MagicMock:
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data)
    return resp


def _mock_session(responses: list) -> MagicMock:
    """Build a context-manager mock that returns responses in order."""
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.post = AsyncMock(side_effect=responses[:1])
    session.get = AsyncMock(side_effect=responses[1:] if len(responses) > 1 else responses)
    return session


AUTH_OK = {
    "success": True,
    "data": {"access_token": "test-token-abc"},
}

SITE_DATA_OK = {
    "success": True,
    "data": [{
        "gridPower": 500,
        "solarGenerationPower": 2000,
        "dailySolarGeneration": 8.5,
        "lifetimeSolarGeneration": 1200.0,
        "dailyFromGrid": 1.2,
        "lifetimeFromGrid": 300.0,
        "dailyToGrid": 3.1,
        "lifetimeToGrid": 500.0,
        "batterySOC": 75,
        "batteryPower": -800,
        "batteryStatus": 1,
        "dailyBatteryCharging": 4.0,
        "dailyBatteryDischarge": 2.5,
        "lifetimeBatteryCharging": 900.0,
        "lifetimeBatteryDischarge": 850.0,
    }],
}


class TestAuthentication:
    @pytest.mark.asyncio
    async def test_authenticate_sets_token(self):
        client = AtmoceCloudClient("key", "secret")
        auth_resp = _mock_response(AUTH_OK)

        with patch("aiohttp.ClientSession") as mock_cls:
            session = MagicMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=False)
            session.post = AsyncMock(return_value=auth_resp)
            auth_resp.__aenter__ = AsyncMock(return_value=auth_resp)
            auth_resp.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = session

            await client._async_authenticate()

        assert client._access_token == "test-token-abc"

    @pytest.mark.asyncio
    async def test_authenticate_raises_on_failure(self):
        client = AtmoceCloudClient("bad", "creds")
        fail_resp = _mock_response({"success": False, "reason": "invalid credentials"})

        with patch("aiohttp.ClientSession") as mock_cls:
            session = MagicMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=False)
            fail_resp.__aenter__ = AsyncMock(return_value=fail_resp)
            fail_resp.__aexit__ = AsyncMock(return_value=False)
            session.post = AsyncMock(return_value=fail_resp)
            mock_cls.return_value = session

            with pytest.raises(PermissionError, match="Cloud auth failed"):
                await client._async_authenticate()


class TestFetchSiteData:
    @pytest.mark.asyncio
    async def test_fetch_maps_fields_correctly(self):
        client = AtmoceCloudClient("key", "secret")
        client._access_token = "test-token"

        site_resp = _mock_response(SITE_DATA_OK)

        with patch("aiohttp.ClientSession") as mock_cls:
            session = MagicMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=False)
            site_resp.__aenter__ = AsyncMock(return_value=site_resp)
            site_resp.__aexit__ = AsyncMock(return_value=False)
            session.get = AsyncMock(return_value=site_resp)
            mock_cls.return_value = session

            data = await client.async_fetch_site_data("SN123")

        assert data["pv_power"] == 2000
        assert data["battery_soc"] == 75
        assert data["grid_power"] == 500
        assert data["battery_power"] == -800

    @pytest.mark.asyncio
    async def test_fetch_returns_none_for_unavailable_fields(self):
        client = AtmoceCloudClient("key", "secret")
        client._access_token = "test-token"

        site_resp = _mock_response(SITE_DATA_OK)

        with patch("aiohttp.ClientSession") as mock_cls:
            session = MagicMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=False)
            site_resp.__aenter__ = AsyncMock(return_value=site_resp)
            site_resp.__aexit__ = AsyncMock(return_value=False)
            session.get = AsyncMock(return_value=site_resp)
            mock_cls.return_value = session

            data = await client.async_fetch_site_data("SN123")

        # These fields are not available from Cloud API
        assert data["grid_voltage"] is None
        assert data["grid_current"] is None
        assert data["comm_control_mode"] is None
        assert data["forced_cmd"] is None

    @pytest.mark.asyncio
    async def test_fetch_raises_on_api_error(self):
        client = AtmoceCloudClient("key", "secret")
        client._access_token = "test-token"

        fail_resp = _mock_response({"success": False, "reason": "site not found"})

        with patch("aiohttp.ClientSession") as mock_cls:
            session = MagicMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=False)
            fail_resp.__aenter__ = AsyncMock(return_value=fail_resp)
            fail_resp.__aexit__ = AsyncMock(return_value=False)
            session.get = AsyncMock(return_value=fail_resp)
            mock_cls.return_value = session

            with pytest.raises(ValueError, match="Cloud data fetch failed"):
                await client.async_fetch_site_data("SN123")

    @pytest.mark.asyncio
    async def test_fetch_raises_on_empty_data(self):
        client = AtmoceCloudClient("key", "secret")
        client._access_token = "test-token"

        empty_resp = _mock_response({"success": True, "data": []})

        with patch("aiohttp.ClientSession") as mock_cls:
            session = MagicMock()
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=False)
            empty_resp.__aenter__ = AsyncMock(return_value=empty_resp)
            empty_resp.__aexit__ = AsyncMock(return_value=False)
            session.get = AsyncMock(return_value=empty_resp)
            mock_cls.return_value = session

            with pytest.raises(ValueError):
                await client.async_fetch_site_data("SN123")


@pytest.fixture(autouse=True)
def _no_poll_delay():
    """Remove the inter-poll sleeps so control tests run instantly."""
    with patch.object(cloud_client, "_SET_POLL_DELAY", 0), \
         patch.object(cloud_client, "_READ_POLL_DELAY", 0):
        yield


class TestSetParam:
    @pytest.mark.asyncio
    async def test_set_param_success(self):
        client = AtmoceCloudClient("key", "secret")
        client._access_token = "test-token"

        post = _mock_response({
            "success": True,
            "data": {"requestId": "req1", "results": [{"subTaskId": "sub1"}]},
        })
        task = _mock_response({
            "success": True,
            "data": [{"paramResults": [
                {"paramCode": "endOfChargeSOC", "PSitStatus": 1},
            ]}],
        })

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = _session_with(post=post, gets=[task])
            ok = await client.async_set_param("SN123", "endOfChargeSOC", 90)

        assert ok is True

    @pytest.mark.asyncio
    async def test_set_param_sends_value_in_body(self):
        client = AtmoceCloudClient("key", "secret")
        client._access_token = "test-token"

        post = _mock_response({
            "success": True, "data": {"requestId": "req1"},
        })
        task = _mock_response({
            "success": True,
            "data": [{"paramResults": [{"paramCode": "endOfDischargeSOC", "PSitStatus": 1}]}],
        })
        session = _session_with(post=post, gets=[task])

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = session
            await client.async_set_param("SN123", "endOfDischargeSOC", 10)

        body = session.post.call_args.kwargs["json"]
        assert body["SNs"][0]["SN"] == "SN123"
        param = body["SNs"][0]["params"][0]
        assert param["paramCode"] == "endOfDischargeSOC"
        assert param["paramValue"] == "10"

    @pytest.mark.asyncio
    async def test_set_param_raises_when_api_rejects(self):
        client = AtmoceCloudClient("key", "secret")
        client._access_token = "test-token"

        post = _mock_response({"success": False, "reason": "no permission"})

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = _session_with(post=post, gets=[])
            with pytest.raises(ValueError, match="paramSet failed"):
                await client.async_set_param("SN123", "endOfChargeSOC", 90)

    @pytest.mark.asyncio
    async def test_set_param_raises_when_task_fails(self):
        client = AtmoceCloudClient("key", "secret")
        client._access_token = "test-token"

        post = _mock_response({"success": True, "data": {"requestId": "req1"}})
        task = _mock_response({
            "success": True,
            "data": [{"paramResults": [{"paramCode": "endOfChargeSOC", "PSitStatus": 2}]}],
        })

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = _session_with(post=post, gets=[task])
            with pytest.raises(ValueError, match="rejected"):
                await client.async_set_param("SN123", "endOfChargeSOC", 90)


class TestReadParams:
    @pytest.mark.asyncio
    async def test_read_params_returns_values(self):
        client = AtmoceCloudClient("key", "secret")
        client._access_token = "test-token"

        post = _mock_response({"success": True, "data": {"requestId": "req1"}})
        task = _mock_response({
            "success": True,
            "data": [{"paramResults": [
                {"paramCode": "endOfChargeSOC", "PReadStatus": 1, "paramValue": "90"},
                {"paramCode": "endOfDischargeSOC", "PReadStatus": 1, "paramValue": "10"},
                {"paramCode": "batteryReservedSOC", "PReadStatus": 1, "paramValue": "20"},
            ]}],
        })

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = _session_with(post=post, gets=[task])
            values = await client.async_read_params(
                "SN123",
                ["endOfChargeSOC", "endOfDischargeSOC", "batteryReservedSOC"],
            )

        assert values == {
            "endOfChargeSOC": "90",
            "endOfDischargeSOC": "10",
            "batteryReservedSOC": "20",
        }

    @pytest.mark.asyncio
    async def test_read_params_polls_until_ready(self):
        client = AtmoceCloudClient("key", "secret")
        client._access_token = "test-token"

        post = _mock_response({"success": True, "data": {"requestId": "req1"}})
        pending = _mock_response({
            "success": True,
            "data": [{"paramResults": [{"paramCode": "endOfChargeSOC", "PReadStatus": 0}]}],
        })
        ready = _mock_response({
            "success": True,
            "data": [{"paramResults": [
                {"paramCode": "endOfChargeSOC", "PReadStatus": 1, "paramValue": "95"},
            ]}],
        })

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = _session_with(post=post, gets=[pending, ready])
            values = await client.async_read_params("SN123", ["endOfChargeSOC"])

        assert values == {"endOfChargeSOC": "95"}

    @pytest.mark.asyncio
    async def test_read_params_raises_on_api_error(self):
        client = AtmoceCloudClient("key", "secret")
        client._access_token = "test-token"

        post = _mock_response({"success": False, "reason": "bad request"})

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = _session_with(post=post, gets=[])
            with pytest.raises(ValueError, match="paramRead failed"):
                await client.async_read_params("SN123", ["endOfChargeSOC"])
