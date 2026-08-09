"""The FireAngel Pro Connected integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .bridge import FireAngelBridge

PLATFORMS = (Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR)

type FireAngelConfigEntry = ConfigEntry[FireAngelBridge]


async def async_setup_entry(hass: HomeAssistant, entry: FireAngelConfigEntry) -> bool:
    """Set up FireAngel Pro Connected from a config entry."""
    bridge = FireAngelBridge(hass, entry)
    await bridge.async_load_persisted_state()
    await bridge.async_start()
    entry.runtime_data = bridge
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FireAngelConfigEntry) -> bool:
    """Unload a FireAngel Pro Connected config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_stop()
    return True
