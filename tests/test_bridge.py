"""Tests for the WiSafe2 serial bridge protocol."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from serial import SerialException

from custom_components.fireangel_pro_connected.bridge import FireAngelBridge
from custom_components.fireangel_pro_connected.const import (
    COMMAND_PAIRING,
    COMMAND_PAIRING_STATE,
    COMMAND_SILENCE_CO,
    COMMAND_SILENCE_FIRE,
    COMMAND_SOUND_CO,
    COMMAND_SOUND_COMBINED,
    COMMAND_SOUND_FIRE,
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
    ProtocolMode,
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
    assert detector.last_test_pass == detector.last_seen
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


def test_last_test_pass_updates_only_for_successful_tests(
    hass: HomeAssistant,
) -> None:
    """Test successful test recognition without changes from other messages."""
    bridge = make_bridge(hass)
    first = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)
    later = datetime(2026, 8, 10, 11, 0, tzinfo=UTC)

    with patch(
        "custom_components.fireangel_pro_connected.bridge.dt_util.utcnow",
        side_effect=[first, first, first, first, later],
    ):
        bridge.async_process_line(
            '{"device":"A1B2C3", "event":"FIRE TEST", "result":"FAIL"}'
        )
        assert bridge.devices["A1B2C3"].last_test_pass is None

        bridge.async_process_line(
            '{"device":"A1B2C3", "event":"FIRE EMERGENCY", "result":"PASS"}'
        )
        assert bridge.devices["A1B2C3"].last_test_pass is None

        bridge.async_process_line(
            '{"device":"A1B2C3", "event":"FIRE TEST", "result":"PASS"}'
        )
        assert bridge.devices["A1B2C3"].last_test_pass == first

        bridge.async_process_line('{"device":"A1B2C3", "battery":"LOW", "base":"OFF"}')
        assert bridge.devices["A1B2C3"].last_test_pass == first

        bridge.async_process_line(
            '{"device":"A1B2C3", "event":"TEST", "result":"PASS"}'
        )

    assert bridge.devices["A1B2C3"].last_test_pass == later


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
    assert bridge.last_message is None

    bridge.async_process_line("NETWORK PAIRED")
    assert bridge.last_message == "NETWORK PAIRED"
    assert bridge.last_message_summary == "NETWORK PAIRED"
    assert bridge.devices == {}

    bridge.async_process_line('{"type":"heartbeat","uptime":42}')
    assert bridge.last_message == "NETWORK PAIRED"
    assert bridge.last_message_summary == "NETWORK PAIRED"
    assert bridge.bridge_uptime == 42


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
    assert detector.last_test_pass is not None
    assert detector.last_test_pass.tzinfo is not None

    restored._store.async_load = AsyncMock(
        return_value={
            "A1B2C3": {"event": "CLEAR"},
            "FFFFFF": {"event": "FIRE EMERGENCY"},
        }
    )
    await restored.async_load_persisted_state()
    assert detector.event == "CLEAR"


async def test_restore_old_persisted_status_without_last_test_pass(
    hass: HomeAssistant,
) -> None:
    """Test storage created before last-test tracking remains compatible."""
    bridge = make_bridge(hass, options={CONF_DEVICES: [{CONF_DEVICE_ID: "A1B2C3"}]})
    bridge._store.async_load = AsyncMock(
        return_value={"A1B2C3": {"event": "CLEAR", "battery": "OK"}}
    )

    await bridge.async_load_persisted_state()

    detector = bridge.devices["A1B2C3"]
    assert detector.event == "CLEAR"
    assert detector.battery == "OK"
    assert detector.last_test_pass is None


async def test_ignore_invalid_persisted_last_test_timestamp(
    hass: HomeAssistant,
) -> None:
    """Ignore a malformed timestamp while restoring the remaining status."""
    bridge = make_bridge(hass, options={CONF_DEVICES: [{CONF_DEVICE_ID: "A1B2C3"}]})
    bridge._store.async_load = AsyncMock(
        return_value={"A1B2C3": {"event": "CLEAR", "last_test_pass": "not-a-timestamp"}}
    )

    await bridge.async_load_persisted_state()

    detector = bridge.devices["A1B2C3"]
    assert detector.event == "CLEAR"
    assert detector.last_test_pass is None


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
    bridge.async_process_line('{"heartBeat":"1"}')
    await bridge.async_send_command(COMMAND_SOUND_CO)
    writer.write.assert_called_once_with(b"1~")
    bridge._task = hass.async_create_task(asyncio.sleep(60))
    await bridge.async_stop()
    writer.close.assert_called_once_with()
    await bridge.async_stop()
    with pytest.raises(SerialException):
        await bridge.async_send_command(COMMAND_SOUND_CO)
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


def test_passive_protocol_detection_and_v2_dispatch(hass: HomeAssistant) -> None:
    """Detect either protocol solely from inbound traffic and normalize V2."""
    bridge = make_bridge(hass)
    bridge.async_process_line(
        '{"type":"bridge","event":"startup","firmware":"2.0.0",'
        '"protocol":2,"radio":"ready"}'
    )
    assert bridge.protocol_mode == ProtocolMode.V2
    assert bridge.protocol_version == 2
    assert bridge.firmware_version == "2.0.0"
    assert bridge.radio_state == "ready"

    bridge.async_process_line(
        '{"type":"event","device":"a1b2c3","model":"7803",'
        '"event":"CO_TEST","result":"PASS","base":"ON","battery":"OK",'
        '"raw_status":129,"future_field":true}'
    )
    detector = bridge.devices["A1B2C3"]
    assert detector.event == "CARBON MONOXIDE TEST"
    assert detector.last_test_pass == detector.last_seen
    assert detector.raw_status == 129
    assert bridge.last_message_summary == "A1B2C3 · CARBON MONOXIDE TEST · PASS"

    bridge.async_process_line(
        '{"type":"status","uptime":42,"radio":"ready",'
        '"diagnostics":{"received":7,"bad":"ignored","flag":true}}'
    )
    assert bridge.bridge_uptime == 42
    assert bridge.diagnostic_counters == {"received": 7}

    bridge.async_process_line('{"heartBeat":"2"}')
    assert bridge.protocol_mode == ProtocolMode.LEGACY


@pytest.mark.parametrize(
    "message",
    [
        '{"type":"heartbeat","uptime":123456,"radio":"ready"}',
        '{"type":"status","uptime":123456,"radio":"ready"}',
        '{"type":"event","device":"A1B2C3","event":"STATUS",'
        '"base":"ON","battery":"OK","raw_status":0}',
    ],
)
def test_v2_protocol_version_when_startup_was_missed(
    hass: HomeAssistant, message: str
) -> None:
    """Infer Protocol 2 from every recognized envelope after startup."""
    bridge = make_bridge(hass)

    bridge.async_process_line(message)

    assert bridge.protocol_mode == ProtocolMode.V2
    assert bridge.protocol_version == 2


@pytest.mark.parametrize("protocol", [3, "2", True, None])
def test_reject_explicit_incompatible_v2_protocol(
    hass: HomeAssistant, protocol: object
) -> None:
    """Do not identify an explicitly incompatible envelope as Protocol 2."""
    bridge = make_bridge(hass)

    bridge.async_process_line(
        json.dumps({"type": "status", "protocol": protocol, "uptime": 1})
    )

    assert bridge.protocol_mode == ProtocolMode.UNKNOWN
    assert bridge.protocol_version is None


def test_last_activity_tracks_all_valid_bridge_traffic(hass: HomeAssistant) -> None:
    """Track meaningful traffic because heartbeats are idle-only keep-alives."""
    bridge = make_bridge(hass)
    start = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    messages = (
        '{"type":"bridge","event":"startup","protocol":2}',
        '{"type":"heartbeat"}',
        '{"type":"status","uptime":2}',
        '{"type":"event","device":"A1B2C3","event":"FIRE_EMERGENCY"}',
        '{"type":"command_result","id":99,"result":"accepted"}',
        '{"heartBeat":"3"}',
        '{"device":"D4E5F6","battery":"OK"}',
        "INIT OK",
    )
    times = [start + timedelta(seconds=index) for index in range(len(messages))]

    with patch(
        "custom_components.fireangel_pro_connected.bridge.dt_util.utcnow",
        side_effect=times,
    ):
        for message, expected in zip(messages, times, strict=True):
            bridge.async_process_line(message)
            assert bridge.last_activity == expected

    malformed_time = times[-1] + timedelta(seconds=1)
    with patch(
        "custom_components.fireangel_pro_connected.bridge.dt_util.utcnow",
        return_value=malformed_time,
    ):
        bridge.async_process_line('{"type":"event","device":"bad","event":"TEST"}')
        bridge.async_process_line('{"type":"command_result","id":"bad"}')
    assert bridge.last_activity == malformed_time


def test_v2_attach_event_status_partial_and_malformed(hass: HomeAssistant) -> None:
    """An event can identify V2 and malformed/unknown traffic remains harmless."""
    bridge = make_bridge(hass)
    bridge.async_process_line(
        '{"type":"event","device":"D4E5F6","event":"FIRE_EMERGENCY"}'
    )
    assert bridge.protocol_mode == ProtocolMode.V2
    assert bridge.devices["D4E5F6"].event == "FIRE EMERGENCY"
    bridge.async_process_line(
        '{"type":"event","device":"D4E5F6","event":"STATUS",'
        '"base":"OFF","battery":"LOW"}'
    )
    assert bridge.devices["D4E5F6"].event == "FIRE EMERGENCY"
    assert bridge.devices["D4E5F6"].base == "OFF"
    bridge.async_process_line('{"type":"event","device":[],"event":3}')
    bridge.async_process_line('{"type":"future","anything":true}')
    assert bridge.last_message == '{"type":"future","anything":true}'


async def test_unknown_mode_rejected_and_v2_command_correlation(
    hass: HomeAssistant,
) -> None:
    """Encode compact V2 commands and correlate interleaved results by ID."""
    bridge = make_bridge(hass)
    writer = Mock()
    writer.drain = AsyncMock()
    bridge.connected, bridge._writer = True, writer
    with pytest.raises(SerialException, match="firmware identification"):
        await bridge.async_send_command(COMMAND_SOUND_CO)

    bridge.async_process_line('{"type":"heartbeat","uptime":1}')
    first = asyncio.create_task(bridge.async_send_command(COMMAND_SOUND_CO))
    second = asyncio.create_task(bridge.async_send_command(COMMAND_PAIRING_STATE))
    await asyncio.sleep(0)
    assert [call.args[0] for call in writer.write.call_args_list] == [
        b'{"command":"sound_co","id":0}\n',
        b'{"command":"pairing_state","id":1}\n',
    ]
    bridge.async_process_line(
        '{"type":"event","device":"C0FFEE","event":"TEST","result":"PASS"}'
    )
    bridge.async_process_line('{"type":"command_result","id":1,"result":"accepted"}')
    assert not second.done()
    bridge.async_process_line('{"type":"command_result","id":0,"result":"accepted"}')
    bridge.async_process_line('{"type":"command_result","id":1,"result":"paired"}')
    assert (await first)["result"] == "accepted"
    assert (await second)["result"] == "paired"
    assert bridge.devices["C0FFEE"].last_test_pass is not None


def test_bridge_legacy_pass_is_not_detector_test(hass: HomeAssistant) -> None:
    """Keep synthetic legacy bridge actions without claiming a detector test."""
    bridge = make_bridge(hass)
    bridge.async_process_line(
        f'{{"device":"{DEFAULT_BRIDGE_DEVICE_ID}","event":"FIRE TEST","result":"PASS"}}'
    )
    state = bridge.devices[DEFAULT_BRIDGE_DEVICE_ID]
    assert state.event == "FIRE TEST"
    assert state.result == "PASS"
    assert state.last_test_pass is None


async def test_reconnect_resets_detection_and_cancels_pending(
    hass: HomeAssistant,
) -> None:
    """Every connection starts unknown and invalidates old V2 requests."""
    bridge = make_bridge(hass)
    bridge.protocol_mode = ProtocolMode.V2
    pending = asyncio.get_running_loop().create_future()
    bridge._pending_commands[9] = pending
    reader, writer = AsyncMock(), Mock()
    with patch(
        "custom_components.fireangel_pro_connected.bridge.serial_asyncio_fast.open_serial_connection",
        new=AsyncMock(return_value=(reader, writer)),
    ):
        await bridge._async_connect()
    assert bridge.protocol_mode == ProtocolMode.UNKNOWN
    with pytest.raises(SerialException, match="protocol changed"):
        await pending
    writer.write.assert_not_called()


async def test_legacy_commands_wait_for_active_pairing(hass: HomeAssistant) -> None:
    """Serialize legacy management writes until a pairing response arrives."""
    bridge = make_bridge(hass)
    writer = Mock()
    writer.drain = AsyncMock()
    bridge.connected, bridge._writer = True, writer
    bridge.async_process_line("INIT OK")

    await bridge.async_send_command(COMMAND_PAIRING)
    queued = asyncio.create_task(bridge.async_send_command(COMMAND_SOUND_CO))
    await asyncio.sleep(0)
    assert [call.args[0] for call in writer.write.call_args_list] == [b"9~"]

    bridge.async_process_line("CMD BUSY")
    assert bridge.last_error == "CMD BUSY"
    assert not queued.done()
    bridge.async_process_line("NETWORK PAIRED")
    await queued
    assert [call.args[0] for call in writer.write.call_args_list] == [b"9~", b"1~"]


async def test_v2_commands_wait_for_pairing_and_busy_is_correlated(
    hass: HomeAssistant,
) -> None:
    """Release queued V2 writes on completion and propagate correlated busy."""
    bridge = make_bridge(hass)
    writer = Mock()
    writer.drain = AsyncMock()
    bridge.connected, bridge._writer = True, writer
    bridge.async_process_line('{"type":"heartbeat"}')

    pairing = asyncio.create_task(bridge.async_send_command(COMMAND_PAIRING))
    await asyncio.sleep(0)
    bridge.async_process_line('{"type":"command_result","id":0,"result":"accepted"}')
    await pairing
    queued = asyncio.create_task(bridge.async_send_command(COMMAND_SOUND_CO))
    await asyncio.sleep(0)
    assert len(writer.write.call_args_list) == 1

    bridge.async_process_line('{"type":"command_result","id":0,"result":"paired"}')
    await asyncio.sleep(0)
    assert writer.write.call_args_list[-1].args[0] == (
        b'{"command":"sound_co","id":1}\n'
    )
    bridge.async_process_line('{"type":"error","id":1,"code":"busy"}')
    with pytest.raises(SerialException, match="busy"):
        await queued
    assert bridge.last_error == "busy"
    assert bridge.last_message_summary == "Error · busy"


def test_activity_availability_uses_75_second_timeout(hass: HomeAssistant) -> None:
    """Availability follows all recognized activity, not heartbeat age alone."""
    bridge = make_bridge(hass)
    activity = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    bridge.connected = True
    bridge.last_activity = activity

    with patch(
        "custom_components.fireangel_pro_connected.bridge.dt_util.utcnow",
        side_effect=[
            activity + timedelta(seconds=74),
            activity + timedelta(seconds=76),
        ],
    ):
        assert bridge.activity_available
        assert not bridge.activity_available


@pytest.mark.parametrize("result", ["accepted", "timeout"])
async def test_v2_normal_command_terminal_results(
    hass: HomeAssistant, result: str
) -> None:
    """Complete normal commands immediately for every documented result."""
    bridge = make_bridge(hass)
    writer = Mock(drain=AsyncMock())
    bridge.connected, bridge._writer = True, writer
    bridge.async_process_line('{"type":"heartbeat"}')

    command = asyncio.create_task(bridge.async_send_command(COMMAND_SOUND_FIRE))
    await asyncio.sleep(0)
    bridge.async_process_line(
        f'{{"type":"command_result","id":0,"command":"sound_fire","result":"{result}"}}'
    )

    if result == "timeout":
        with pytest.raises(SerialException, match="timed out"):
            await command
    else:
        assert (await command)["result"] == "accepted"


@pytest.mark.parametrize("result", ["paired", "unpaired", "timeout"])
async def test_v2_pairing_state_terminal_results(
    hass: HomeAssistant, result: str
) -> None:
    """Complete pairing-state queries for every documented terminal result."""
    bridge = make_bridge(hass)
    writer = Mock(drain=AsyncMock())
    bridge.connected, bridge._writer = True, writer
    bridge.async_process_line('{"type":"heartbeat"}')

    command = asyncio.create_task(bridge.async_send_command(COMMAND_PAIRING_STATE))
    await asyncio.sleep(0)
    bridge.async_process_line(
        f'{{"type":"command_result","id":0,"command":"pairing_state",'
        f'"result":"{result}"}}'
    )

    if result == "timeout":
        with pytest.raises(SerialException, match="timed out"):
            await command
    else:
        assert (await command)["result"] == result


@pytest.mark.parametrize(
    ("initial", "final"),
    [
        ("accepted", "paired"),
        ("accepted", "unpaired"),
        ("already_paired", None),
        ("timeout", None),
    ],
)
async def test_v2_pairing_terminal_results_release_queued_command(
    hass: HomeAssistant, initial: str, final: str | None
) -> None:
    """Never leave management commands blocked behind terminal pairing results."""
    bridge = make_bridge(hass)
    writer = Mock(drain=AsyncMock())
    bridge.connected, bridge._writer = True, writer
    bridge.async_process_line('{"type":"heartbeat"}')

    pairing = asyncio.create_task(bridge.async_send_command(COMMAND_PAIRING))
    await asyncio.sleep(0)
    queued = asyncio.create_task(bridge.async_send_command(COMMAND_SOUND_CO))
    await asyncio.sleep(0)
    bridge.async_process_line(
        f'{{"type":"command_result","id":0,"command":"pairing","result":"{initial}"}}'
    )
    if initial == "timeout":
        with pytest.raises(SerialException, match="timed out"):
            await pairing
    else:
        assert (await pairing)["result"] == initial

    if final is not None:
        assert len(writer.write.call_args_list) == 1
        assert bridge._cancel_pairing_watchdog is not None
        bridge.async_process_line(
            f'{{"type":"command_result","id":0,"command":"pairing","result":"{final}"}}'
        )
    await asyncio.sleep(0)
    assert writer.write.call_args_list[-1].args[0] == b'{"command":"sound_co","id":1}\n'
    bridge.async_process_line(
        '{"type":"command_result","id":1,"command":"sound_co","result":"accepted"}'
    )
    await queued
    assert bridge._pairing_finished.is_set()
    assert bridge._cancel_pairing_watchdog is None
    if final is not None:
        assert bridge.last_error is None


def test_v2_event_result_lifecycle(hass: HomeAssistant) -> None:
    """Keep test results associated only with their test event."""
    bridge = make_bridge(hass)
    bridge.async_process_line(
        '{"type":"event","device":"A1B2C3","event":"FIRE_TEST",'
        '"result":"PASS","base":"ON","battery":"OK","raw_status":1}'
    )
    state = bridge.devices["A1B2C3"]
    test_time = state.last_test_pass

    bridge.async_process_line(
        '{"type":"event","device":"A1B2C3","event":"STATUS",'
        '"base":"OFF","battery":"LOW","raw_status":71}'
    )
    assert (state.event, state.result, state.last_test_pass) == (
        "FIRE TEST",
        "PASS",
        test_time,
    )

    for event in ("FIRE_EMERGENCY", "SILENCE", "MISSING"):
        test_time = state.last_test_pass
        bridge.async_process_line(
            f'{{"type":"event","device":"A1B2C3","event":"{event}","raw_status":0}}'
        )
        assert state.result is None
        assert state.last_test_pass == test_time
        bridge.async_process_line(
            '{"type":"event","device":"A1B2C3","event":"FIRE_TEST",'
            '"result":"PASS","raw_status":1}'
        )


async def test_correlated_pairing_error_releases_queued_command(
    hass: HomeAssistant,
) -> None:
    """Release pairing serialization when firmware sends a correlated error."""
    bridge = make_bridge(hass)
    writer = Mock(drain=AsyncMock())
    bridge.connected, bridge._writer = True, writer
    bridge.async_process_line('{"type":"heartbeat"}')
    pairing = asyncio.create_task(bridge.async_send_command(COMMAND_PAIRING))
    await asyncio.sleep(0)
    queued = asyncio.create_task(bridge.async_send_command(COMMAND_SOUND_CO))
    await asyncio.sleep(0)

    bridge.async_process_line(
        '{"type":"command_result","id":0,"command":"pairing","result":"accepted"}'
    )
    await pairing
    assert bridge._cancel_pairing_watchdog is not None
    bridge.async_process_line('{"type":"error","id":0,"code":"pairing_state_timeout"}')

    await asyncio.sleep(0)
    assert writer.write.call_args_list[-1].args[0] == b'{"command":"sound_co","id":1}\n'
    bridge.async_process_line('{"type":"command_result","id":1,"result":"accepted"}')
    await queued
    assert bridge._pairing_finished.is_set()
    assert bridge._cancel_pairing_watchdog is None


async def test_pairing_watchdog_releases_queued_command(hass: HomeAssistant) -> None:
    """Release serialization if an accepted pairing has no terminal result."""
    bridge = make_bridge(hass)
    writer = Mock(drain=AsyncMock())
    bridge.connected, bridge._writer = True, writer
    bridge.protocol_mode = ProtocolMode.V2
    cancel_watchdog = Mock()

    with patch(
        "custom_components.fireangel_pro_connected.bridge.async_call_later",
        return_value=cancel_watchdog,
    ) as schedule:
        pairing = asyncio.create_task(bridge.async_send_command(COMMAND_PAIRING))
        await asyncio.sleep(0)
        queued = asyncio.create_task(bridge.async_send_command(COMMAND_SOUND_CO))
        await asyncio.sleep(0)
        bridge._process_command_result(
            {"type": "command_result", "id": 0, "result": "accepted"}
        )
        await pairing
        assert schedule.call_args.args[1] == 35
        assert not queued.done()

        bridge._pairing_watchdog_expired(datetime.now(UTC))

    await asyncio.sleep(0)
    assert bridge.last_error == "Pairing terminal result was not received"
    assert bridge._pairing_finished.is_set()
    assert bridge._cancel_pairing_watchdog is None
    assert writer.write.call_args_list[-1].args[0] == b'{"command":"sound_co","id":1}\n'
    bridge._process_command_result({"id": 1, "result": "accepted"})
    await queued


async def test_disconnect_cancels_pairing_watchdog(hass: HomeAssistant) -> None:
    """Clear accepted pairing state when the serial connection closes."""
    bridge = make_bridge(hass)
    writer = Mock(drain=AsyncMock())
    bridge.connected, bridge._writer = True, writer
    bridge.protocol_mode = ProtocolMode.V2
    cancel_watchdog = Mock()

    with patch(
        "custom_components.fireangel_pro_connected.bridge.async_call_later",
        return_value=cancel_watchdog,
    ):
        pairing = asyncio.create_task(bridge.async_send_command(COMMAND_PAIRING))
        await asyncio.sleep(0)
        bridge._process_command_result({"id": 0, "result": "accepted"})
        await pairing
        bridge._close_writer()

    cancel_watchdog.assert_called_once_with()
    assert bridge._pairing_finished.is_set()
    assert bridge._pairing_request_id is None
    assert bridge._cancel_pairing_watchdog is None
    writer.close.assert_called_once_with()


def test_future_v2_event_records_activity_without_state_change(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Treat future event enums as valid traffic without guessing semantics."""
    bridge = make_bridge(hass)
    bridge.async_process_line(
        '{"type":"event","device":"A1B2C3","event":"FIRE_EMERGENCY"}'
    )
    previous_event = bridge.devices["A1B2C3"].event
    previous_activity = bridge.last_activity

    bridge.async_process_line(
        '{"type":"event","device":"A1B2C3","event":"END_OF_LIFE","raw_status":7}'
    )

    assert bridge.protocol_mode == ProtocolMode.V2
    assert bridge.last_activity is not None
    assert bridge.last_activity >= previous_activity
    assert bridge.devices["A1B2C3"].event == previous_event
    assert not [record for record in caplog.records if record.levelno >= 30]


def test_literal_v2_protocol_contract_messages(hass: HomeAssistant) -> None:
    """Parse representative wire messages copied from the V2 specification."""
    bridge = make_bridge(hass)
    messages = (
        '{"type":"bridge","event":"startup","firmware":"2.0.0","protocol":2,"radio":"ready"}',
        '{"type":"heartbeat","uptime":123456,"radio":"ready"}',
        '{"type":"status","id":17,"firmware":"2.0.0","protocol":2,"uptime":123456,"radio":"ready","diagnostics":{"overflow":0,"malformed":0,"incomplete":0,"unknown":0,"command_timeout":0,"command_retry":0,"radio_reinit":0}}',
        '{"type":"event","device":"92BF1A","model":"ED08","event":"FIRE_TEST","result":"PASS","base":"ON","battery":"OK","raw_status":1}',
        '{"type":"event","device":"92BF1A","model":"7803","event":"CO_TEST","result":"FAIL","base":"ON","raw_status":0}',
        '{"type":"event","device":"92BF1A","model":"ED08","event":"STATUS","base":"ON","battery":"LOW","raw_status":71}',
        '{"type":"event","device":"92BF1A","event":"FIRE_EMERGENCY","base":"ON","raw_status":0}',
        '{"type":"event","device":"92BF1A","event":"CO_EMERGENCY","base":"ON","raw_status":0}',
        '{"type":"event","device":"92BF1A","event":"SILENCE","base":"ON","raw_status":1}',
        '{"type":"event","device":"92BF1A","event":"MISSING","base":"MISSING","battery":"MISSING","raw_status":0}',
        '{"type":"command_result","id":17,"command":"sound_fire","result":"accepted"}',
        '{"type":"command_result","id":17,"command":"sound_fire","result":"timeout"}',
        '{"type":"command_result","id":17,"command":"pairing","result":"already_paired"}',
        '{"type":"error","id":17,"code":"unknown_command"}',
    )
    for message in messages:
        bridge.async_process_line(message)

    assert bridge.protocol_mode == ProtocolMode.V2
    assert bridge.diagnostic_counters == {
        "overflow": 0,
        "malformed": 0,
        "incomplete": 0,
        "unknown": 0,
        "command_timeout": 0,
        "command_retry": 0,
        "radio_reinit": 0,
    }
    assert bridge.last_error == "unknown_command"


def test_missing_raw_frame_is_retained_and_validated(hass: HomeAssistant) -> None:
    """Preserve valid MISSING frame evidence without filtering the bridge ID."""
    bridge = make_bridge(hass)
    raw_frame = "d22a384100efa5b813000009407e"

    bridge.async_process_line(
        '{"type":"event","device":"A5B813","event":"MISSING",'
        '"base":"MISSING","battery":"MISSING","raw_status":0,'
        f'"raw_frame":"{raw_frame}"}}'
    )

    state = bridge.devices["A5B813"]
    assert state.is_bridge_device
    assert state.event == "MISSING"
    assert state.last_raw_frame == raw_frame.upper()
    assert bridge._stored_status()["A5B813"]["last_raw_frame"] == raw_frame.upper()

    for invalid in ("ABC", "GG", "0xD2", ""):
        bridge.async_process_line(
            '{"type":"event","device":"A5B813","event":"MISSING",'
            f'"raw_frame":"{invalid}"}}'
        )
        assert state.last_raw_frame == raw_frame.upper()

    bridge.async_process_line(
        '{"type":"event","device":"A5B813","event":"SILENCE","raw_status":1}'
    )
    assert state.last_raw_frame == raw_frame.upper()


async def test_all_v2_command_bytes_match_protocol_contract(
    hass: HomeAssistant,
) -> None:
    """Keep every supported host command compact and free of an inbound type."""
    bridge = make_bridge(hass)
    writer = Mock(drain=AsyncMock())
    bridge.connected, bridge._writer = True, writer
    bridge.async_process_line('{"type":"heartbeat"}')
    commands = (
        COMMAND_SOUND_CO,
        COMMAND_SOUND_FIRE,
        COMMAND_SOUND_COMBINED,
        COMMAND_SILENCE_CO,
        COMMAND_SILENCE_FIRE,
        COMMAND_PAIRING_STATE,
        COMMAND_PAIRING,
    )

    for request_id, command_name in enumerate(commands):
        task = asyncio.create_task(bridge.async_send_command(command_name))
        await asyncio.sleep(0)
        expected = f'{{"command":"{command_name}","id":{request_id}}}\n'.encode()
        assert writer.write.call_args_list[-1].args[0] == expected
        result = "paired" if command_name == COMMAND_PAIRING_STATE else "accepted"
        bridge.async_process_line(
            f'{{"type":"command_result","id":{request_id},'
            f'"command":"{command_name}","result":"{result}"}}'
        )
        await task
        if command_name == COMMAND_PAIRING:
            bridge.async_process_line(
                f'{{"type":"command_result","id":{request_id},'
                '"command":"pairing","result":"paired"}'
            )
