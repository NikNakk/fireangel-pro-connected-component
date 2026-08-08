"""Tests for the WiSafe2 serial bridge protocol."""

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fireangel_pro_connected.bridge import FireAngelBridge
from custom_components.fireangel_pro_connected.const import (
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_PORT,
    DOMAIN,
)


def make_bridge(hass: HomeAssistant) -> FireAngelBridge:
    """Create a bridge without opening hardware."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_PORT: "/dev/ttyUSB0"})
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
