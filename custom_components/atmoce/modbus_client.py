"""Modbus TCP client for Atmoce Gateway."""
from __future__ import annotations

import logging
import struct
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import (
    MODBUS_TIMEOUT,
    REG_ACTIVE_POWER_PCT,
    REG_BATTERY_CHARGED_DAILY,
    REG_BATTERY_CHARGED_TOTAL,
    REG_BATTERY_DISCHARGED_DAILY,
    REG_BATTERY_DISCHARGED_TOTAL,
    REG_BATTERY_MAX_CHARGE,
    REG_BATTERY_MAX_DISCHARGE,
    REG_BATTERY_MODE,
    REG_BATTERY_POWER,
    REG_BATTERY_RATED_ENERGY,
    REG_BATTERY_SOC,
    REG_BATTERY_STATUS,
    REG_COMM_CONTROL_MODE,
    REG_DISPATCH_POWER,
    REG_ELECTRICITY_SALES_DAILY,
    REG_ELECTRICITY_SALES_TOTAL,
    REG_FORCED_CMD,
    REG_FORCED_DURATION,
    REG_FORCED_MODE,
    REG_FORCED_POWER,
    REG_FORCED_TARGET_SOC,
    REG_FW_VERSION,
    REG_GRID_CURRENT,
    REG_GRID_ENERGY_DAILY,
    REG_GRID_ENERGY_TOTAL,
    REG_GRID_POWER,
    REG_GRID_VOLTAGE,
    REG_HW_VERSION,
    REG_PV_ENERGY_DAILY,
    REG_PV_ENERGY_TOTAL,
    REG_PV_POWER,
    REG_PV_RATED_POWER,
    REG_RESET,
    REG_SN,
    REG_STATION_STATUS,
)

_LOGGER = logging.getLogger(__name__)


def _regs_to_uint32(regs: list[int]) -> int:
    """Combine two 16-bit Modbus registers into an unsigned 32-bit integer (big-endian)."""
    return (regs[0] << 16) | regs[1]


def _regs_to_int32(regs: list[int]) -> int:
    """Combine two 16-bit Modbus registers into a signed 32-bit integer (big-endian, two's complement)."""
    raw = (regs[0] << 16) | regs[1]
    return struct.unpack(">i", struct.pack(">I", raw))[0]


def _regs_to_uint64(regs: list[int]) -> int:
    """Combine four 16-bit Modbus registers into an unsigned 64-bit integer (big-endian)."""
    return (regs[0] << 48) | (regs[1] << 32) | (regs[2] << 16) | regs[3]


def _regs_to_str(regs: list[int]) -> str:
    """Decode Modbus registers as a packed ASCII string, stripping null bytes and whitespace."""
    raw = b"".join(struct.pack(">H", r) for r in regs)
    return raw.decode("ascii", errors="ignore").strip("\x00").strip()


class AtmoceModbusClient:
    """Async Modbus TCP client for the Atmoce Gateway."""

    def __init__(self, host: str, port: int, slave: int) -> None:
        self._host = host
        self._port = int(port)
        self._slave = int(slave)
        self._client: AsyncModbusTcpClient | None = None

    # ── Connection ────────────────────────────────────────────────────────────
    async def async_connect(self) -> None:
        self._client = AsyncModbusTcpClient(
            self._host,
            port=self._port,
            timeout=MODBUS_TIMEOUT,
        )
        connected = await self._client.connect()
        if not connected:
            raise ConnectionError(f"Cannot connect to Atmoce gateway at {self._host}:{self._port}")

    async def async_close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.connected

    # ── Low-level read helpers ─────────────────────────────────────────────────
    async def _read_holding(self, address: int, count: int) -> list[int]:
        if not self.connected:
            raise ConnectionError("Not connected")
        result = await self._client.read_holding_registers(
            address, count=count, device_id=self._slave
        )
        if result.isError():
            raise ModbusException(f"Error reading register {address}: {result}")
        return result.registers

    async def _read_uint16(self, address: int) -> int:
        regs = await self._read_holding(address, 1)
        return regs[0]

    async def _read_int16(self, address: int) -> int:
        raw = await self._read_uint16(address)
        return struct.unpack(">h", struct.pack(">H", raw))[0]

    async def _read_uint32(self, address: int) -> int:
        regs = await self._read_holding(address, 2)
        return _regs_to_uint32(regs)

    async def _read_int32(self, address: int) -> int:
        regs = await self._read_holding(address, 2)
        return _regs_to_int32(regs)

    async def _read_uint64(self, address: int) -> int:
        regs = await self._read_holding(address, 4)
        return _regs_to_uint64(regs)

    async def _read_str(self, address: int, count: int) -> str:
        regs = await self._read_holding(address, count)
        return _regs_to_str(regs)

    # ── Low-level write helpers ────────────────────────────────────────────────
    async def _write_uint16(self, address: int, value: int) -> None:
        if not self.connected:
            raise ConnectionError("Not connected")
        result = await self._client.write_register(address, value, device_id=self._slave)
        if result.isError():
            raise ModbusException(f"Error writing register {address}: {result}")

    async def _write_uint32(self, address: int, value: int) -> None:
        high = (value >> 16) & 0xFFFF
        low = value & 0xFFFF
        if not self.connected:
            raise ConnectionError("Not connected")
        result = await self._client.write_registers(address, [high, low], device_id=self._slave)
        if result.isError():
            raise ModbusException(f"Error writing registers {address}: {result}")

    async def _write_int32(self, address: int, value: int) -> None:
        packed = struct.pack(">i", value)
        high, low = struct.unpack(">HH", packed)
        if not self.connected:
            raise ConnectionError("Not connected")
        result = await self._client.write_registers(address, [high, low], device_id=self._slave)
        if result.isError():
            raise ModbusException(f"Error writing registers {address}: {result}")

    # ── Device identity ────────────────────────────────────────────────────────
    async def async_read_serial_number(self) -> str:
        return await self._read_str(REG_SN[0], 10)

    async def async_read_firmware_version(self) -> str:
        return await self._read_str(REG_FW_VERSION[0], 15)

    async def async_read_hw_version(self) -> int:
        return await self._read_uint16(REG_HW_VERSION[0])

    # ── Full data poll ─────────────────────────────────────────────────────────
    async def async_fetch_all(self) -> dict[str, Any]:
        """Read all monitored registers and return a flat dict of scaled values."""
        data: dict[str, Any] = {}

        async def safe(key: str, coro):
            try:
                data[key] = await coro
            except (ModbusException, ConnectionError, OSError) as exc:
                _LOGGER.debug("Register read failed for %s: %s", key, exc)
                data[key] = None

        # Grid
        await safe("grid_voltage",      self._read_uint16(REG_GRID_VOLTAGE[0]))
        await safe("grid_current",      self._read_int16(REG_GRID_CURRENT[0]))
        await safe("grid_power",        self._read_int32(REG_GRID_POWER[0]))
        await safe("grid_energy_daily", self._read_uint32(REG_GRID_ENERGY_DAILY[0]))
        await safe("grid_energy_total", self._read_uint64(REG_GRID_ENERGY_TOTAL[0]))
        await safe("elec_sales_daily",  self._read_uint32(REG_ELECTRICITY_SALES_DAILY[0]))
        await safe("elec_sales_total",  self._read_uint64(REG_ELECTRICITY_SALES_TOTAL[0]))

        # PV
        await safe("pv_power",         self._read_uint32(REG_PV_POWER[0]))
        await safe("pv_energy_daily",  self._read_uint32(REG_PV_ENERGY_DAILY[0]))
        await safe("pv_energy_total",  self._read_uint64(REG_PV_ENERGY_TOTAL[0]))
        await safe("pv_rated_power",   self._read_uint32(REG_PV_RATED_POWER[0]))

        # Battery
        await safe("battery_soc",               self._read_uint16(REG_BATTERY_SOC[0]))
        await safe("battery_power",             self._read_int32(REG_BATTERY_POWER[0]))
        await safe("battery_status",            self._read_uint16(REG_BATTERY_STATUS[0]))
        await safe("battery_mode",              self._read_uint16(REG_BATTERY_MODE[0]))
        await safe("battery_dispatch_power",    self._read_int32(REG_DISPATCH_POWER[0]))
        await safe("battery_charged_daily",     self._read_uint32(REG_BATTERY_CHARGED_DAILY[0]))
        await safe("battery_discharged_daily",  self._read_uint32(REG_BATTERY_DISCHARGED_DAILY[0]))
        await safe("battery_charged_total",     self._read_uint64(REG_BATTERY_CHARGED_TOTAL[0]))
        await safe("battery_discharged_total",  self._read_uint64(REG_BATTERY_DISCHARGED_TOTAL[0]))
        await safe("battery_max_charge",        self._read_uint32(REG_BATTERY_MAX_CHARGE[0]))
        await safe("battery_max_discharge",     self._read_uint32(REG_BATTERY_MAX_DISCHARGE[0]))
        await safe("battery_rated_energy",      self._read_uint32(REG_BATTERY_RATED_ENERGY[0]))

        # Control state readback
        await safe("comm_control_mode",  self._read_uint16(REG_COMM_CONTROL_MODE[0]))
        await safe("forced_cmd",         self._read_uint16(REG_FORCED_CMD[0]))
        await safe("forced_mode",        self._read_uint16(REG_FORCED_MODE[0]))
        await safe("forced_target_soc",  self._read_uint16(REG_FORCED_TARGET_SOC[0]))
        await safe("forced_duration",    self._read_uint16(REG_FORCED_DURATION[0]))
        await safe("forced_power",       self._read_uint32(REG_FORCED_POWER[0]))

        # System
        await safe("station_status", self._read_uint16(REG_STATION_STATUS[0]))

        # Apply scales
        def scale(key: str, factor: float) -> None:
            if data.get(key) is not None:
                data[key] = round(data[key] * factor, 3)

        scale("grid_voltage",             0.1)
        scale("grid_current",             0.01)
        scale("grid_energy_daily",        0.01)
        scale("grid_energy_total",        0.01)
        scale("elec_sales_daily",         0.01)
        scale("elec_sales_total",         0.01)
        scale("pv_energy_daily",          0.01)
        scale("pv_energy_total",          0.01)
        scale("pv_rated_power",           0.001)
        scale("battery_charged_daily",    0.01)
        scale("battery_discharged_daily", 0.01)
        scale("battery_charged_total",    0.01)
        scale("battery_discharged_total", 0.01)
        scale("battery_max_charge",       0.01)
        scale("battery_max_discharge",    0.01)
        scale("battery_rated_energy",     0.001)
        scale("forced_power",             0.001)

        return data

    # ── Write commands ─────────────────────────────────────────────────────────
    async def async_set_remote_control(self, enabled: bool) -> None:
        await self._write_uint16(REG_COMM_CONTROL_MODE[0], 1 if enabled else 0)

    async def async_set_forced_command(self, cmd: int) -> None:
        """0=ForceCharge, 1=ForceDischarge, 2=Auto (Administrado por batería)."""
        await self._write_uint16(REG_FORCED_CMD[0], cmd)

    async def async_set_forced_mode(self, mode: int) -> None:
        """0=TargetSOC, 1=Duration, 2=Both."""
        await self._write_uint16(REG_FORCED_MODE[0], mode)

    async def async_set_forced_target_soc(self, soc: int) -> None:
        await self._write_uint16(REG_FORCED_TARGET_SOC[0], int(soc))

    async def async_set_forced_duration(self, minutes: int) -> None:
        await self._write_uint16(REG_FORCED_DURATION[0], int(minutes))

    async def async_set_forced_power(self, power_kw: float) -> None:
        """Write power in kW; register expects W (×1000)."""
        await self._write_uint32(REG_FORCED_POWER[0], int(power_kw * 1000))

    async def async_set_dispatch_power(self, power_w: int) -> None:
        """Signed watts: negative=charge, positive=discharge."""
        await self._write_int32(REG_DISPATCH_POWER[0], int(power_w))

    async def async_set_active_power_pct(self, pct: float) -> None:
        """0–100 %, register scale ×10."""
        await self._write_uint16(REG_COMM_CONTROL_MODE[0], 1)  # ensure remote
        await self._write_uint16(REG_ACTIVE_POWER_PCT[0], int(pct * 10))

    async def async_reset_gateway(self) -> None:
        await self._write_uint16(REG_RESET[0], 0)
