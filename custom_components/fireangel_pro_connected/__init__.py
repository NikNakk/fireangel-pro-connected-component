"""The FireAngel Pro Connected integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

type FireAngelConfigEntry = ConfigEntry[None]


async def async_setup_entry(
    hass: HomeAssistant, entry: FireAngelConfigEntry
) -> bool:
    """Set up FireAngel Pro Connected from a config entry."""
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: FireAngelConfigEntry
) -> bool:
    """Unload a FireAngel Pro Connected config entry."""
    return True

