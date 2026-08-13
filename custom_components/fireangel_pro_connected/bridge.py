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
from homeassistant.core import HassJob, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from serial import SerialException

from .const import (
    COMMAND_PAIRING,
    COMMAND_PAIRING_STATE,
    CONF_BAUD_RATE,
    CONF_BRIDGE_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DEVICE_TYPE,
    CONF_DEVICES,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    DEFAULT_BAUD_RATE,
    DEFAULT_BRIDGE_DEVICE_ID,
    DEVICE_TYPE_AUTO,
    DEVICE_TYPE_BRIDGE,
    DEVICE_TYPE_CO,
    DEVICE_TYPE_SMOKE,
    DOMAIN,
    LEGACY_COMMANDS,
    MODEL_DEVICE_TYPES,
    MODEL_NAMES,
    ProtocolMode,
)

_LOGGER = logging.getLogger(__name__)
_DEVICE_ID_PATTERN = re.compile(r"^[0-9A-F]{6}$")
_MODEL_PATTERN = re.compile(r"^[0-9A-F]{4}$")
_RAW_FRAME_PATTERN = re.compile(r"^(?:[0-9A-Fa-f]{2})+$")
_RECONNECT_DELAY = 10
_STORAGE_VERSION = 1
_COMMAND_TIMEOUT = 10
_PAIRING_WATCHDOG_TIMEOUT = 35
_ACTIVITY_TIMEOUT = 75
_V2_TYPES = {"bridge", "heartbeat", "status", "event", "command_result", "error"}
_V2_EVENTS = {
    "FIRE_TEST": "FIRE TEST",
    "CO_TEST": "CARBON MONOXIDE TEST",
    "TEST": "TEST",
    "FIRE_EMERGENCY": "FIRE EMERGENCY",
    "CO_EMERGENCY": "CARBON MONOXIDE EMERGENCY",
    "EMERGENCY": "EMERGENCY",
    "STATUS": None,
    "SILENCE": "SILENCE",
    "MISSING": "MISSING",
}

type UpdateCallback = Callable[[], None]
type NewDeviceCallback = Callable[[str], None]


@dataclass(slots=True)
class DetectorState:
    """The latest state received for one detector."""

    device_id: str
    model: str | None = None
    device_type: str | None = None
    name: str | None = None
    event: str | None = None
    result: str | None = None
    base: str | None = None
    battery: str | None = None
    last_test_pass: datetime | None = None
    last_seen: datetime | None = None
    bridge_device: bool = False
    raw_status: Any | None = None
    last_raw_frame: str | None = None
    last_raw_frame_at: datetime | None = None

    @property
    def resolved_device_type(self) -> str:
        """Return the configured or safely inferred WiSafe2 device type."""
        if self.bridge_device:
            return DEVICE_TYPE_BRIDGE
        inferred = MODEL_DEVICE_TYPES.get(self.model or "")
        if inferred == DEVICE_TYPE_CO:
            return inferred
        if "CARBON MONOXIDE" in (self.event or ""):
            return DEVICE_TYPE_CO
        if self.device_type not in (None, DEVICE_TYPE_AUTO):
            return self.device_type
        return inferred or DEVICE_TYPE_SMOKE

    @property
    def is_bridge_device(self) -> bool:
        """Return whether this is the WiSafe2 interface attached to Arduino."""
        return self.resolved_device_type == DEVICE_TYPE_BRIDGE


class FireAngelBridge:
    """Manage the serial bridge and discovered detector state."""

    def __init__(self, hass: HomeAssistant, entry: Any) -> None:
        """Initialize the bridge."""
        self.hass = hass
        self.entry = entry
        self.port: str = entry.data[CONF_PORT]
        self.baud_rate: int = entry.data.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE)
        self.bridge_device_id: str = entry.data.get(
            CONF_BRIDGE_DEVICE_ID, DEFAULT_BRIDGE_DEVICE_ID
        )
        self.devices: dict[str, DetectorState] = {}
        self.connected = False
        self.maintenance_suspended = False
        self.last_message: str | None = None
        self.last_message_summary: str | None = None
        self.last_heartbeat: datetime | None = None
        self.last_activity: datetime | None = None
        self.protocol_mode = ProtocolMode.UNKNOWN
        self.protocol_version: int | None = None
        self.firmware_version: str | None = None
        self.radio_state: str | None = None
        self.bridge_uptime: int | None = None
        self.diagnostic_counters: dict[str, int] = {}
        self.last_error: str | None = None
        self.last_command_result: dict[str, Any] | None = None
        self._next_request_id = 0
        self._pending_commands: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._pending_command_names: dict[int, str] = {}
        self._write_lock = asyncio.Lock()
        self._pairing_active = False
        self._pairing_request_id: int | None = None
        self._pairing_finished = asyncio.Event()
        self._pairing_finished.set()
        self._cancel_pairing_watchdog: Callable[[], None] | None = None
        self._cancel_activity_timeout: Callable[[], None] | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task[None] | None = None
        self._update_callbacks: set[UpdateCallback] = set()
        self._new_device_callbacks: set[NewDeviceCallback] = set()
        self._store: Store[dict[str, dict[str, str]]] = Store(
            hass, _STORAGE_VERSION, f"fireangel_pro_connected.{entry.entry_id}"
        )

        for device in entry.options.get(CONF_DEVICES, []):
            device_id = self.normalize_device_id(device.get(CONF_DEVICE_ID, ""))
            model = self.normalize_model(device.get(CONF_MODEL))
            if device_id is not None:
                self.devices[device_id] = DetectorState(
                    device_id,
                    model=model,
                    device_type=device.get(CONF_DEVICE_TYPE),
                    name=device.get(CONF_NAME),
                    bridge_device=device_id == self.bridge_device_id,
                )

    async def async_load_persisted_state(self) -> None:
        """Restore detector status without putting runtime data in entry options."""
        stored = await self._store.async_load()
        if not stored:
            return
        for device_id, values in stored.items():
            if (state := self.devices.get(device_id)) is None:
                continue
            for key in ("event", "result", "base", "battery", "last_raw_frame"):
                if key in values:
                    setattr(state, key, values[key])
            if (value := values.get("last_test_pass")) is not None:
                timestamp = dt_util.parse_datetime(value)
                if timestamp is not None and timestamp.tzinfo is not None:
                    state.last_test_pass = timestamp
            if (value := values.get("last_raw_frame_at")) is not None:
                timestamp = dt_util.parse_datetime(value)
                if timestamp is not None and timestamp.tzinfo is not None:
                    state.last_raw_frame_at = timestamp

    @staticmethod
    def normalize_device_id(value: str) -> str | None:
        """Normalize and validate a detector ID."""
        normalized = value.strip().replace(":", "").replace("-", "").upper()
        return normalized if _DEVICE_ID_PATTERN.fullmatch(normalized) else None

    @staticmethod
    def normalize_model(value: str | None) -> str | None:
        """Normalize and validate a model code."""
        if not isinstance(value, str) or not value:
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

    async def async_suspend_for_maintenance(self) -> None:
        """Release the serial port until maintenance is explicitly finished."""
        self.maintenance_suspended = True
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        self._reader = None
        self._close_writer()
        # Let the serial transport's close callback run before reporting that
        # another process may claim the device.
        await asyncio.sleep(0)
        self.connected = False
        self._cancel_activity_timer()
        self._notify_update()

    async def async_resume_from_maintenance(self) -> None:
        """Allow the normal serial reader and reconnect loop to run again."""
        if not self.maintenance_suspended and self._task is not None:
            return
        self.maintenance_suspended = False
        if self._task is None:
            self._task = self.hass.async_create_background_task(
                self._async_read_forever(),
                "FireAngel Pro Connected serial reader",
            )
        self._notify_update()

    async def async_stop(self) -> None:
        """Stop reading and close the serial connection."""
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        self._close_writer()
        self.connected = False
        self._set_protocol(ProtocolMode.UNKNOWN)
        self._cancel_activity_timer()

    async def _async_connect(self) -> None:
        """Connect to the configured serial port."""
        if self.maintenance_suspended:
            return
        self._set_protocol(ProtocolMode.UNKNOWN)
        self._reader, self._writer = await serial_asyncio_fast.open_serial_connection(
            url=self.port,
            baudrate=self.baud_rate,
        )
        self.connected = True
        self._notify_update()

    async def _async_read_forever(self) -> None:
        """Read lines and reconnect after serial failures."""
        while not self.maintenance_suspended:
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
                self.last_error = str(err)
                self._reader = None
                self._close_writer()
                self._notify_update()
                if not self.maintenance_suspended:
                    await asyncio.sleep(_RECONNECT_DELAY)

    def _close_writer(self) -> None:
        """Close the current serial writer."""
        self._finish_pairing()
        if self._writer is not None:
            self._writer.close()
            self._writer = None

    def _set_protocol(self, mode: ProtocolMode) -> None:
        """Set a newly detected protocol and cancel incompatible requests."""
        if mode == self.protocol_mode:
            return
        for future in self._pending_commands.values():
            if not future.done():
                future.set_exception(SerialException("Bridge protocol changed"))
        self._pending_commands.clear()
        self._pending_command_names.clear()
        self._finish_pairing()
        self.protocol_mode = mode
        if mode != ProtocolMode.V2:
            self.protocol_version = None
            self.firmware_version = None
            self.radio_state = None
            self.bridge_uptime = None
            self.diagnostic_counters = {}

    async def async_send_command(self, command: str) -> dict[str, Any] | None:
        """Encode and send a semantic command for the detected protocol."""
        if not self.connected or self._writer is None:
            raise SerialException("FireAngel bridge is not connected")
        if self.protocol_mode == ProtocolMode.UNKNOWN:
            raise SerialException("Waiting for firmware identification")
        if command not in LEGACY_COMMANDS:
            raise ValueError(f"Unsupported FireAngel command: {command}")
        request_id: int | None = None
        future: asyncio.Future[dict[str, Any]] | None = None
        try:
            async with self._write_lock:
                await self._pairing_finished.wait()
                if not self.connected or self._writer is None:
                    raise SerialException("FireAngel bridge is not connected")
                if self.protocol_mode == ProtocolMode.LEGACY:
                    self._writer.write(LEGACY_COMMANDS[command])
                    await self._writer.drain()
                    if command == COMMAND_PAIRING:
                        self._start_pairing()
                    return None

                request_id = self._allocate_request_id()
                future = asyncio.get_running_loop().create_future()
                self._pending_commands[request_id] = future
                self._pending_command_names[request_id] = command
                encoded = (
                    json.dumps(
                        {"command": command, "id": request_id},
                        separators=(",", ":"),
                    ).encode()
                    + b"\n"
                )
                self._writer.write(encoded)
                await self._writer.drain()
                if command == COMMAND_PAIRING:
                    self._start_pairing(request_id)
            assert future is not None
            return await asyncio.wait_for(future, _COMMAND_TIMEOUT)
        finally:
            if request_id is not None:
                self._pending_commands.pop(request_id, None)
                self._pending_command_names.pop(request_id, None)

    def _start_pairing(self, request_id: int | None = None) -> None:
        """Prevent further management writes until pairing finishes."""
        self._pairing_active = True
        self._pairing_request_id = request_id
        self._pairing_finished.clear()

    def _finish_pairing(self) -> None:
        """Release commands serialized behind an active pairing operation."""
        self._cancel_pairing_watchdog_timer()
        self._pairing_active = False
        self._pairing_request_id = None
        self._pairing_finished.set()

    def _start_pairing_watchdog(self) -> None:
        """Bound the wait for the terminal result after pairing is accepted."""
        self._cancel_pairing_watchdog_timer()
        self._cancel_pairing_watchdog = async_call_later(
            self.hass,
            _PAIRING_WATCHDOG_TIMEOUT,
            HassJob(
                self._pairing_watchdog_expired,
                "FireAngel pairing terminal-result watchdog",
                cancel_on_shutdown=True,
            ),
        )

    @callback
    def _pairing_watchdog_expired(self, _now: datetime) -> None:
        """Release management commands if the terminal pairing result was lost."""
        self._cancel_pairing_watchdog = None
        if not self._pairing_active:
            return
        self.last_error = "Pairing terminal result was not received"
        self._finish_pairing()
        self._notify_update()

    def _cancel_pairing_watchdog_timer(self) -> None:
        """Cancel a pending terminal pairing-result watchdog."""
        if self._cancel_pairing_watchdog is not None:
            self._cancel_pairing_watchdog()
            self._cancel_pairing_watchdog = None

    @property
    def activity_available(self) -> bool:
        """Return whether recent recognized traffic confirms bridge activity."""
        return (
            self.connected
            and self.last_activity is not None
            and (dt_util.utcnow() - self.last_activity).total_seconds()
            <= _ACTIVITY_TIMEOUT
        )

    def _record_activity(self, now: datetime) -> None:
        """Record traffic and arrange an entity refresh when it becomes stale."""
        self.last_activity = now
        self._cancel_activity_timer()
        self._cancel_activity_timeout = async_call_later(
            self.hass,
            _ACTIVITY_TIMEOUT,
            HassJob(
                lambda _now: self._notify_update(),
                "FireAngel activity availability timeout",
                cancel_on_shutdown=True,
            ),
        )

    def _cancel_activity_timer(self) -> None:
        """Cancel the current activity-expiry refresh."""
        if self._cancel_activity_timeout is not None:
            self._cancel_activity_timeout()
            self._cancel_activity_timeout = None

    def _allocate_request_id(self) -> int:
        """Allocate an unused 16-bit V2 request ID."""
        for _ in range(65536):
            request_id = self._next_request_id
            self._next_request_id = (request_id + 1) % 65536
            if request_id not in self._pending_commands:
                return request_id
        raise SerialException("No command request IDs available")

    @callback
    def async_process_line(self, line: str) -> None:
        """Process one line emitted by the Arduino firmware."""
        line = line.strip()
        if not line:
            return
        now = dt_util.utcnow()

        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            self._record_message(
                line, line if self._is_legacy_text(line) else "Unrecognized message"
            )
            if self._is_legacy_text(line):
                self._set_protocol(ProtocolMode.LEGACY)
                self._record_activity(now)
                upper = line.upper()
                if upper == "CMD BUSY":
                    self.last_error = "CMD BUSY"
                elif upper in {"NETWORK PAIRED", "NETWORK UNPAIRED"}:
                    self._finish_pairing()
            self._notify_update()
            return

        if not isinstance(payload, dict):
            self._record_message(line, "Unrecognized message")
            self._notify_update()
            return

        message_type = payload.get("type")
        if isinstance(message_type, str):
            normalized_type = message_type.casefold()
            if normalized_type != "heartbeat":
                self._record_message(
                    line, self._summarize_v2_message(normalized_type, payload)
                )
            if normalized_type in _V2_TYPES:
                protocol = payload.get("protocol")
                if "protocol" in payload and (
                    not isinstance(protocol, int)
                    or isinstance(protocol, bool)
                    or protocol != 2
                ):
                    _LOGGER.debug(
                        "Ignoring V2 envelope with incompatible protocol: %s",
                        protocol,
                    )
                    self._notify_update()
                    return
                self._set_protocol(ProtocolMode.V2)
                self.protocol_version = 2
                # A recognized typed message is valid V2 traffic even when a
                # future enum value is not understood by this integration.
                self._record_activity(now)
                self._process_v2(normalized_type, payload, now)
            else:
                _LOGGER.debug("Ignoring unknown V2 message type: %s", message_type)
                self._notify_update()
            return

        # Firmware variants differ in the capitalization of JSON field names
        # (notably ``device`` versus ``Device``). Treat protocol keys as
        # case-insensitive while leaving their values untouched.
        fields = {
            key.casefold(): value
            for key, value in payload.items()
            if isinstance(key, str)
        }

        if "heartbeat" in fields:
            self._set_protocol(ProtocolMode.LEGACY)
            self.last_heartbeat = now
            self._record_activity(now)
            self._notify_update()
            return

        self._record_message(line, self._summarize_legacy_message(fields))
        device_id = self.normalize_device_id(str(fields.get("device", "")))
        if device_id is None:
            self._notify_update()
            return
        self._set_protocol(ProtocolMode.LEGACY)
        self._update_detector(fields, now, v2=False)

    def _record_message(self, line: str, summary: str) -> None:
        """Retain a raw non-heartbeat line and its display-friendly summary."""
        self.last_message = line
        self.last_message_summary = summary[:255]

    def _summarize_v2_message(self, message_type: str, payload: dict[str, Any]) -> str:
        """Build a concise summary from validated protocol-2 fields."""
        if message_type == "event":
            parts = [
                self.normalize_device_id(str(payload.get("device", ""))) or "Detector"
            ]
            if isinstance(event := payload.get("event"), str):
                parts.append(_V2_EVENTS.get(event.upper(), event.upper()) or "STATUS")
            if isinstance(result := payload.get("result"), str):
                parts.append(result.upper())
            return " · ".join(parts)
        if message_type == "bridge":
            parts = ["Bridge"]
            if isinstance(event := payload.get("event"), str):
                parts.append(event.replace("_", " ").title())
            if isinstance(protocol := payload.get("protocol"), int):
                parts.append(f"Protocol {protocol}")
            return " · ".join(parts)
        if message_type == "status":
            return "Bridge · Status"
        if message_type == "command_result":
            request_id = payload.get("id")
            command = payload.get("command")
            if not isinstance(command, str) and isinstance(request_id, int):
                command = self._pending_command_names.get(request_id)
            label = (
                command.replace("_", " ").title()
                if isinstance(command, str)
                else "Command"
            )
            result = payload.get("result", payload.get("status"))
            return f"{label} · {result.title()}" if isinstance(result, str) else label
        if message_type == "error":
            error = payload.get("code", payload.get("message", payload.get("error")))
            return f"Error · {error}" if isinstance(error, str) else "Error"
        return f"Unrecognized message · {message_type}"

    def _summarize_legacy_message(self, fields: dict[str, Any]) -> str:
        """Build a concise summary from legacy detector fields."""
        parts = [self.normalize_device_id(str(fields.get("device", ""))) or "Detector"]
        if isinstance(event := fields.get("event"), str):
            parts.append(event.upper())
            if isinstance(result := fields.get("result"), str):
                parts.append(result.upper())
            return " · ".join(parts)
        for key, label in (("battery", "Battery"), ("base", "Base")):
            if isinstance(value := fields.get(key), str):
                parts.append(f"{label} {value.upper()}")
        if len(parts) == 1 and isinstance(model := fields.get("model"), str):
            parts.append(f"Model {model.upper()}")
        return " · ".join(parts)

    @staticmethod
    def _is_legacy_text(line: str) -> bool:
        """Recognize established legacy startup and command responses."""
        upper = line.upper()
        return upper.startswith("INIT ") or upper in {
            "INIT OK",
            "CMD BUSY",
            "NETWORK PAIRED",
            "NETWORK UNPAIRED",
        }

    @callback
    def _process_v2(
        self, message_type: str, payload: dict[str, Any], now: datetime
    ) -> None:
        """Validate and dispatch a typed protocol-2 message."""
        if message_type == "bridge":
            if payload.get("protocol") == 2:
                self.protocol_version = 2
            if isinstance(payload.get("firmware"), str):
                self.firmware_version = payload["firmware"]
            if isinstance(payload.get("radio"), str):
                self.radio_state = payload["radio"]
        elif message_type in {"heartbeat", "status"}:
            if message_type == "heartbeat":
                self.last_heartbeat = now
            if isinstance(payload.get("uptime"), int):
                self.bridge_uptime = payload["uptime"]
            if isinstance(payload.get("radio"), str):
                self.radio_state = payload["radio"]
            if isinstance(payload.get("firmware"), str):
                self.firmware_version = payload["firmware"]
            counters = payload.get("diagnostics")
            if isinstance(counters, dict):
                self.diagnostic_counters.update(
                    {
                        key: value
                        for key, value in counters.items()
                        if isinstance(key, str)
                        and isinstance(value, int)
                        and not isinstance(value, bool)
                    }
                )
        elif message_type == "event":
            self._process_v2_event(payload, now)
            return
        elif message_type == "command_result":
            self._process_command_result(payload)
        elif message_type == "error":
            self.last_error = str(
                payload.get(
                    "code",
                    payload.get("message", payload.get("error", "Unknown error")),
                )
            )
            request_id = payload.get("id")
            if isinstance(request_id, int):
                if request_id == self._pairing_request_id:
                    self._finish_pairing()
                if (
                    future := self._pending_commands.get(request_id)
                ) is not None and not future.done():
                    future.set_exception(SerialException(self.last_error))
        self._notify_update()

    def _process_v2_event(self, payload: dict[str, Any], now: datetime) -> None:
        """Normalize a V2 detector event into the shared state path."""
        device_id = self.normalize_device_id(str(payload.get("device", "")))
        event = payload.get("event")
        if device_id is None or not isinstance(event, str):
            self._notify_update()
            return
        event_name = event.upper()
        if event_name not in _V2_EVENTS:
            self._notify_update()
            return
        fields = dict(payload)
        normalized_event = _V2_EVENTS[event_name]
        if normalized_event is None:
            fields.pop("event", None)
        else:
            fields["event"] = normalized_event
        self._update_detector(fields, now, v2=True)

    def _process_command_result(self, payload: dict[str, Any]) -> bool:
        """Record a command result and resolve its matching request."""
        request_id = payload.get("id")
        status = payload.get("result", payload.get("status"))
        if not isinstance(request_id, int) or not isinstance(status, str):
            return False
        self.last_command_result = dict(payload)
        command = self._pending_command_names.get(request_id)
        if (
            request_id == self._pairing_request_id
            and command == COMMAND_PAIRING
            and status == "accepted"
        ):
            self._start_pairing_watchdog()
        if request_id == self._pairing_request_id and status in {
            "paired",
            "unpaired",
            "already_paired",
            "timeout",
        }:
            self._finish_pairing()
        future = self._pending_commands.get(request_id)
        if future is None or future.done():
            return True
        if status == "timeout":
            future.set_exception(
                SerialException(f"FireAngel {command or 'command'} timed out")
            )
            return True
        if command == COMMAND_PAIRING_STATE:
            complete = status in {"paired", "unpaired"}
        elif command == COMMAND_PAIRING:
            complete = status in {"accepted", "paired", "unpaired", "already_paired"}
        else:
            complete = status in {"accepted", "paired", "unpaired"}
        if complete:
            future.set_result(dict(payload))
        return True

    @callback
    def _update_detector(
        self, fields: dict[str, Any], now: datetime, *, v2: bool
    ) -> None:
        """Merge normalized wire fields into detector runtime state."""
        device_id = self.normalize_device_id(str(fields.get("device", "")))
        if device_id is None:
            self._notify_update()
            return
        self._record_activity(now)

        is_new = device_id not in self.devices
        state = self.devices.setdefault(
            device_id,
            DetectorState(device_id, bridge_device=device_id == self.bridge_device_id),
        )
        model = self.normalize_model(fields.get("model"))
        inventory_changed = False
        if model is not None:
            inventory_changed = state.model != model
            state.model = model
        for key in ("base", "battery"):
            value = fields.get(key)
            if not isinstance(value, str):
                continue
            normalized = value.upper()
            if v2 and key == "base" and normalized not in {"ON", "OFF", "MISSING"}:
                continue
            if v2 and key == "battery" and normalized not in {"OK", "LOW", "MISSING"}:
                continue
            setattr(state, key, normalized)
        event_value = fields.get("event")
        if isinstance(event_value, str):
            event = event_value.strip().upper()
            state.event = event
            if event == "TEST" or event.endswith(" TEST"):
                result_value = fields.get("result")
                state.result = (
                    result_value.strip().upper()
                    if isinstance(result_value, str)
                    else None
                )
            else:
                state.result = None
        if v2 and "raw_status" in fields:
            state.raw_status = fields["raw_status"]
        if (
            v2
            and isinstance(raw_frame := fields.get("raw_frame"), str)
            and _RAW_FRAME_PATTERN.fullmatch(raw_frame)
        ):
            state.last_raw_frame = raw_frame.upper()
            state.last_raw_frame_at = now
        event = str(fields.get("event", "")).strip().upper()
        result = str(fields.get("result", "")).strip().upper()
        if (
            result == "PASS"
            and (event == "TEST" or event.endswith(" TEST"))
            and (v2 or not state.is_bridge_device)
        ):
            state.last_test_pass = now
        state.last_seen = now

        self._store.async_delay_save(self._stored_status)
        if is_new or inventory_changed:
            self._persist_devices()
        if inventory_changed and not is_new and not state.is_bridge_device:
            self._update_device_registry_model(state)
        if is_new:
            for listener in tuple(self._new_device_callbacks):
                listener(device_id)
        self._notify_update()

    @callback
    def _update_device_registry_model(self, state: DetectorState) -> None:
        """Update a registered detector after its model is learned."""
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, state.device_id)}
        )
        if device is not None:
            device_registry.async_update_device(
                device.id,
                model=MODEL_NAMES.get(state.model, state.model),
            )

    @callback
    def async_add_manual_device(
        self,
        device_id: str,
        model: str | None = None,
        device_type: str | None = None,
        name: str | None = None,
    ) -> None:
        """Add a detector entered in the options flow."""
        normalized_id = self.normalize_device_id(device_id)
        if normalized_id is None or normalized_id in self.devices:
            return
        self.devices[normalized_id] = DetectorState(
            normalized_id,
            model=self.normalize_model(model),
            device_type=device_type,
            name=name,
            bridge_device=normalized_id == self.bridge_device_id,
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
        """Persist detector inventory in config-entry options."""
        options = dict(self.entry.options)
        options[CONF_DEVICES] = [
            {
                key: value
                for key, value in asdict(device).items()
                if key in (CONF_DEVICE_ID, CONF_MODEL, CONF_DEVICE_TYPE, CONF_NAME)
                and value is not None
            }
            for device in self.devices.values()
        ]
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    @callback
    def _stored_status(self) -> dict[str, dict[str, str]]:
        """Return the restorable runtime status for storage."""
        return {
            device_id: {
                key: value
                for key in ("event", "result", "base", "battery", "last_raw_frame")
                if (value := getattr(device, key)) is not None
            }
            | (
                {"last_test_pass": device.last_test_pass.isoformat()}
                if device.last_test_pass is not None
                else {}
            )
            | (
                {"last_raw_frame_at": device.last_raw_frame_at.isoformat()}
                if device.last_raw_frame_at is not None
                else {}
            )
            for device_id, device in self.devices.items()
        }
