"""Serial communication with a WiSafe2-to-HomeAssistant bridge."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import serial_asyncio_fast
from homeassistant.config_entries import ConfigEntryNotReady
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util
from serial import SerialException

from .const import (
    CONF_BAUD_RATE,
    CONF_DEVICE_ID,
    CONF_DEVICE_TYPE,
    CONF_DEVICES,
    CONF_MODEL,
    CONF_PORT,
    DEFAULT_BAUD_RATE,
)

_LOGGER = logging.getLogger(__name__)
_DEVICE_ID_PATTERN = re.compile(r"^[0-9A-F]{6}$")
_MODEL_PATTERN = re.compile(r"^[0-9A-F]{4}$")
_RECONNECT_DELAY = 10

type UpdateCallback = Callable[[], None]
type NewDeviceCallback = Callable[[str], None]


@dataclass(slots=True)
class DetectorState:
    """The latest state received for one detector."""

    device_id: str
    model: str | None = None
    device_type: str | None = None
    event: str | None = None
    result: str | None = None
    base: str | None = None
    battery: str | None = None
    last_seen: datetime | None = None


class FireAngelBridge:
    """Manage the serial bridge and discovered detector state."""

    def __init__(self, hass: HomeAssistant, entry: Any) -> None:
        """Initialize the bridge."""
        self.hass = hass
        self.entry = entry
        self.port: str = entry.data[CONF_PORT]
        self.baud_rate: int = entry.data.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE)
        self.devices: dict[str, DetectorState] = {}
        self.connected = False
        self.last_message: str | None = None
        self.last_heartbeat: datetime | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task[None] | None = None
        self._update_callbacks: set[UpdateCallback] = set()
        self._new_device_callbacks: set[NewDeviceCallback] = set()

        for device in entry.options.get(CONF_DEVICES, []):
            device_id = self.normalize_device_id(device.get(CONF_DEVICE_ID, ""))
            model = self.normalize_model(device.get(CONF_MODEL))
            if device_id is not None:
                self.devices[device_id] = DetectorState(
                    device_id,
                    model=model,
                    device_type=device.get(CONF_DEVICE_TYPE),
                )

    @staticmethod
    def normalize_device_id(value: str) -> str | None:
        """Normalize and validate a detector ID."""
        normalized = value.strip().replace(":", "").replace("-", "").upper()
        return normalized if _DEVICE_ID_PATTERN.fullmatch(normalized) else None

    @staticmethod
    def normalize_model(value: str | None) -> str | None:
        """Normalize and validate a model code."""
        if not value:
            return None
        normalized = value.strip().replace(":", "").replace("-", "").upper()
        return normalized if _MODEL_PATTERN.fullmatch(normalized) else None

    async def async_start(self) -> None:
        """Open the serial connection and start reading."""
        try:
            await self._async_connect()
        except (OSError, SerialException) as err:
            raise ConfigEntryNotReady(
                f"Unable to open FireAngel bridge at {self.port}: {err}"
            ) from err
        self._task = self.hass.async_create_background_task(
            self._async_read_forever(),
            "FireAngel Pro Connected serial reader",
        )

    async def async_stop(self) -> None:
        """Stop reading and close the serial connection."""
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        self._close_writer()
        self.connected = False

    async def _async_connect(self) -> None:
        """Connect to the configured serial port."""
        self._reader, self._writer = await serial_asyncio_fast.open_serial_connection(
            url=self.port,
            baudrate=self.baud_rate,
        )
        self.connected = True
        self._notify_update()

    async def _async_read_forever(self) -> None:
        """Read lines and reconnect after serial failures."""
        while True:
            try:
                if self._reader is None:
                    await self._async_connect()
                line = await self._reader.readline()
                if not line:
                    raise SerialException("Serial connection closed")
                self.async_process_line(line.decode(errors="replace"))
            except asyncio.CancelledError:
                raise
            except (OSError, SerialException) as err:
                _LOGGER.warning("FireAngel serial connection lost: %s", err)
                self.connected = False
                self._reader = None
                self._close_writer()
                self._notify_update()
                await asyncio.sleep(_RECONNECT_DELAY)

    def _close_writer(self) -> None:
        """Close the current serial writer."""
        if self._writer is not None:
            self._writer.close()
            self._writer = None

    async def async_send_command(self, command: bytes) -> None:
        """Send a command to the Arduino bridge."""
        if not self.connected or self._writer is None:
            raise SerialException("FireAngel bridge is not connected")
        self._writer.write(command)
        await self._writer.drain()

    @callback
    def async_process_line(self, line: str) -> None:
        """Process one line emitted by the Arduino firmware."""
        line = line.strip()
        if not line:
            return
        self.last_message = line
        now = dt_util.utcnow()

        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            self._notify_update()
            return

        if not isinstance(payload, dict):
            self._notify_update()
            return

        if "heartBeat" in payload:
            self.last_heartbeat = now
            self._notify_update()
            return

        device_id = self.normalize_device_id(str(payload.get("device", "")))
        if device_id is None:
            self._notify_update()
            return

        is_new = device_id not in self.devices
        state = self.devices.setdefault(device_id, DetectorState(device_id))
        model = self.normalize_model(payload.get("model"))
        if model is not None:
            state.model = model
        for key in ("event", "result", "base", "battery"):
            if key in payload:
                setattr(state, key, str(payload[key]).upper())
        state.last_seen = now

        if is_new:
            self._persist_devices()
            for listener in tuple(self._new_device_callbacks):
                listener(device_id)
        self._notify_update()

    @callback
    def async_add_manual_device(
        self,
        device_id: str,
        model: str | None = None,
        device_type: str | None = None,
    ) -> None:
        """Add a detector entered in the options flow."""
        normalized_id = self.normalize_device_id(device_id)
        if normalized_id is None or normalized_id in self.devices:
            return
        self.devices[normalized_id] = DetectorState(
            normalized_id,
            model=self.normalize_model(model),
            device_type=device_type,
        )
        for listener in tuple(self._new_device_callbacks):
            listener(normalized_id)
        self._notify_update()

    @callback
    def async_add_update_listener(self, listener: UpdateCallback) -> Callable[[], None]:
        """Register a bridge state listener."""
        self._update_callbacks.add(listener)
        return lambda: self._update_callbacks.discard(listener)

    @callback
    def async_add_new_device_listener(
        self, listener: NewDeviceCallback
    ) -> Callable[[], None]:
        """Register a newly discovered detector listener."""
        self._new_device_callbacks.add(listener)
        return lambda: self._new_device_callbacks.discard(listener)

    @callback
    def _notify_update(self) -> None:
        """Notify entities that state changed."""
        for listener in tuple(self._update_callbacks):
            listener()

    @callback
    def _persist_devices(self) -> None:
        """Persist discovered IDs so their devices exist after a restart."""
        options = dict(self.entry.options)
        options[CONF_DEVICES] = [
            {
                key: value
                for key, value in asdict(device).items()
                if key in (CONF_DEVICE_ID, CONF_MODEL, CONF_DEVICE_TYPE)
                and value is not None
            }
            for device in self.devices.values()
        ]
        self.hass.config_entries.async_update_entry(self.entry, options=options)
