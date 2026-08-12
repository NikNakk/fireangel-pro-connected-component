"""Tests for serial maintenance lifecycle and service targeting."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fireangel_pro_connected import async_setup
from custom_components.fireangel_pro_connected.bridge import FireAngelBridge
from custom_components.fireangel_pro_connected.const import CONF_PORT, DOMAIN


def bridge_entry(hass: HomeAssistant, port: str = "/dev/ttyUSB0"):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_PORT: port}, title=port)
    entry.add_to_hass(hass)
    entry.runtime_data = FireAngelBridge(hass, entry)
    return entry


async def test_suspend_and_resume_serial_lifecycle(hass: HomeAssistant) -> None:
    """Suspension closes once, prevents reconnect, and resume is idempotent."""
    entry = bridge_entry(hass)
    bridge = entry.runtime_data
    writer = Mock()
    bridge._writer = writer
    bridge._reader = AsyncMock()
    bridge.connected = True
    bridge._task = hass.async_create_task(asyncio.sleep(60))

    await bridge.async_suspend_for_maintenance()
    assert bridge.maintenance_suspended
    assert not bridge.connected
    assert bridge._task is None
    writer.close.assert_called_once_with()
    await bridge.async_suspend_for_maintenance()
    writer.close.assert_called_once_with()

    with patch.object(bridge, "_async_connect", AsyncMock()) as connect:
        await bridge._async_read_forever()
    connect.assert_not_awaited()

    with patch.object(bridge, "_async_read_forever", AsyncMock()) as read_forever:
        await bridge.async_resume_from_maintenance()
        await bridge._task
        await bridge.async_resume_from_maintenance()
    assert not bridge.maintenance_suspended
    read_forever.assert_awaited_once()


async def test_unexpected_disconnect_reconnects_when_active(
    hass: HomeAssistant,
) -> None:
    """An ordinary serial failure retains the existing reconnect behavior."""
    bridge = bridge_entry(hass).runtime_data
    reader = AsyncMock()
    reader.readline.return_value = b""
    bridge._reader = reader

    async def stop_after_delay(delay: int) -> None:
        assert delay == 10
        raise asyncio.CancelledError

    with (
        patch.object(bridge, "_async_connect", AsyncMock()) as connect,
        patch(
            "custom_components.fireangel_pro_connected.bridge.asyncio.sleep",
            stop_after_delay,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await bridge._async_read_forever()
    connect.assert_not_awaited()
    assert bridge.last_error == "Serial connection closed"


async def test_maintenance_services_target_entries_safely(hass: HomeAssistant) -> None:
    """Services return port metadata and reject ambiguous entry selection."""
    await async_setup(hass, {})
    first = bridge_entry(hass, "/dev/ttyUSB0")
    response = await hass.services.async_call(
        DOMAIN, "maintenance_status", {}, blocking=True, return_response=True
    )
    assert response["serial_device"] == "/dev/ttyUSB0"

    second = bridge_entry(hass, "/dev/ttyUSB1")
    with pytest.raises(HomeAssistantError, match="multiple"):
        await hass.services.async_call(
            DOMAIN, "maintenance_status", {}, blocking=True, return_response=True
        )

    second.runtime_data.async_suspend_for_maintenance = AsyncMock()
    response = await hass.services.async_call(
        DOMAIN,
        "suspend_for_maintenance",
        {"config_entry_id": second.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response["config_entry_id"] == second.entry_id
    second.runtime_data.async_suspend_for_maintenance.assert_awaited_once()
    assert response["serial_device"] == "/dev/ttyUSB1"
    assert first.runtime_data.maintenance_suspended is False
