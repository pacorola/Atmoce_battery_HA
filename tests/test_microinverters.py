"""Tests for the undocumented microinverter register blocks."""
import pytest
from pymodbus.exceptions import ModbusException

from custom_components.atmoce.const import MI_BLOCK_SIZE
from custom_components.atmoce.modbus_client import (
    AtmoceModbusClient,
    parse_microinverter,
)


def _ascii(text: str, registers: int) -> list[int]:
    raw = text.encode().ljust(registers * 2, b"\x00")
    return [(raw[i] << 8) | raw[i + 1] for i in range(0, registers * 2, 2)]


# A block read from a real 2-in-1 microinverter (serial number replaced).
_REAL = {11: 1, 28: 1000, 29: 2, 41: 121, 42: 1, 48: 47, 50: 3012, 52: 13,
         54: 1436, 56: 3012, 58: 74, 60: 2121, 62: 14, 64: 1161, 66: 2121,
         71: 5133, 73: 27, 75: 2597, 77: 5133, 78: 372, 79: 137, 80: 2288,
         81: 5001, 82: 292, 83: 65535, 84: 65535, 85: 372, 86: 207,
         87: 65535, 88: 65535, 89: 65535, 90: 65535, 92: 43}


def _block(serial: str = "ES267000001", values: dict[int, int] | None = None) -> list[int]:
    regs = [0] * MI_BLOCK_SIZE
    regs[1:7] = _ascii(serial, 6)
    regs[12:19] = _ascii("01.02.00.00.17", 7)
    for offset, value in (values if values is not None else _REAL).items():
        regs[offset] = value
    return regs


class TestParseMicroinverter:
    def test_real_block(self):
        mi = parse_microinverter(_block())
        assert mi["serial_number"] == "ES267000001"
        assert mi["firmware"] == "01.02.00.00.17"
        assert mi["rated_power"] == 1000
        assert mi["channel_count"] == 2
        assert mi["ac_power"] == 121
        assert mi["energy_total"] == pytest.approx(51.33)
        assert mi["energy_daily"] == pytest.approx(0.27)
        assert mi["ac_voltage"] == pytest.approx(228.8)
        assert mi["ac_frequency"] == pytest.approx(50.01)
        assert mi["temperature"] == pytest.approx(29.2)
        assert len(mi["channels"]) == 2
        one, two = mi["channels"]
        assert (one["power"], two["power"]) == (47, 74)
        assert one["energy_total"] == pytest.approx(30.12)
        assert two["energy_daily"] == pytest.approx(0.14)
        assert one["dc_voltage"] == pytest.approx(37.2)
        assert two["dc_current"] == pytest.approx(2.07)

    def test_channels_add_up(self):
        mi = parse_microinverter(_block())
        one, two = mi["channels"]
        assert one["power"] + two["power"] == mi["ac_power"]
        assert one["energy_total"] + two["energy_total"] == pytest.approx(mi["energy_total"])
        assert one["energy_daily"] + two["energy_daily"] == pytest.approx(mi["energy_daily"])

    def test_empty_slot(self):
        assert parse_microinverter([0] * MI_BLOCK_SIZE) is None

    def test_short_read(self):
        assert parse_microinverter(_block()[:50]) is None

    def test_single_input_has_one_channel(self):
        mi = parse_microinverter(_block(values={**_REAL, 29: 1}))
        assert len(mi["channels"]) == 1

    def test_not_available_reads_as_none(self):
        mi = parse_microinverter(_block(values={**_REAL, 82: 0xFFFF}))
        assert mi["temperature"] is None


class _FakeBlocks:
    def __init__(self, blocks: list[list[int]], fail_at: int | None = None):
        self.blocks = blocks
        self.fail_at = fail_at
        self.reads: list[tuple[int, int]] = []

    async def read_holding(self, address: int, count: int) -> list[int]:
        self.reads.append((address, count))
        index = address // MI_BLOCK_SIZE
        if index == self.fail_at:
            raise ModbusException("timeout")
        return self.blocks[index] if index < len(self.blocks) else [0] * count


def _client(fake: _FakeBlocks) -> AtmoceModbusClient:
    client = AtmoceModbusClient("host", 502, 1)
    client._read_holding = fake.read_holding
    return client


class TestReadMicroinverters:
    @pytest.mark.asyncio
    async def test_stops_at_first_empty_slot(self):
        fake = _FakeBlocks([_block("ES267000001"), _block("ES267000002")])
        mis = await _client(fake).async_read_microinverters()
        assert [m["serial_number"] for m in mis] == ["ES267000001", "ES267000002"]
        assert [m["index"] for m in mis] == [0, 1]
        # two blocks plus the empty third one, never more than 100 registers
        assert fake.reads == [(0, 100), (100, 100), (200, 100)]

    @pytest.mark.asyncio
    async def test_no_microinverter(self):
        assert await _client(_FakeBlocks([])).async_read_microinverters() == []

    @pytest.mark.asyncio
    async def test_read_error_propagates(self):
        fake = _FakeBlocks([_block()], fail_at=0)
        with pytest.raises(ModbusException):
            await _client(fake).async_read_microinverters()


class TestCoordinatorRefresh:
    """The coordinator reads the blocks at most every MI_SCAN_INTERVAL."""

    @pytest.mark.asyncio
    async def test_throttled_and_kept_on_failure(self, coordinator):
        from unittest.mock import AsyncMock

        from custom_components.atmoce.const import MI_SCAN_INTERVAL

        clock = iter([0.0, 10.0, MI_SCAN_INTERVAL + 1, 2 * MI_SCAN_INTERVAL + 2])
        coordinator.hass.loop.time = lambda: next(clock)
        coordinator.firmware_version = "01.02.00.01.17"  # skip identity reads
        coordinator._modbus.async_fetch_all = AsyncMock(return_value={})
        first = [parse_microinverter(_block())]
        coordinator._modbus.async_read_microinverters = AsyncMock(return_value=first)

        data = await coordinator._async_update_data()
        assert data["microinverters"] == first
        await coordinator._async_update_data()          # 10 s later: not re-read
        assert coordinator._modbus.async_read_microinverters.await_count == 1

        coordinator._modbus.async_read_microinverters = AsyncMock(
            side_effect=ModbusException("timeout"))
        data = await coordinator._async_update_data()   # due, but fails
        assert data["microinverters"] == first           # previous values kept
        assert data["active_source"] == "Modbus"         # main poll unaffected
