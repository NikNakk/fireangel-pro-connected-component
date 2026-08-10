"""Tests for FireAngel Pro Connected diagnostics."""

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
