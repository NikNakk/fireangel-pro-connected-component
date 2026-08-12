"""Constants for the FireAngel Pro Connected integration."""

from enum import StrEnum
from typing import Final

DOMAIN: Final = "fireangel_pro_connected"

CONF_BAUD_RATE: Final = "baud_rate"
CONF_BRIDGE_DEVICE_ID: Final = "bridge_device_id"
CONF_DEVICE_ID: Final = "device_id"
CONF_DEVICES: Final = "devices"
CONF_DEVICE_TYPE: Final = "device_type"
CONF_LEGACY_YAML: Final = "legacy_yaml"
CONF_MODEL: Final = "model"
CONF_NAME: Final = "name"
CONF_PORT: Final = "port"

ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"

SERVICE_MAINTENANCE_STATUS: Final = "maintenance_status"
SERVICE_RESUME_AFTER_MAINTENANCE: Final = "resume_after_maintenance"
SERVICE_SUSPEND_FOR_MAINTENANCE: Final = "suspend_for_maintenance"

DEFAULT_BAUD_RATE: Final = 115200
DEFAULT_BRIDGE_DEVICE_ID: Final = "A5B813"

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


class ProtocolMode(StrEnum):
    """Wire protocol detected on the current serial connection."""

    UNKNOWN = "unknown"
    LEGACY = "legacy"
    V2 = "v2"


COMMAND_SOUND_CO: Final = "sound_co"
COMMAND_SOUND_FIRE: Final = "sound_fire"
COMMAND_SOUND_COMBINED: Final = "sound_combined"
COMMAND_SILENCE_CO: Final = "silence_co"
COMMAND_SILENCE_FIRE: Final = "silence_fire"
COMMAND_PAIRING_STATE: Final = "pairing_state"
COMMAND_PAIRING: Final = "pairing"

LEGACY_COMMANDS: Final = {
    COMMAND_SOUND_CO: b"1~",
    COMMAND_SOUND_FIRE: b"2~",
    COMMAND_SOUND_COMBINED: b"3~",
    COMMAND_SILENCE_CO: b"6~",
    COMMAND_SILENCE_FIRE: b"7~",
    COMMAND_PAIRING_STATE: b"8~",
    COMMAND_PAIRING: b"9~",
}

MODEL_NAMES: Final = {
    "ED08": "FP2620W2",
    "1104": "FP1720W2",
    "1103": "WST-630",
    "7803": "W2-CO-10X",
    "C304": "W2-SVP-630",
}

# These mappings are safe detector-type inferences; heat alarms remain
# user-configurable because the firmware reports smoke and heat alike as FIRE.
# Bridge identity is configured separately because its WiSafe2 module is
# harvested from another device and its model code does not identify its role.
MODEL_DEVICE_TYPES: Final = {
    "ED08": DEVICE_TYPE_SMOKE,
    "1104": DEVICE_TYPE_HEAT,
    "1103": DEVICE_TYPE_SMOKE,
    "7803": DEVICE_TYPE_CO,
}

DEVICE_TYPE_ICONS: Final = {
    DEVICE_TYPE_SMOKE: "mdi:smoke-detector",
    DEVICE_TYPE_HEAT: "mdi:thermometer-alert",
    DEVICE_TYPE_CO: "mdi:molecule-co",
    DEVICE_TYPE_BRIDGE: "mdi:access-point-network",
}
