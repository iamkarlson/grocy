"""Adds config flow for Grocy."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from grocy import Grocy

from .const import (
    CONF_API_KEY,
    CONF_CALENDAR_FIX_TIMEZONE,
    CONF_CALENDAR_SYNC_INTERVAL,
    CONF_PORT,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_CALENDAR_SYNC_INTERVAL,
    DEFAULT_PORT,
    DOMAIN,
    NAME,
)
from .helpers import extract_base_url_and_path

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Migrate old config entries."""
    version = config_entry.version
    if version == 1:
        # Migrate from version 1 to 2: add calendar_sync_interval with default
        new_data = {**config_entry.data}
        new_data[CONF_CALENDAR_SYNC_INTERVAL] = DEFAULT_CALENDAR_SYNC_INTERVAL
        new_data[CONF_CALENDAR_FIX_TIMEZONE] = True

        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)
        _LOGGER.info(
            "Migrated config entry from version %s to version %s",
            version,
            2,
        )
    return True


def _get_user_data_schema(
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    """Return the schema for user configuration form."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=defaults.get(CONF_URL, "")): str,
            vol.Required(CONF_API_KEY, default=defaults.get(CONF_API_KEY, "")): str,
            vol.Optional(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Optional(
                CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, False)
            ): bool,
            vol.Optional(
                CONF_CALENDAR_SYNC_INTERVAL,
                default=defaults.get(
                    CONF_CALENDAR_SYNC_INTERVAL, DEFAULT_CALENDAR_SYNC_INTERVAL
                ),
            ): int,
            vol.Optional(
                CONF_CALENDAR_FIX_TIMEZONE,
                default=defaults.get(CONF_CALENDAR_FIX_TIMEZONE, True),
            ): bool,
        }
    )


class GrocyFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Grocy."""

    VERSION = 2

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,  # noqa: ARG004
    ) -> GrocyOptionsFlowHandler:
        """Get the options flow for this handler."""
        return GrocyOptionsFlowHandler()

    def __init__(self) -> None:
        """Initialize."""
        self._errors: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        self._errors = {}
        _LOGGER.debug("Step user")

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            error = await self._test_credentials(
                user_input[CONF_URL],
                user_input[CONF_API_KEY],
                user_input[CONF_PORT],
                user_input[CONF_VERIFY_SSL],
            )
            _LOGGER.debug("Testing of credentials returned error: %s", error)

            if error is None:
                return self.async_create_entry(title=NAME, data=user_input)

            self._errors["base"] = error
            return self.async_show_form(
                step_id="user",
                data_schema=_get_user_data_schema(user_input),
                errors=self._errors,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_get_user_data_schema(),
            errors=self._errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        reconfigure_entry = self._get_reconfigure_entry()
        _LOGGER.debug("Step reconfigure")

        if user_input is not None:
            error = await self._test_credentials(
                user_input[CONF_URL],
                user_input[CONF_API_KEY],
                user_input[CONF_PORT],
                user_input[CONF_VERIFY_SSL],
            )

            if error is None:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates=user_input,
                )

            self._errors["base"] = error
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=_get_user_data_schema(user_input),
                errors=self._errors,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_get_user_data_schema(dict(reconfigure_entry.data)),
            errors=self._errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        reauth_entry = self._get_reauth_entry()
        _LOGGER.debug("Step reauth_confirm")

        if user_input is not None:
            error = await self._test_credentials(
                reauth_entry.data[CONF_URL],
                user_input[CONF_API_KEY],
                reauth_entry.data[CONF_PORT],
                reauth_entry.data[CONF_VERIFY_SSL],
            )

            if error is None:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

            self._errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=self._errors,
            description_placeholders={
                CONF_HOST: reauth_entry.data[CONF_URL],
            },
        )

    async def _test_credentials(
        self, url: str, api_key: str, port: int, verify_ssl: bool
    ) -> str | None:
        """
        Test if credentials are valid.

        Returns None if valid, or an error key if invalid.
        """
        try:
            (base_url, path) = extract_base_url_and_path(url)
            client = Grocy(
                base_url, api_key, port=port, path=path, verify_ssl=verify_ssl
            )

            _LOGGER.debug("Testing credentials")

            def system_info():
                """Get system information from Grocy."""
                return client.system.info()

            await self.hass.async_add_executor_job(system_info)
            return None
        except ConnectionError as error:
            _LOGGER.error("Connection error: %s", error)
            return "cannot_connect"
        except TimeoutError as error:
            _LOGGER.error("Timeout error: %s", error)
            return "timeout"
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error("Authentication error: %s", error)
            return "invalid_auth"


class GrocyOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for Grocy."""

    def __init__(self) -> None:
        """Initialize options flow."""
        super().__init__()
        self._errors: dict[str, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Validate credentials if URL or API key changed
            url_changed = user_input[CONF_URL] != self.config_entry.data.get(CONF_URL)
            api_key_changed = user_input[CONF_API_KEY] != self.config_entry.data.get(
                CONF_API_KEY
            )
            port_changed = user_input[CONF_PORT] != self.config_entry.data.get(
                CONF_PORT
            )
            verify_ssl_changed = user_input[
                CONF_VERIFY_SSL
            ] != self.config_entry.data.get(CONF_VERIFY_SSL, False)

            if url_changed or api_key_changed or port_changed or verify_ssl_changed:
                # Test credentials before saving
                error = await self._test_credentials(
                    user_input[CONF_URL],
                    user_input[CONF_API_KEY],
                    user_input[CONF_PORT],
                    user_input[CONF_VERIFY_SSL],
                )
                if error is not None:
                    self._errors["base"] = error
                    return self.async_show_form(
                        step_id="init",
                        data_schema=_get_user_data_schema(user_input),
                        errors=self._errors,
                    )

            # Update the config entry data with new options
            new_data = {**self.config_entry.data}
            new_data[CONF_URL] = user_input[CONF_URL]
            new_data[CONF_API_KEY] = user_input[CONF_API_KEY]
            new_data[CONF_PORT] = user_input[CONF_PORT]
            new_data[CONF_VERIFY_SSL] = user_input[CONF_VERIFY_SSL]
            new_data[CONF_CALENDAR_SYNC_INTERVAL] = user_input[
                CONF_CALENDAR_SYNC_INTERVAL
            ]
            new_data[CONF_CALENDAR_FIX_TIMEZONE] = user_input.get(
                CONF_CALENDAR_FIX_TIMEZONE, True
            )

            # Update the config entry
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

            # Reload the integration to apply changes
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_get_user_data_schema(dict(self.config_entry.data)),
            errors=self._errors,
        )

    async def _test_credentials(
        self, url: str, api_key: str, port: int, verify_ssl: bool
    ) -> str | None:
        """
        Test if credentials are valid.

        Returns None if valid, or an error key if invalid.
        """
        try:
            (base_url, path) = extract_base_url_and_path(url)
            client = Grocy(
                base_url, api_key, port=port, path=path, verify_ssl=verify_ssl
            )

            _LOGGER.debug("Testing credentials")

            def system_info():
                """Get system information from Grocy."""
                return client.system.info()

            await self.hass.async_add_executor_job(system_info)
            return None
        except ConnectionError as error:
            _LOGGER.error("Connection error: %s", error)
            return "cannot_connect"
        except TimeoutError as error:
            _LOGGER.error("Timeout error: %s", error)
            return "timeout"
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error("Authentication error: %s", error)
            return "invalid_auth"
