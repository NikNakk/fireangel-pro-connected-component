"""Button entities for FireAngel Pro Connected bridge commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import State
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FireAngelConfigEntry
from .const import (
    COMMAND_PAIRING,
    COMMAND_PAIRING_STATE,
    COMMAND_SILENCE_CO,
    COMMAND_SILENCE_FIRE,
    COMMAND_SOUND_CO,
    COMMAND_SOUND_COMBINED,
    COMMAND_SOUND_FIRE,
    ProtocolMode,
)
from .entity import FireAngelBridgeEntity


@dataclass(frozen=True, kw_only=True)
class FireAngelButtonDescription(ButtonEntityDescription):
    """Describe a bridge command button."""

    command: str


BUTTONS = (
    FireAngelButtonDescription(
        key="test_co", translation_key="test_co", command=COMMAND_SOUND_CO
    ),
    FireAngelButtonDescription(
        key="test_fire", translation_key="test_fire", command=COMMAND_SOUND_FIRE
    ),
    FireAngelButtonDescription(
        key="test_all", translation_key="test_all", command=COMMAND_SOUND_COMBINED
    ),
    FireAngelButtonDescription(
        key="silence_co", translation_key="silence_co", command=COMMAND_SILENCE_CO
    ),
    FireAngelButtonDescription(
        key="silence_fire",
        translation_key="silence_fire",
        command=COMMAND_SILENCE_FIRE,
    ),
    FireAngelButtonDescription(
        key="get_pairing",
        translation_key="get_pairing",
        command=COMMAND_PAIRING_STATE,
    ),
    FireAngelButtonDescription(
        key="start_pairing",
        translation_key="start_pairing",
        command=COMMAND_PAIRING,
    ),
)


async def async_setup_entry(
    hass: Any,
    entry: FireAngelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up FireAngel command buttons."""
    async_add_entities(
        FireAngelCommandButton(entry, description) for description in BUTTONS
    )


class FireAngelCommandButton(FireAngelBridgeEntity, ButtonEntity):
    """Send a preset command to the Arduino bridge."""

    entity_description: FireAngelButtonDescription

    def __init__(
        self,
        entry: FireAngelConfigEntry,
        description: FireAngelButtonDescription,
    ) -> None:
        """Initialize a command button."""
        super().__init__(entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    async def async_get_last_state(self) -> State | None:
        """Do not restore a historical press as current startup activity."""
        return None

    async def async_press(self) -> None:
        """Send the command."""
        await self.bridge.async_send_command(self.entity_description.command)

    @property
    def available(self) -> bool:
        """Return whether the bridge connection has identified its firmware."""
        return super().available and self.bridge.protocol_mode != ProtocolMode.UNKNOWN
