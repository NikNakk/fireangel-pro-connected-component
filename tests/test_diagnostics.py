"""Tests for FireAngel Pro Connected diagnostics."""

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fireangel_pro_connected.bridge import FireAngelBridge
from custom_components.fireangel_pro_connected.const import (
    CONF_BAUD_RATE,
    CONF_DEVICES,
    CONF_NAME,
    CONF_PORT,
)
from custom_components.fireangel_pro_connected.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_include_config_entry_data(hass: HomeAssistant) -> None:
    """Test diagnostics include the integration's configuration."""
    entry = MockConfigEntry(
        domain="fireangel_pro_connected",
        data={CONF_PORT: "/dev/ttyUSB0", CONF_BAUD_RATE: 115200},
        options={CONF_DEVICES: {"A1B2C3": {CONF_NAME: "Hallway"}}},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["data"] == entry.data
    assert diagnostics["entry"]["options"] == entry.options


async def test_diagnostics_include_runtime_protocol(hass: HomeAssistant) -> None:
    """Test detected firmware details are included in diagnostics."""
    entry = MockConfigEntry(
        domain="fireangel_pro_connected", data={CONF_PORT: "/dev/ttyUSB0"}
    )
    entry.add_to_hass(hass)
    entry.runtime_data = FireAngelBridge(hass, entry)
    entry.runtime_data.async_process_line(
        '{"type":"bridge","protocol":2,"firmware":"2.0.0","radio":"ready"}'
    )
    entry.runtime_data.async_process_line(
        '{"type":"event","device":"A5B813","event":"MISSING",'
        '"raw_frame":"D22A384100EFA5B813000009407E"}'
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["bridge"]["protocol_mode"] == "v2"
    assert diagnostics["bridge"]["protocol_version"] == 2
    assert diagnostics["bridge"]["firmware_version"] == "2.0.0"
    assert diagnostics["bridge"]["last_activity"] is not None
    assert diagnostics["bridge"]["last_message"].startswith('{"type":"event"')
    assert diagnostics["detectors"] == {
        "A5B813": {"last_raw_frame": "D22A384100EFA5B813000009407E"}
    }
