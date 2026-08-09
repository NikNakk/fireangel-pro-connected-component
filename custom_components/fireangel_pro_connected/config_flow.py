"""Config flow for FireAngel Pro Connected."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_BAUD_RATE,
    CONF_DEVICE_ID,
    CONF_DEVICE_TYPE,
    CONF_DEVICES,
    CONF_LEGACY_YAML,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    DEFAULT_BAUD_RATE,
    DEVICE_TYPE_AUTO,
    DEVICE_TYPE_CO,
    DEVICE_TYPE_HEAT,
    DEVICE_TYPE_SMOKE,
    DEVICE_TYPES,
    DOMAIN,
)

_LEGACY_UNIQUE_ID_PATTERN = re.compile(
    r"^\s*-\s+unique_id:\s*fireangel_(event|battery|onbase)_([0-9a-f]{6})\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_LEGACY_EVENT_BLOCK_PATTERN = re.compile(
    r"^\s*-\s+unique_id:\s*fireangel_event_([0-9a-f]{6})\s*$"
    r"(?P<body>.*?)(?=^\s*-\s+unique_id:|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
_LEGACY_NAME_PATTERN = re.compile(r"^\s*name:\s*(.+?)\s*$", re.MULTILINE)


def _legacy_detector_type(name: str) -> str:
    """Infer a detector type from a legacy entity name."""
    lowered = name.lower()
    if "carbon monoxide" in lowered or re.search(r"\bco\b", lowered):
        return DEVICE_TYPE_CO
    if "heat" in lowered:
        return DEVICE_TYPE_HEAT
    if "smoke" in lowered:
        return DEVICE_TYPE_SMOKE
    return DEVICE_TYPE_AUTO


def _legacy_detector_name(name: str) -> str | None:
    """Derive a detector device name from a legacy event entity name."""
    cleaned = re.sub(
        r"\s+(?:(?:carbon monoxide|co|smoke|heat)\s+)?event\s*$",
        "",
        name,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned or None


def _parse_legacy_package(value: str) -> list[dict[str, str]]:
    """Extract real detectors from the legacy package template entities."""
    entity_kinds: dict[str, set[str]] = {}
    for kind, raw_device_id in _LEGACY_UNIQUE_ID_PATTERN.findall(value):
        device_id = raw_device_id.upper()
        entity_kinds.setdefault(device_id, set()).add(kind.lower())

    event_names: dict[str, str] = {}
    for match in _LEGACY_EVENT_BLOCK_PATTERN.finditer(value):
        name_match = _LEGACY_NAME_PATTERN.search(match.group("body"))
        if name_match:
            event_names[match.group(1).upper()] = name_match.group(1).strip(" '\"")

    devices = []
    for device_id, kinds in entity_kinds.items():
        # The firmware pseudo-device only has an event entity. Actual alarms in
        # the legacy package have event, battery, and base-status entities.
        if kinds != {"event", "battery", "onbase"}:
            continue
        device = {CONF_DEVICE_ID: device_id}
        legacy_name = event_names.get(device_id, "")
        device_type = _legacy_detector_type(legacy_name)
        if device_type != DEVICE_TYPE_AUTO:
            device[CONF_DEVICE_TYPE] = device_type
        if device_name := _legacy_detector_name(legacy_name):
            device[CONF_NAME] = device_name
        devices.append(device)
    return devices


class FireAngelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FireAngel Pro Connected."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the Arduino serial connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            port = user_input[CONF_PORT].strip()
            await self.async_set_unique_id(port)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="FireAngel Pro Connected",
                data={
                    CONF_PORT: port,
                    CONF_BAUD_RATE: user_input[CONF_BAUD_RATE],
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_PORT): str,
                vol.Required(CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> FireAngelOptionsFlow:
        """Create the options flow."""
        return FireAngelOptionsFlow()


class FireAngelOptionsFlow(config_entries.OptionsFlow):
    """Handle detector enrollment options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the options menu."""
        return self.async_show_menu(
            step_id="init", menu_options=["add_device", "import_legacy_yaml"]
        )

    async def async_step_import_legacy_yaml(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Import detector inventory from the legacy package YAML."""
        errors: dict[str, str] = {}
        if user_input is not None:
            imported = _parse_legacy_package(user_input[CONF_LEGACY_YAML])
            if not imported:
                errors[CONF_LEGACY_YAML] = "no_devices_found"
            else:
                devices = list(self.config_entry.options.get(CONF_DEVICES, []))
                known = {item[CONF_DEVICE_ID] for item in devices}
                new_devices = [
                    device for device in imported if device[CONF_DEVICE_ID] not in known
                ]
                if not new_devices:
                    errors[CONF_LEGACY_YAML] = "all_devices_configured"
                else:
                    devices.extend(new_devices)
                    if self.config_entry.state is ConfigEntryState.LOADED:
                        bridge = self.config_entry.runtime_data
                        for device in new_devices:
                            bridge.async_add_manual_device(
                                device[CONF_DEVICE_ID],
                                None,
                                device.get(CONF_DEVICE_TYPE, DEVICE_TYPE_AUTO),
                                device.get(CONF_NAME),
                            )
                    return self.async_create_entry(
                        title="",
                        data={**self.config_entry.options, CONF_DEVICES: devices},
                    )

        return self.async_show_form(
            step_id="import_legacy_yaml",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LEGACY_YAML): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a detector by its printed hex ID."""
        errors: dict[str, str] = {}
        if user_input is not None:
            from .bridge import FireAngelBridge  # noqa: PLC0415

            device_id = FireAngelBridge.normalize_device_id(user_input[CONF_DEVICE_ID])
            model = FireAngelBridge.normalize_model(user_input.get(CONF_MODEL))
            device_type = user_input[CONF_DEVICE_TYPE]
            known = {
                item[CONF_DEVICE_ID]
                for item in self.config_entry.options.get(CONF_DEVICES, [])
            }
            if device_id is None:
                errors[CONF_DEVICE_ID] = "invalid_device_id"
            elif device_id in known:
                errors[CONF_DEVICE_ID] = "already_configured"
            elif user_input.get(CONF_MODEL) and model is None:
                errors[CONF_MODEL] = "invalid_model"
            else:
                devices = list(self.config_entry.options.get(CONF_DEVICES, []))
                device = {CONF_DEVICE_ID: device_id}
                if model is not None:
                    device[CONF_MODEL] = model
                if device_type != DEVICE_TYPE_AUTO:
                    device[CONF_DEVICE_TYPE] = device_type
                devices.append(device)
                if self.config_entry.state is ConfigEntryState.LOADED:
                    bridge = self.config_entry.runtime_data
                    bridge.async_add_manual_device(device_id, model, device_type)
                return self.async_create_entry(
                    title="",
                    data={**self.config_entry.options, CONF_DEVICES: devices},
                )

        return self.async_show_form(
            step_id="add_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): str,
                    vol.Optional(CONF_MODEL): str,
                    vol.Required(
                        CONF_DEVICE_TYPE, default=DEVICE_TYPE_AUTO
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(DEVICE_TYPES),
                            translation_key="device_type",
                        )
                    ),
                }
            ),
            errors=errors,
        )
