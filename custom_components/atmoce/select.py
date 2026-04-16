"""Select platform for Atmoce Battery."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .coordinator import AtmoceCoordinator
from .controls import AtmoceForcedCommandSelect, AtmoceForcedModeSelect


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AtmoceCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        AtmoceForcedCommandSelect(coordinator),
        AtmoceForcedModeSelect(coordinator),
    ])
