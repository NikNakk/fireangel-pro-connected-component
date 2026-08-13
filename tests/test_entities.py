"""Tests for FireAngel Pro Connected entities."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fireangel_pro_connected.binary_sensor import (
    FireAngelAlarmSensor,
    FireAngelBaseSensor,
    FireAngelBatterySensor,
    FireAngelBridgeActivitySensor,
    FireAngelBridgeConnectionSensor,
    _detector_entities,
    async_setup_entry,
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
    DEVICE_TYPE_SMOKE,
    DOMAIN,
    ProtocolMode,
)
from custom_components.fireangel_pro_connected.sensor import (
    FireAngelBridgeMessageSensor,
    FireAngelEventSensor,
    FireAngelLastTestPassSensor,
    FireAngelModelCodeSensor,
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
    activity = FireAngelBridgeActivitySensor(entry)
    message = FireAngelBridgeMessageSensor(entry)
    assert connection.available and activity.available
    assert not connection.is_on and not activity.is_on
    assert message.native_value is None
    bridge.connected, bridge.last_message = True, "READY"
    bridge.last_message_summary = "Bridge ready"
    bridge.last_activity = datetime.now(UTC)
    assert connection.is_on and activity.is_on
    assert message.available and message.native_value == "Bridge ready"
    assert message.extra_state_attributes == {"raw_message": "READY"}
    assert not message.entity_registry_enabled_default

    message.hass = hass
    message.async_write_ha_state = Mock()
    await message.async_added_to_hass()
    bridge._notify_update()

    message.async_write_ha_state.assert_called_once_with()

    button = FireAngelCommandButton(entry, BUTTONS[0])
    bridge.last_activity = None
    assert not button.available
    bridge.protocol_mode = ProtocolMode.LEGACY
    bridge.last_activity = datetime.now(UTC)
    assert button.available
    bridge.async_send_command = AsyncMock()
    await button.async_press()
    bridge.async_send_command.assert_awaited_once_with(BUTTONS[0].command)

    state = bridge.devices["A1B2C3"]
    alarm = FireAngelAlarmSensor(bridge, "A1B2C3")
    battery = FireAngelBatterySensor(bridge, "A1B2C3")
    base = FireAngelBaseSensor(bridge, "A1B2C3")
    event = FireAngelEventSensor(bridge, "A1B2C3")
    model_code = FireAngelModelCodeSensor(bridge, "A1B2C3")
    last_test = FireAngelLastTestPassSensor(bridge, "A1B2C3")
    assert alarm.is_on is battery.is_on is base.is_on is None
    assert model_code.native_value is None
    assert alarm.device_class is BinarySensorDeviceClass.SMOKE
    state.event, state.battery, state.base = "FIRE EMERGENCY", "LOW", "OFF"
    state.result, state.model = "PASS", "1103"
    assert alarm.is_on and battery.is_on and base.is_on
    assert event.native_value == "FIRE EMERGENCY"
    assert event.extra_state_attributes["result"] == "PASS"
    assert event.extra_state_attributes["last_raw_frame"] is None
    assert event.extra_state_attributes["last_raw_frame_at"] is None
    assert model_code.native_value == "1103"
    assert event.device_info["model"] == "WST-630"
    assert event.device_info["name"] == "FireAngel A1B2C3"
    assert last_test.native_value is None
    assert last_test.device_class is SensorDeviceClass.TIMESTAMP
    assert last_test.unique_id == "fireangel_last_test_pass_a1b2c3"
    state.last_test_pass = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)
    assert last_test.native_value == state.last_test_pass
    assert last_test.device_info == event.device_info
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


def test_bridge_module_entities_belong_to_bridge_device(hass: HomeAssistant) -> None:
    """Group the WiSafe2 interface entities with the serial bridge."""
    bridge, entry = make_bridge(hass)
    bridge.devices["A5B813"] = DetectorState("A5B813", model="C304", bridge_device=True)
    bridge_device_info = FireAngelBridgeMessageSensor(entry).device_info

    entities = (
        FireAngelAlarmSensor(bridge, "A5B813"),
        FireAngelEventSensor(bridge, "A5B813"),
        FireAngelLastTestPassSensor(bridge, "A5B813"),
        FireAngelModelCodeSensor(bridge, "A5B813"),
    )

    assert all(entity.device_info == bridge_device_info for entity in entities)
    assert all("a5b813" in entity.unique_id for entity in entities)


def test_detector_type_inference_and_bridge_entities(hass: HomeAssistant) -> None:
    """Infer known detector models and omit bridge-only status entities."""
    bridge, _entry = make_bridge(hass)
    bridge.devices["A1B2C3"] = DetectorState("A1B2C3", model="ED08")
    bridge.devices["C0FFEE"] = DetectorState("C0FFEE", model="7803")
    bridge.devices["D4E5F6"] = DetectorState("D4E5F6", device_type=DEVICE_TYPE_HEAT)
    bridge.devices["A5B813"] = DetectorState("A5B813", model="C304", bridge_device=True)
    bridge.devices["F0A1B2"] = DetectorState("F0A1B2", model="C304")
    bridge.devices["D0D0D0"] = DetectorState("D0D0D0", model="1104")

    assert (
        FireAngelAlarmSensor(bridge, "A1B2C3").device_class
        is BinarySensorDeviceClass.SMOKE
    )
    assert (
        FireAngelAlarmSensor(bridge, "C0FFEE").device_class
        is BinarySensorDeviceClass.CO
    )
    assert FireAngelEventSensor(bridge, "A1B2C3").icon == "mdi:smoke-detector"
    assert FireAngelEventSensor(bridge, "C0FFEE").icon == "mdi:molecule-co"
    assert FireAngelEventSensor(bridge, "D4E5F6").icon == "mdi:thermometer-alert"
    assert (
        FireAngelAlarmSensor(bridge, "D0D0D0").device_class
        is BinarySensorDeviceClass.HEAT
    )
    assert FireAngelEventSensor(bridge, "D0D0D0").device_info["model"] == "FP1720W2"
    bridge_entities = _detector_entities(bridge, "A5B813")
    assert [type(entity) for entity in bridge_entities] == [FireAngelAlarmSensor]
    assert bridge_entities[0].icon == "mdi:access-point-network"
    assert FireAngelEventSensor(bridge, "A5B813").icon == "mdi:access-point-network"
    assert bridge.devices["A5B813"].resolved_device_type == DEVICE_TYPE_BRIDGE
    assert bridge.devices["F0A1B2"].resolved_device_type == DEVICE_TYPE_SMOKE


def test_definitive_firmware_type_overrides_manual_type() -> None:
    """Prefer definitive bridge and CO evidence over a manual alarm type."""
    assert (
        DetectorState(
            "A1B2C3", model="7803", device_type=DEVICE_TYPE_HEAT
        ).resolved_device_type
        == DEVICE_TYPE_CO
    )
    assert (
        DetectorState(
            "C0FFEE",
            device_type=DEVICE_TYPE_SMOKE,
            event="CARBON MONOXIDE EMERGENCY",
        ).resolved_device_type
        == DEVICE_TYPE_CO
    )
    assert (
        DetectorState(
            "A5B813", model="C304", device_type=DEVICE_TYPE_SMOKE, bridge_device=True
        ).resolved_device_type
        == DEVICE_TYPE_BRIDGE
    )


async def test_remove_registered_bridge_diagnostics(hass: HomeAssistant) -> None:
    """Remove stale diagnostics after a partial message identifies the bridge."""
    bridge, _entry = make_bridge(hass)
    bridge.devices["A1B2C3"] = DetectorState("A1B2C3")
    bridge.devices["A5B813"] = DetectorState("A5B813", bridge_device=True)
    registry = er.async_get(hass)
    battery = registry.async_get_or_create(
        "binary_sensor", DOMAIN, "fireangel_battery_a1b2c3"
    )
    base = registry.async_get_or_create(
        "binary_sensor", DOMAIN, "fireangel_onbase_a1b2c3"
    )
    existing_bridge_battery = registry.async_get_or_create(
        "binary_sensor", DOMAIN, "fireangel_battery_a5b813"
    )
    existing_bridge_base = registry.async_get_or_create(
        "binary_sensor", DOMAIN, "fireangel_onbase_a5b813"
    )

    await async_setup_entry(hass, _entry, Mock())
    assert registry.async_get(battery.entity_id) is not None
    assert registry.async_get(base.entity_id) is not None
    assert registry.async_get(existing_bridge_battery.entity_id) is None
    assert registry.async_get(existing_bridge_base.entity_id) is None

    bridge.async_process_line('{"device":"A5B813", "model":"C304"}')
    assert registry.async_get(battery.entity_id) is not None
    assert registry.async_get(base.entity_id) is not None


async def test_remove_bridge_diagnostics_only_when_discovered(
    hass: HomeAssistant,
) -> None:
    """Remove stale diagnostics once when the bridge device is discovered."""
    bridge, entry = make_bridge(hass)
    registry = er.async_get(hass)
    await async_setup_entry(hass, entry, Mock())

    stale_battery = registry.async_get_or_create(
        "binary_sensor", DOMAIN, "fireangel_battery_a5b813"
    )
    stale_base = registry.async_get_or_create(
        "binary_sensor", DOMAIN, "fireangel_onbase_a5b813"
    )
    bridge.async_process_line('{"device":"A5B813", "model":"C304"}')
    assert registry.async_get(stale_battery.entity_id) is None
    assert registry.async_get(stale_base.entity_id) is None

    battery = registry.async_get_or_create(
        "binary_sensor", DOMAIN, "fireangel_battery_a5b813"
    )
    base = registry.async_get_or_create(
        "binary_sensor", DOMAIN, "fireangel_onbase_a5b813"
    )
    bridge.async_process_line('{"device":"A1B2C3", "battery":"OK"}')

    assert registry.async_get(battery.entity_id) is not None
    assert registry.async_get(base.entity_id) is not None
