"""Tests for the WiSafe2 serial bridge protocol."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from serial import SerialException

from custom_components.fireangel_pro_connected.bridge import FireAngelBridge
from custom_components.fireangel_pro_connected.const import (
    CONF_BRIDGE_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DEVICE_TYPE,
    CONF_DEVICES,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    DEFAULT_BRIDGE_DEVICE_ID,
    DEVICE_TYPE_HEAT,
    DOMAIN,
)


def make_bridge(hass: HomeAssistant, *, options=None) -> FireAngelBridge:
    """Create a bridge without opening hardware."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_PORT: "/dev/ttyUSB0"}, options=options or {}
    )
    entry.add_to_hass(hass)
    return FireAngelBridge(hass, entry)


def test_parse_message_and_discover_device(hass: HomeAssistant) -> None:
    """Test parsing firmware JSON and persisting an unfamiliar detector."""
    bridge = make_bridge(hass)
    discovered: list[str] = []
    bridge.async_add_new_device_listener(discovered.append)

    bridge.async_process_line(
        '{"device":"a1b2c3", "model":"1103", "event":"FIRE TEST", '
        '"result":"PASS", "base":"ON", "battery":"OK"}'
    )

    detector = bridge.devices["A1B2C3"]
    assert detector.model == "1103"
    assert detector.event == "FIRE TEST"
    assert detector.result == "PASS"
    assert detector.base == "ON"
    assert detector.battery == "OK"
    assert detector.last_seen is not None
    assert discovered == ["A1B2C3"]
    assert bridge.entry.options[CONF_DEVICES] == [
        {CONF_DEVICE_ID: "A1B2C3", "model": "1103"}
    ]


def test_bridge_role_uses_configured_device_id(hass: HomeAssistant) -> None:
    """Identify the bridge by device ID without classifying its donor model."""
    bridge = make_bridge(hass)
    bridge.async_process_line(
        f'{{"device":"{DEFAULT_BRIDGE_DEVICE_ID}", "model":"C304"}}'
    )
    bridge.async_process_line('{"device":"F0A1B2", "model":"C304"}')

    assert bridge.devices[DEFAULT_BRIDGE_DEVICE_ID].is_bridge_device
    assert not bridge.devices["F0A1B2"].is_bridge_device

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: "/dev/ttyUSB1", CONF_BRIDGE_DEVICE_ID: "F0A1B2"},
    )
    entry.add_to_hass(hass)
    configured = FireAngelBridge(hass, entry)
    configured.async_process_line('{"device":"F0A1B2", "model":"ED08"}')
    assert configured.devices["F0A1B2"].is_bridge_device


def test_merge_partial_messages_without_rediscovery(hass: HomeAssistant) -> None:
    """Test that partial firmware messages update the same detector."""
    bridge = make_bridge(hass)
    discovered: list[str] = []
    bridge.async_add_new_device_listener(discovered.append)

    bridge.async_process_line('{"device":"D4E5F6", "event":"MISSING"}')
    bridge.async_process_line(
        '{"device":"D4E5F6", "model":"7803", "base":"ON", "battery":"LOW"}'
    )

    detector = bridge.devices["D4E5F6"]
    assert detector.event == "MISSING"
    assert detector.model == "7803"
    assert detector.base == "ON"
    assert detector.battery == "LOW"
    assert discovered == ["D4E5F6"]
    assert bridge.entry.options[CONF_DEVICES] == [
        {CONF_DEVICE_ID: "D4E5F6", CONF_MODEL: "7803"}
    ]


def test_parse_case_insensitive_firmware_fields(hass: HomeAssistant) -> None:
    """Test field capitalization used by older firmware variants."""
    bridge = make_bridge(hass)

    bridge.async_process_line(
        '{"Device":"EFA567", "model":"ED08", "base":"OFF", "battery":"OK"}'
    )

    detector = bridge.devices["EFA567"]
    assert detector.model == "ED08"
    assert detector.base == "OFF"
    assert detector.battery == "OK"
    assert detector.last_seen is not None


def test_heartbeat_and_plain_status(hass: HomeAssistant) -> None:
    """Test heartbeat JSON and non-JSON command responses."""
    bridge = make_bridge(hass)
    bridge.async_process_line('{"heartBeat":"3"}')
    assert bridge.last_heartbeat is not None

    bridge.async_process_line("NETWORK PAIRED")
    assert bridge.last_message == "NETWORK PAIRED"
    assert bridge.devices == {}


def test_normalize_hex_identifiers() -> None:
    """Test accepted migration ID formats."""
    assert FireAngelBridge.normalize_device_id("a1-b2-c3") == "A1B2C3"
    assert FireAngelBridge.normalize_device_id("A1:B2:C3") == "A1B2C3"
    assert FireAngelBridge.normalize_device_id("A1B2C") is None
    assert FireAngelBridge.normalize_model("11:03") == "1103"


async def test_restore_manual_listeners_and_ignored_lines(
    hass: HomeAssistant,
) -> None:
    bridge = make_bridge(
        hass,
        options={
            CONF_DEVICES: [
                {
                    CONF_DEVICE_ID: "a1-b2-c3",
                    CONF_MODEL: "11:03",
                    CONF_NAME: "Kitchen Fireangel",
                    CONF_DEVICE_TYPE: DEVICE_TYPE_HEAT,
                },
                {CONF_DEVICE_ID: "invalid"},
            ]
        },
    )
    assert bridge.devices["A1B2C3"].model == "1103"
    assert bridge.devices["A1B2C3"].name == "Kitchen Fireangel"
    assert FireAngelBridge.normalize_model(None) is None
    assert FireAngelBridge.normalize_model("bad") is None
    updates, devices = Mock(), Mock()
    remove_update = bridge.async_add_update_listener(updates)
    remove_device = bridge.async_add_new_device_listener(devices)
    bridge.async_add_manual_device("C0:FF:EE", "78-03", DEVICE_TYPE_HEAT)
    bridge.async_add_manual_device("invalid")
    bridge.async_add_manual_device("C0FFEE")
    assert bridge.devices["C0FFEE"].model == "7803"
    devices.assert_called_once_with("C0FFEE")
    updates.assert_called_once_with()
    remove_update()
    remove_device()
    bridge.async_add_manual_device("D0D0D0")
    updates.assert_called_once_with()
    bridge.async_process_line("  ")
    bridge.async_process_line("[]")
    bridge.async_process_line('{"device":"bad"}')


async def test_persist_and_restore_status_outside_entry_options(
    hass: HomeAssistant,
) -> None:
    """Test runtime status uses integration storage rather than user options."""
    bridge = make_bridge(hass, options={CONF_DEVICES: [{CONF_DEVICE_ID: "A1B2C3"}]})
    bridge.async_process_line(
        '{"device":"A1B2C3", "event":"FIRE TEST", "result":"PASS", '
        '"base":"ON", "battery":"LOW"}'
    )
    await asyncio.sleep(0)
    await hass.async_block_till_done()

    assert bridge.entry.options == {CONF_DEVICES: [{CONF_DEVICE_ID: "A1B2C3"}]}
    restored = FireAngelBridge(hass, bridge.entry)
    await restored.async_load_persisted_state()
    detector = restored.devices["A1B2C3"]
    assert detector.event == "FIRE TEST"
    assert detector.result == "PASS"
    assert detector.base == "ON"
    assert detector.battery == "LOW"

    restored._store.async_load = AsyncMock(
        return_value={
            "A1B2C3": {"event": "CLEAR"},
            "FFFFFF": {"event": "FIRE EMERGENCY"},
        }
    )
    await restored.async_load_persisted_state()
    assert detector.event == "CLEAR"


async def test_serial_lifecycle(hass: HomeAssistant) -> None:
    bridge = make_bridge(hass)
    reader, writer = AsyncMock(), Mock()
    writer.drain = AsyncMock()
    update = Mock()
    bridge.async_add_update_listener(update)
    with patch(
        "custom_components.fireangel_pro_connected.bridge.serial_asyncio_fast.open_serial_connection",
        new=AsyncMock(return_value=(reader, writer)),
    ):
        await bridge._async_connect()
    assert bridge.connected
    update.assert_called_once_with()
    await bridge.async_send_command(b"1~")
    writer.write.assert_called_once_with(b"1~")
    bridge._task = hass.async_create_task(asyncio.sleep(60))
    await bridge.async_stop()
    writer.close.assert_called_once_with()
    await bridge.async_stop()
    with pytest.raises(SerialException):
        await bridge.async_send_command(b"1~")
    with (
        patch.object(
            bridge, "_async_connect", AsyncMock(side_effect=OSError("no port"))
        ),
        pytest.raises(ConfigEntryNotReady, match="Unable to open"),
    ):
        await bridge.async_start()


async def test_start_and_read_loops(hass: HomeAssistant) -> None:
    bridge = make_bridge(hass)
    with (
        patch.object(bridge, "_async_connect", AsyncMock()),
        patch.object(bridge, "_async_read_forever", AsyncMock()),
    ):
        await bridge.async_start()
        await bridge._task
    await bridge.async_stop()

    reader, writer = AsyncMock(), Mock()
    reader.readline.side_effect = [b'{"heartBeat":"1"}\n', b""]
    bridge._reader, bridge._writer, bridge.connected = reader, writer, True

    async def cancel_sleep(delay):
        assert delay == 10
        raise asyncio.CancelledError

    with (
        patch(
            "custom_components.fireangel_pro_connected.bridge.asyncio.sleep",
            cancel_sleep,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await bridge._async_read_forever()
    assert bridge.last_heartbeat is not None
    writer.close.assert_called_once_with()
    await bridge.async_stop()

    reconnect_reader = AsyncMock()
    reconnect_reader.readline.side_effect = asyncio.CancelledError

    async def connect():
        bridge._reader = reconnect_reader

    bridge._reader = None
    with (
        patch.object(bridge, "_async_connect", connect),
        pytest.raises(asyncio.CancelledError),
    ):
        await bridge._async_read_forever()
