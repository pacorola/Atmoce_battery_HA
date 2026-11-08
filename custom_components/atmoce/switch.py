"""Switch platform for Atmoce Battery."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controls import (
    AtmoceGridChargeSwitch,
    AtmoceRemoteControlSwitch,
    AtmoceSellToGridSwitch,
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
        AtmoceRemoteControlSwitch(coordinator),
        # Portal-backed policy (needs the atmocecloud.com login)
        AtmoceGridChargeSwitch(coordinator),
        AtmoceSellToGridSwitch(coordinator),
    ])
