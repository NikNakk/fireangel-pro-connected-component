"""The FireAngel Pro Connected integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .bridge import FireAngelBridge
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    CONF_PORT,
    DOMAIN,
    SERVICE_MAINTENANCE_STATUS,
    SERVICE_RESUME_AFTER_MAINTENANCE,
    SERVICE_SUSPEND_FOR_MAINTENANCE,
)

PLATFORMS = (Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR)

type FireAngelConfigEntry = ConfigEntry[FireAngelBridge]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register authenticated maintenance services for loaded bridges."""

    async def async_handle_maintenance(call: ServiceCall) -> dict:
        entries = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if getattr(entry, "runtime_data", None) is not None
        ]
        requested_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
        if requested_id is not None:
            entries = [entry for entry in entries if entry.entry_id == requested_id]
            if not entries:
                raise HomeAssistantError(
                    f"No loaded FireAngel config entry matches {requested_id}"
                )
        elif len(entries) != 1:
            raise HomeAssistantError(
                "Specify config_entry_id when zero or multiple FireAngel entries "
                "are loaded"
            )

        entry = entries[0]
        bridge = entry.runtime_data
        if call.service == SERVICE_SUSPEND_FOR_MAINTENANCE:
            await bridge.async_suspend_for_maintenance()
        elif call.service == SERVICE_RESUME_AFTER_MAINTENANCE:
            await bridge.async_resume_from_maintenance()
        return {
            "config_entry_id": entry.entry_id,
            "title": entry.title,
            "serial_device": entry.data[CONF_PORT],
            "connected": bridge.connected,
            "maintenance_suspended": bridge.maintenance_suspended,
        }

    for service in (
        SERVICE_MAINTENANCE_STATUS,
        SERVICE_SUSPEND_FOR_MAINTENANCE,
        SERVICE_RESUME_AFTER_MAINTENANCE,
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            async_handle_maintenance,
            supports_response=SupportsResponse.ONLY,
        )
    return True


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
