"""The FireAngel Pro Connected integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .bridge import FireAngelBridge
from .const import DOMAIN

PLATFORMS = (Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR)

type FireAngelConfigEntry = ConfigEntry[FireAngelBridge]


async def async_setup_entry(hass: HomeAssistant, entry: FireAngelConfigEntry) -> bool:
    """Set up FireAngel Pro Connected from a config entry."""
    bridge = FireAngelBridge(hass, entry)
    await bridge.async_load_persisted_state()
    await bridge.async_start()
    entry.runtime_data = bridge
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_remove_orphaned_bridge_module_device(hass, entry, bridge)
    return True


@callback
def _async_remove_orphaned_bridge_module_device(
    hass: HomeAssistant, entry: FireAngelConfigEntry, bridge: FireAngelBridge
) -> None:
    """Remove the old module device after its entities move to the bridge."""
    device_registry = dr.async_get(hass)
    module_device = device_registry.async_get_device(
        identifiers={(DOMAIN, bridge.bridge_device_id)}
    )
    if module_device is None or er.async_entries_for_device(
        er.async_get(hass), module_device.id, include_disabled_entities=True
    ):
        return

    bridge_device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.entry_id)}
    )
    if bridge_device is None:
        return

    device_registry.async_remove_device(module_device.id)


async def async_unload_entry(hass: HomeAssistant, entry: FireAngelConfigEntry) -> bool:
    """Unload a FireAngel Pro Connected config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_stop()
    return True
