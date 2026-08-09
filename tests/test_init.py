"""Tests for FireAngel Pro Connected setup."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fireangel_pro_connected.const import (
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_PORT,
    DOMAIN,
)


async def test_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """Test setting up and unloading a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="/dev/ttyUSB0",
        data={CONF_PORT: "/dev/ttyUSB0"},
        options={CONF_DEVICES: [{CONF_DEVICE_ID: "A1B2C3"}]},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.fireangel_pro_connected.FireAngelBridge.async_start",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.fireangel_pro_connected.FireAngelBridge.async_stop",
            new=AsyncMock(),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        registry = er.async_get(hass)
        assert registry.async_get_entity_id("sensor", DOMAIN, "fireangel_event_a1b2c3")
        assert registry.async_get_entity_id("sensor", DOMAIN, "fireangel_model_a1b2c3")

        entry.runtime_data.async_process_line(
            '{"device":"C0FFEE", "model":"1103", "event":"FIRE TEST", "result":"PASS"}'
        )
        await hass.async_block_till_done()
        assert registry.async_get_entity_id("sensor", DOMAIN, "fireangel_event_c0ffee")
        assert registry.async_get_entity_id("sensor", DOMAIN, "fireangel_model_c0ffee")
        assert registry.async_get_entity_id(
            "binary_sensor", DOMAIN, "fireangel_alarm_c0ffee"
        )

        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_unload_failure(hass: HomeAssistant) -> None:
    """Test that a failed platform unload leaves the bridge running."""
    from custom_components.fireangel_pro_connected import async_unload_entry
    from custom_components.fireangel_pro_connected.bridge import FireAngelBridge

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_PORT: "/dev/ttyUSB0"})
    entry.add_to_hass(hass)
    bridge = FireAngelBridge(hass, entry)
    bridge.async_stop = AsyncMock()
    entry.runtime_data = bridge
    with patch.object(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=False)
    ):
        assert not await async_unload_entry(hass, entry)
    bridge.async_stop.assert_not_awaited()
