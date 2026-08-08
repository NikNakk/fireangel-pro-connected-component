"""Tests for FireAngel Pro Connected diagnostics."""

from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fireangel_pro_connected.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_redact_credentials(hass: HomeAssistant) -> None:
    """Test that diagnostics do not expose credentials."""
    entry = MockConfigEntry(
        domain="fireangel_pro_connected",
        data={CONF_USERNAME: "person@example.com", CONF_PASSWORD: "secret"},
        options={CONF_TOKEN: "token"},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["data"] == {
        CONF_USERNAME: "person@example.com",
        CONF_PASSWORD: "**REDACTED**",
    }
    assert diagnostics["entry"]["options"] == {CONF_TOKEN: "**REDACTED**"}

