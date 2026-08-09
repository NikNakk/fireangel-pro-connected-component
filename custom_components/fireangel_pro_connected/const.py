"""Constants for the FireAngel Pro Connected integration."""

from typing import Final

DOMAIN: Final = "fireangel_pro_connected"

CONF_BAUD_RATE: Final = "baud_rate"
CONF_DEVICE_ID: Final = "device_id"
CONF_DEVICES: Final = "devices"
CONF_DEVICE_TYPE: Final = "device_type"
CONF_LEGACY_YAML: Final = "legacy_yaml"
CONF_MODEL: Final = "model"
CONF_NAME: Final = "name"
CONF_PORT: Final = "port"

DEFAULT_BAUD_RATE: Final = 115200

DEVICE_TYPE_AUTO: Final = "auto"
DEVICE_TYPE_BRIDGE: Final = "bridge"
DEVICE_TYPE_CO: Final = "carbon_monoxide"
DEVICE_TYPE_HEAT: Final = "heat"
DEVICE_TYPE_SMOKE: Final = "smoke"
DEVICE_TYPES: Final = (
    DEVICE_TYPE_AUTO,
    DEVICE_TYPE_SMOKE,
    DEVICE_TYPE_HEAT,
    DEVICE_TYPE_CO,
)

COMMAND_TEST_CO: Final = b"1~"
COMMAND_TEST_FIRE: Final = b"2~"
COMMAND_TEST_ALL: Final = b"3~"
COMMAND_SILENCE_CO: Final = b"6~"
COMMAND_SILENCE_FIRE: Final = b"7~"
COMMAND_GET_PAIRING: Final = b"8~"
COMMAND_START_PAIRING: Final = b"9~"

MODEL_NAMES: Final = {
    "ED08": "FP2620W2",
    "1103": "WST-630",
    "7803": "W2-CO-10X",
    "C304": "W2-SVP-630",
}

# The W2-SVP-630 is the WiSafe2 interface used by the Arduino bridge rather
# than an alarm. The other mappings are safe detector-type inferences; heat
# alarms remain user-configurable because the firmware reports smoke and heat
# alike as FIRE.
MODEL_DEVICE_TYPES: Final = {
    "ED08": DEVICE_TYPE_SMOKE,
    "1103": DEVICE_TYPE_SMOKE,
    "7803": DEVICE_TYPE_CO,
    "C304": DEVICE_TYPE_BRIDGE,
}
