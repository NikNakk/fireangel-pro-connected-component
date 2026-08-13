"""Tests for FireAngel Pro Connected setup."""

from unittest.mock import AsyncMock, Mock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fireangel_pro_connected import (
    _async_remove_orphaned_bridge_module_device,
)
from custom_components.fireangel_pro_connected.bridge import FireAngelBridge
from custom_components.fireangel_pro_connected.const import (
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_PORT,
    DEFAULT_BRIDGE_DEVICE_ID,
    DOMAIN,
)


async def test_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """Test setting up and unloading a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="/dev/ttyUSB0",
        data={CONF_PORT: "/dev/ttyUSB0"},
        options={
            CONF_DEVICES: [
                {CONF_DEVICE_ID: "A1B2C3"},
                {CONF_DEVICE_ID: DEFAULT_BRIDGE_DEVICE_ID},
            ]
        },
    )
    entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    old_module_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DEFAULT_BRIDGE_DEVICE_ID)},
    )
    for platform, unique_id in (
        ("binary_sensor", "fireangel_alarm_a5b813"),
        ("sensor", "fireangel_event_a5b813"),
        ("sensor", "fireangel_last_test_pass_a5b813"),
        ("sensor", "fireangel_model_a5b813"),
    ):
        entity_registry.async_get_or_create(
            platform, DOMAIN, unique_id, device_id=old_module_device.id
        )

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
        device_registry = dr.async_get(hass)
        bridge_device = device_registry.async_get_device(
            identifiers={(DOMAIN, entry.entry_id)}
        )
        assert bridge_device is not None
        assert (
            device_registry.async_get_device(
                identifiers={(DOMAIN, DEFAULT_BRIDGE_DEVICE_ID)}
            )
            is None
        )
        for platform, unique_id in (
            ("binary_sensor", "fireangel_alarm_a5b813"),
            ("sensor", "fireangel_event_a5b813"),
            ("sensor", "fireangel_last_test_pass_a5b813"),
            ("sensor", "fireangel_model_a5b813"),
        ):
            entity_id = registry.async_get_entity_id(platform, DOMAIN, unique_id)
            assert entity_id is not None
            assert registry.async_get(entity_id).device_id == bridge_device.id

        assert registry.async_get_entity_id("sensor", DOMAIN, "fireangel_event_a1b2c3")
        assert registry.async_get_entity_id("sensor", DOMAIN, "fireangel_model_a1b2c3")
        assert registry.async_get_entity_id(
            "sensor", DOMAIN, "fireangel_last_test_pass_a1b2c3"
        )
        assert registry.async_get_entity_id(
            "update", DOMAIN, f"{entry.entry_id}_firmware"
        )

        entry.runtime_data.async_process_line(
            '{"device":"C0FFEE", "model":"1103", "event":"FIRE TEST", "result":"PASS"}'
        )
        await hass.async_block_till_done()
        assert registry.async_get_entity_id("sensor", DOMAIN, "fireangel_event_c0ffee")
        assert registry.async_get_entity_id("sensor", DOMAIN, "fireangel_model_c0ffee")
        assert registry.async_get_entity_id(
            "sensor", DOMAIN, "fireangel_last_test_pass_c0ffee"
        )
        assert registry.async_get_entity_id(
            "binary_sensor", DOMAIN, "fireangel_alarm_c0ffee"
        )

        detector_device = device_registry.async_get_device(
            identifiers={(DOMAIN, "A1B2C3")}
        )
        assert detector_device is not None
        assert detector_device.model is None
        entry.runtime_data.async_process_line('{"device":"A1B2C3", "model":"ED08"}')
        detector_device = device_registry.async_get_device(
            identifiers={(DOMAIN, "A1B2C3")}
        )
        assert detector_device is not None
        assert detector_device.model == "FP2620W2"

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


def test_orphaned_bridge_module_cleanup_guards(hass: HomeAssistant) -> None:
    """Keep module devices that are absent, in use, or lack a bridge parent."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_PORT: "/dev/ttyUSB0"})
    entry.add_to_hass(hass)
    bridge = FireAngelBridge(hass, entry)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    _async_remove_orphaned_bridge_module_device(hass, entry, bridge)

    module_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DEFAULT_BRIDGE_DEVICE_ID)},
    )
    entity_registry.async_get_or_create(
        "sensor", DOMAIN, "module_in_use", device_id=module_device.id
    )
    _async_remove_orphaned_bridge_module_device(hass, entry, bridge)
    assert device_registry.async_get(module_device.id) is not None


def test_orphaned_module_without_registered_bridge_is_retained(
    hass: HomeAssistant,
) -> None:
    """Retain an orphan until the replacement bridge device is registered."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_PORT: "/dev/ttyUSB0"})
    bridge = FireAngelBridge(hass, entry)
    module_device = Mock(id="module-device")
    device_registry = Mock()
    device_registry.async_get_device.side_effect = [module_device, None]

    with (
        patch(
            "custom_components.fireangel_pro_connected.dr.async_get",
            return_value=device_registry,
        ),
        patch("custom_components.fireangel_pro_connected.er.async_get"),
        patch(
            "custom_components.fireangel_pro_connected.er.async_entries_for_device",
            return_value=[],
        ),
    ):
        _async_remove_orphaned_bridge_module_device(hass, entry, bridge)

    device_registry.async_remove_device.assert_not_called()
