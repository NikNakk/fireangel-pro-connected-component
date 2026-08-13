"""Firmware update availability for FireAngel Pro Connected."""

from __future__ import annotations

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FireAngelConfigEntry
from .const import ProtocolMode
from .entity import FireAngelBridgeEntity
from .firmware_catalog import FIRMWARE_CATALOG

FIRMWARE_DOCUMENTATION_URL = (
    "https://github.com/NikNakk/fireangel-pro-connected-component/blob/main/"
    "wisafe2_firmware/DOCS.md"
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FireAngelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the advisory bridge firmware update entity."""
    async_add_entities([FireAngelFirmwareUpdateEntity(entry)])


class FireAngelFirmwareUpdateEntity(FireAngelBridgeEntity, UpdateEntity):
    """Advertise the latest firmware bundled with the updater app."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_release_url = FIRMWARE_DOCUMENTATION_URL
    _attr_translation_key = "bridge_firmware"

    def __init__(self, entry: FireAngelConfigEntry) -> None:
        """Initialize the firmware update entity."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_firmware"

    @property
    def available(self) -> bool:
        """Expose availability only when V2 reports an installed version."""
        return (
            super().available
            and self.bridge.protocol_mode is ProtocolMode.V2
            and bool(self.bridge.firmware_version)
        )

    @property
    def installed_version(self) -> str | None:
        """Return the version reported by Protocol V2."""
        if self.bridge.protocol_mode is not ProtocolMode.V2:
            return None
        return self.bridge.firmware_version or None

    @property
    def latest_version(self) -> str:
        """Return the latest firmware shipped by a released updater app."""
        return FIRMWARE_CATALOG["v2"]["version"]
