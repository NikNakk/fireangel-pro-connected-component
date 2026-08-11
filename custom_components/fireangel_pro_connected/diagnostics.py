"""Diagnostics support for FireAngel Pro Connected."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import FireAngelConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FireAngelConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diagnostics: dict[str, Any] = {
        "entry": {
            "data": entry.data,
            "options": entry.options,
        }
    }
    bridge = getattr(entry, "runtime_data", None)
    if bridge is not None:
        diagnostics["bridge"] = {
            "connected": bridge.connected,
            "protocol_mode": bridge.protocol_mode,
            "protocol_version": bridge.protocol_version,
            "firmware_version": bridge.firmware_version,
            "radio_state": bridge.radio_state,
            "bridge_uptime": bridge.bridge_uptime,
            "last_heartbeat": bridge.last_heartbeat,
            "last_activity": bridge.last_activity,
            "last_message": bridge.last_message,
            "last_error": bridge.last_error,
            "last_command_result": bridge.last_command_result,
            "diagnostic_counters": bridge.diagnostic_counters,
        }
        diagnostics["detectors"] = {
            device_id: {"last_raw_frame": detector.last_raw_frame}
            for device_id, detector in bridge.devices.items()
            if detector.last_raw_frame is not None
        }
    return diagnostics
