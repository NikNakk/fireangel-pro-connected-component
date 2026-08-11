"""Binary sensor entities for FireAngel Pro Connected."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FireAngelConfigEntry
from .bridge import FireAngelBridge
from .const import (
    DEVICE_TYPE_BRIDGE,
    DEVICE_TYPE_CO,
    DEVICE_TYPE_HEAT,
    DEVICE_TYPE_ICONS,
    DOMAIN,
)
from .entity import FireAngelBridgeEntity, FireAngelDetectorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FireAngelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up FireAngel binary sensors."""
    bridge = entry.runtime_data
    _async_remove_bridge_diagnostics(hass, bridge)
    async_add_entities(
        [
            FireAngelBridgeConnectionSensor(entry),
            FireAngelBridgeActivitySensor(entry),
        ]
        + [
            entity
            for device_id in bridge.devices
            for entity in _detector_entities(bridge, device_id)
        ]
    )

    @callback
    def async_add_device(device_id: str) -> None:
        async_add_entities(_detector_entities(bridge, device_id))
        if bridge.devices[device_id].is_bridge_device:
            _async_remove_bridge_diagnostics(hass, bridge)

    entry.async_on_unload(bridge.async_add_new_device_listener(async_add_device))


@callback
def _async_remove_bridge_diagnostics(
    hass: HomeAssistant, bridge: FireAngelBridge
) -> None:
    """Remove battery and base entities once a device is known as the bridge."""
    registry = er.async_get(hass)
    for device_id, detector in bridge.devices.items():
        if not detector.is_bridge_device:
            continue
        for unique_id in (
            f"fireangel_battery_{device_id.lower()}",
            f"fireangel_onbase_{device_id.lower()}",
        ):
            if entity_id := registry.async_get_entity_id(
                "binary_sensor", DOMAIN, unique_id
            ):
                registry.async_remove(entity_id)


def _detector_entities(
    bridge: FireAngelBridge, device_id: str
) -> list[BinarySensorEntity]:
    """Create binary sensors for one detector."""
    entities: list[BinarySensorEntity] = [FireAngelAlarmSensor(bridge, device_id)]
    if not bridge.devices[device_id].is_bridge_device:
        entities.extend(
            [
                FireAngelBatterySensor(bridge, device_id),
                FireAngelBaseSensor(bridge, device_id),
            ]
        )
    return entities


class FireAngelBridgeConnectionSensor(FireAngelBridgeEntity, BinarySensorEntity):
    """Represent the bridge serial connection."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "bridge_connection"

    def __init__(self, entry: FireAngelConfigEntry) -> None:
        """Initialize the connection sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_connection"

    @property
    def is_on(self) -> bool:
        """Return whether serial is connected."""
        return self.bridge.connected

    @property
    def available(self) -> bool:
        """The connection sensor remains available while disconnected."""
        return True


class FireAngelBridgeActivitySensor(FireAngelBridgeEntity, BinarySensorEntity):
    """Represent whether recognized bridge traffic was received recently."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "bridge_activity"

    def __init__(self, entry: FireAngelConfigEntry) -> None:
        """Initialize the activity sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_activity"

    @property
    def is_on(self) -> bool:
        """Return whether recognized traffic was received within the timeout."""
        return self.bridge.activity_available

    @property
    def available(self) -> bool:
        """Keep the diagnostic visible when bridge activity becomes stale."""
        return True


class FireAngelAlarmSensor(FireAngelDetectorEntity, BinarySensorEntity):
    """Represent an active smoke, heat, or CO emergency."""

    _attr_translation_key = "alarm"

    def __init__(self, bridge: FireAngelBridge, device_id: str) -> None:
        """Initialize the alarm sensor."""
        super().__init__(bridge, device_id)
        self._attr_unique_id = f"fireangel_alarm_{device_id.lower()}"

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the best device class supported by the bridge message."""
        if self.detector.resolved_device_type == DEVICE_TYPE_CO:
            return BinarySensorDeviceClass.CO
        if self.detector.resolved_device_type == DEVICE_TYPE_HEAT:
            return BinarySensorDeviceClass.HEAT
        return BinarySensorDeviceClass.SMOKE

    @property
    def icon(self) -> str | None:
        """Use a bridge icon while retaining standard alarm-class icons."""
        if self.detector.resolved_device_type == DEVICE_TYPE_BRIDGE:
            return DEVICE_TYPE_ICONS[DEVICE_TYPE_BRIDGE]
        return None

    @property
    def is_on(self) -> bool | None:
        """Return whether the detector reports an emergency."""
        if self.detector.event is None:
            return None
        return "EMERGENCY" in self.detector.event


class FireAngelBatterySensor(FireAngelDetectorEntity, BinarySensorEntity):
    """Represent a detector low-battery condition."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "battery_low"

    def __init__(self, bridge: FireAngelBridge, device_id: str) -> None:
        """Initialize the battery sensor."""
        super().__init__(bridge, device_id)
        self._attr_unique_id = f"fireangel_battery_{device_id.lower()}"

    @property
    def is_on(self) -> bool | None:
        """Return whether the battery is low or missing."""
        if self.detector.battery is None:
            return None
        return self.detector.battery != "OK"


class FireAngelBaseSensor(FireAngelDetectorEntity, BinarySensorEntity):
    """Represent a detector removed from its base."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "base_problem"

    def __init__(self, bridge: FireAngelBridge, device_id: str) -> None:
        """Initialize the base sensor."""
        super().__init__(bridge, device_id)
        self._attr_unique_id = f"fireangel_onbase_{device_id.lower()}"

    @property
    def is_on(self) -> bool | None:
        """Return whether the detector is off or missing from its base."""
        if self.detector.base is None:
            return None
        return self.detector.base != "ON"
