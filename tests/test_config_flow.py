"""Tests for the FireAngel Pro Connected config and options flows."""

from unittest.mock import Mock

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fireangel_pro_connected.const import (
    CONF_BAUD_RATE,
    CONF_DEVICE_ID,
    CONF_DEVICE_TYPE,
    CONF_DEVICES,
    CONF_MODEL,
    CONF_PORT,
    DEFAULT_BAUD_RATE,
    DEVICE_TYPE_HEAT,
    DOMAIN,
)

PORT = "/dev/serial/by-id/fireangel"


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test completing serial bridge setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PORT: PORT, CONF_BAUD_RATE: DEFAULT_BAUD_RATE},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "FireAngel Pro Connected"
    assert result["data"] == {
        CONF_PORT: PORT,
        CONF_BAUD_RATE: DEFAULT_BAUD_RATE,
    }


async def test_single_bridge_per_port(hass: HomeAssistant) -> None:
    """Test that a serial port can only be configured once."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=PORT, data={CONF_PORT: PORT})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PORT: PORT, CONF_BAUD_RATE: DEFAULT_BAUD_RATE},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_manually_add_detector(hass: HomeAssistant) -> None:
    """Test migration by adding an existing detector hex ID."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_PORT: PORT})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_device"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_ID: "a1:b2:c3",
            CONF_DEVICE_TYPE: DEVICE_TYPE_HEAT,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICES] == [
        {
            CONF_DEVICE_ID: "A1B2C3",
            CONF_DEVICE_TYPE: DEVICE_TYPE_HEAT,
        }
    ]


async def test_reject_invalid_detector_id(hass: HomeAssistant) -> None:
    """Test validating manually entered detector IDs."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_PORT: PORT})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_device"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: "not-hex"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_DEVICE_ID: "invalid_device_id"}


async def test_options_validation_and_loaded_add(hass: HomeAssistant) -> None:
    """Cover duplicate/model validation and live enrollment."""
    from homeassistant import config_entries
    from homeassistant.data_entry_flow import FlowResultType

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORT: "/dev/ttyUSB0"},
        options={CONF_DEVICES: [{CONF_DEVICE_ID: "A1B2C3"}]},
    )
    entry.add_to_hass(hass)
    for user_input, expected in (
        (
            {CONF_DEVICE_ID: "A1B2C3", CONF_DEVICE_TYPE: DEVICE_TYPE_HEAT},
            {CONF_DEVICE_ID: "already_configured"},
        ),
        (
            {
                CONF_DEVICE_ID: "C0FFEE",
                CONF_MODEL: "bad",
                CONF_DEVICE_TYPE: DEVICE_TYPE_HEAT,
            },
            {CONF_MODEL: "invalid_model"},
        ),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "add_device"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == expected

    bridge = Mock()
    entry.runtime_data = bridge
    entry.mock_state(hass, config_entries.ConfigEntryState.LOADED)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_device"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_DEVICE_ID: "C0FFEE", CONF_MODEL: "78:03", CONF_DEVICE_TYPE: "auto"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICES][-1] == {
        CONF_DEVICE_ID: "C0FFEE",
        CONF_MODEL: "7803",
    }
    bridge.async_add_manual_device.assert_called_once_with("C0FFEE", "7803", "auto")
