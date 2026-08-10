"""Sensor entities for FireAngel Pro Connected."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FireAngelConfigEntry
from .bridge import FireAngelBridge
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
        + [
            entity
            for device_id in bridge.devices
            for entity in (
                FireAngelEventSensor(bridge, device_id),
                FireAngelLastTestPassSensor(bridge, device_id),
            )
        ]
    )

    @callback
    def async_add_device(device_id: str) -> None:
        async_add_entities(
            [
                FireAngelEventSensor(bridge, device_id),
                FireAngelLastTestPassSensor(bridge, device_id),
            ]
        )

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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return event metadata."""
        return {
            "result": self.detector.result,
            "model_code": self.detector.model,
            "last_seen": self.detector.last_seen,
        }


class FireAngelLastTestPassSensor(FireAngelDetectorEntity, SensorEntity):
    """Show when a detector last reported a successful test."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "last_successful_test"

    def __init__(self, bridge: FireAngelBridge, device_id: str) -> None:
        """Initialize a last successful test sensor."""
        super().__init__(bridge, device_id)
        self._attr_unique_id = f"fireangel_last_test_pass_{device_id.lower()}"

    @property
    def native_value(self) -> datetime | None:
        """Return the latest successful detector test timestamp."""
        return self.detector.last_test_pass
