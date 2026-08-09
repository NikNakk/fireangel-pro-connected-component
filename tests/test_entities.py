"""Tests for FireAngel Pro Connected entities."""

from unittest.mock import AsyncMock, Mock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fireangel_pro_connected.binary_sensor import (
    FireAngelAlarmSensor,
    FireAngelBaseSensor,
    FireAngelBatterySensor,
    FireAngelBridgeConnectionSensor,
    _detector_entities,
)
from custom_components.fireangel_pro_connected.bridge import (
    DetectorState,
    FireAngelBridge,
)
from custom_components.fireangel_pro_connected.button import (
    BUTTONS,
    FireAngelCommandButton,
)
from custom_components.fireangel_pro_connected.const import (
    CONF_PORT,
    DEVICE_TYPE_BRIDGE,
    DEVICE_TYPE_CO,
    DEVICE_TYPE_HEAT,
    DOMAIN,
)
from custom_components.fireangel_pro_connected.sensor import (
    FireAngelBridgeMessageSensor,
    FireAngelEventSensor,
)


def make_bridge(hass: HomeAssistant) -> tuple[FireAngelBridge, MockConfigEntry]:
    """Create a bridge and config entry without opening hardware."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_PORT: "/dev/ttyUSB0"})
    entry.add_to_hass(hass)
    bridge = FireAngelBridge(hass, entry)
    entry.runtime_data = bridge
    return bridge, entry


async def test_entity_properties_and_commands(hass: HomeAssistant) -> None:
    bridge, entry = make_bridge(hass)
    bridge.devices["A1B2C3"] = DetectorState("A1B2C3")
    connection = FireAngelBridgeConnectionSensor(entry)
    message = FireAngelBridgeMessageSensor(entry)
    assert connection.available and not connection.is_on
    assert message.native_value is None
    bridge.connected, bridge.last_message = True, "READY"
    assert connection.is_on and message.available and message.native_value == "READY"

    message.hass = hass
    message.async_write_ha_state = Mock()
    await message.async_added_to_hass()
    bridge._notify_update()

    message.async_write_ha_state.assert_called_once_with()

    bridge.async_send_command = AsyncMock()
    await FireAngelCommandButton(entry, BUTTONS[0]).async_press()
    bridge.async_send_command.assert_awaited_once_with(BUTTONS[0].command)

    state = bridge.devices["A1B2C3"]
    alarm = FireAngelAlarmSensor(bridge, "A1B2C3")
    battery = FireAngelBatterySensor(bridge, "A1B2C3")
    base = FireAngelBaseSensor(bridge, "A1B2C3")
    event = FireAngelEventSensor(bridge, "A1B2C3")
    assert alarm.is_on is battery.is_on is base.is_on is None
    assert alarm.device_class is BinarySensorDeviceClass.SMOKE
    state.event, state.battery, state.base = "FIRE EMERGENCY", "LOW", "OFF"
    state.result, state.model = "PASS", "1103"
    assert alarm.is_on and battery.is_on and base.is_on
    assert event.native_value == "FIRE EMERGENCY"
    assert event.extra_state_attributes["result"] == "PASS"
    assert event.device_info["model"] == "WST-630"
    assert event.device_info["name"] == "FireAngel A1B2C3"
    state.name = "Kitchen Fireangel"
    assert event.device_info["name"] == "Kitchen Fireangel"
    state.event, state.battery, state.base = "CLEAR", "OK", "ON"
    assert not alarm.is_on and not battery.is_on and not base.is_on
    state.device_type = DEVICE_TYPE_HEAT
    assert alarm.device_class is BinarySensorDeviceClass.HEAT
    state.device_type = DEVICE_TYPE_CO
    assert alarm.device_class is BinarySensorDeviceClass.CO
    state.device_type, state.event = None, "CARBON MONOXIDE EMERGENCY"
    assert alarm.device_class is BinarySensorDeviceClass.CO
    state.event, state.model = "CLEAR", "7803"
    assert alarm.device_class is BinarySensorDeviceClass.CO
    event.hass = hass
    event.async_write_ha_state = Mock()
    await event.async_added_to_hass()
    bridge._notify_update()


def test_detector_type_inference_and_bridge_entities(hass: HomeAssistant) -> None:
    """Infer known detector models and omit bridge-only status entities."""
    bridge, _entry = make_bridge(hass)
    bridge.devices["A1B2C3"] = DetectorState("A1B2C3", model="ED08")
    bridge.devices["C0FFEE"] = DetectorState("C0FFEE", model="7803")
    bridge.devices["B1D6E0"] = DetectorState("B1D6E0", model="C304")

    assert (
        FireAngelAlarmSensor(bridge, "A1B2C3").device_class
        is BinarySensorDeviceClass.SMOKE
    )
    assert (
        FireAngelAlarmSensor(bridge, "C0FFEE").device_class
        is BinarySensorDeviceClass.CO
    )
    bridge_entities = _detector_entities(bridge, "B1D6E0")
    assert [type(entity) for entity in bridge_entities] == [FireAngelAlarmSensor]
    assert bridge.devices["B1D6E0"].device_type is None
    assert bridge.devices["B1D6E0"].resolved_device_type == DEVICE_TYPE_BRIDGE
