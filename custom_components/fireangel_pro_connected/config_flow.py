"""Config flow for FireAngel Pro Connected."""

from __future__ import annotations

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
    CONF_MODEL,
    CONF_PORT,
    DEFAULT_BAUD_RATE,
    DEVICE_TYPE_AUTO,
    DEVICE_TYPES,
    DOMAIN,
)


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
        return self.async_show_menu(step_id="init", menu_options=["add_device"])

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
