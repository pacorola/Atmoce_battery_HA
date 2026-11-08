"""Number platform for Atmoce Battery."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controls import (
    AtmoceBatteryReservedSOC,
    AtmoceDispatchPower,
    AtmoceEndOfChargeSOC,
    AtmoceEndOfDischargeSOC,
    AtmoceForcedDuration,
    AtmoceForcedPower,
    AtmoceGridChargeCutoffSOC,
    AtmoceGridChargePower,
    AtmoceSellToGridPower,
    AtmoceSellToGridUpSOC,
    AtmoceTargetSOC,
)
from .coordinator import AtmoceCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AtmoceCoordinator = hass.data[DOMAIN][entry.entry_id]
    # Every control here drives the battery; a gateway without one gets none.
    if not coordinator.has_battery:
        return
    async_add_entities([
        AtmoceTargetSOC(coordinator),
        AtmoceForcedDuration(coordinator),
        AtmoceForcedPower(coordinator),
        AtmoceDispatchPower(coordinator),
        # Web-portal SOC limits (charge / discharge / backup reserve)
        AtmoceEndOfChargeSOC(coordinator),
        AtmoceEndOfDischargeSOC(coordinator),
        AtmoceBatteryReservedSOC(coordinator),
        # Bounds for the two opt-in behaviours, each nested under its switch
        AtmoceGridChargePower(coordinator),
        AtmoceGridChargeCutoffSOC(coordinator),
        AtmoceSellToGridPower(coordinator),
        AtmoceSellToGridUpSOC(coordinator),
    ])
