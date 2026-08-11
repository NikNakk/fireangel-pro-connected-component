"""Shared entities for FireAngel Pro Connected."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import FireAngelConfigEntry
from .bridge import DetectorState, FireAngelBridge
from .const import DOMAIN, MODEL_NAMES


def bridge_device_info(entry: FireAngelConfigEntry) -> DeviceInfo:
    """Return device registry information for the serial bridge."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="C19HOP",
        model="WiSafe2-to-HomeAssistant Bridge",
        name="FireAngel Pro Connected bridge",
        configuration_url=("https://github.com/C19HOP/WiSafe2-to-HomeAssistant-Bridge"),
    )


class FireAngelBridgeEntity(Entity):
    """Base class for an entity belonging to the serial bridge."""

    _attr_has_entity_name = True

    def __init__(self, entry: FireAngelConfigEntry) -> None:
        """Initialize a bridge entity."""
        self.bridge = entry.runtime_data
        self._entry = entry
        self._attr_device_info = bridge_device_info(entry)

    @property
    def available(self) -> bool:
        """Return whether the serial bridge has recent recognized activity."""
        return self.bridge.activity_available

    async def async_added_to_hass(self) -> None:
        """Subscribe to bridge updates."""
        self.async_on_remove(
            self.bridge.async_add_update_listener(self.async_write_ha_state)
        )


class FireAngelDetectorEntity(Entity):
    """Base class for an entity belonging to a detector."""

    _attr_has_entity_name = True

    def __init__(self, bridge: FireAngelBridge, device_id: str) -> None:
        """Initialize a detector entity."""
        self.bridge = bridge
        self.device_id = device_id

    @property
    def detector(self) -> DetectorState:
        """Return current detector state."""
        return self.bridge.devices[self.device_id]

    @property
    def available(self) -> bool:
        """Return whether the serial bridge has recent recognized activity."""
        return self.bridge.activity_available

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        if self.detector.is_bridge_device:
            return bridge_device_info(self.bridge.entry)
        model_code = self.detector.model
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer="FireAngel",
            model=MODEL_NAMES.get(model_code, model_code),
            name=self.detector.name or f"FireAngel {self.device_id}",
            serial_number=self.device_id,
            via_device=(DOMAIN, self.bridge.entry.entry_id),
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to bridge updates."""
        self.async_on_remove(
            self.bridge.async_add_update_listener(self.async_write_ha_state)
        )
