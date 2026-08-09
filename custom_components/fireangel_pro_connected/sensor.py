"""Sensor entities for FireAngel Pro Connected."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FireAngelConfigEntry
from .bridge import FireAngelBridge
from .const import DEVICE_TYPE_ICONS
from .entity import FireAngelBridgeEntity, FireAngelDetectorEntity


async def async_setup_entry(
    hass: Any,
    entry: FireAngelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up FireAngel sensors."""
    bridge = entry.runtime_data
    async_add_entities(
        [FireAngelBridgeMessageSensor(entry)]
        + [FireAngelEventSensor(bridge, device_id) for device_id in bridge.devices]
    )

    @callback
    def async_add_device(device_id: str) -> None:
        async_add_entities([FireAngelEventSensor(bridge, device_id)])

    entry.async_on_unload(bridge.async_add_new_device_listener(async_add_device))


class FireAngelBridgeMessageSensor(FireAngelBridgeEntity, SensorEntity):
    """Show the last line received from the bridge."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "bridge_message"

    def __init__(self, entry: FireAngelConfigEntry) -> None:
        """Initialize the bridge message sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_message"

    @property
    def native_value(self) -> str | None:
        """Return the last bridge line."""
        return self.bridge.last_message


class FireAngelEventSensor(FireAngelDetectorEntity, SensorEntity):
    """Show the latest event reported by a detector."""

    _attr_translation_key = "last_event"

    def __init__(self, bridge: FireAngelBridge, device_id: str) -> None:
        """Initialize an event sensor."""
        super().__init__(bridge, device_id)
        self._attr_unique_id = f"fireangel_event_{device_id.lower()}"

    @property
    def native_value(self) -> str | None:
        """Return the latest detector event."""
        return self.detector.event

    @property
    def icon(self) -> str:
        """Return an icon matching the detector or bridge-interface type."""
        return DEVICE_TYPE_ICONS[self.detector.resolved_device_type]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return event metadata."""
        return {
            "result": self.detector.result,
            "model_code": self.detector.model,
            "last_seen": self.detector.last_seen,
        }
