"""Diagnostics support for FireAngel Pro Connected."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import FireAngelConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FireAngelConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry": {
            "data": entry.data,
            "options": entry.options,
        }
    }
