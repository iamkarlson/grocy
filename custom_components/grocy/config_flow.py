"""Adds config flow for Grocy."""

from __future__ import annotations

import logging
from collections import OrderedDict

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from pygrocy2.grocy import Grocy

from .const import (
    CONF_API_KEY,
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

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, version=2
        )
        _LOGGER.info(
            "Migrated config entry from version %s to version %s",
            version,
            2,
        )
    return True


class GrocyFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Grocy."""

    VERSION = 2

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "GrocyOptionsFlowHandler":
        """Get the options flow for this handler."""
        return GrocyOptionsFlowHandler(config_entry)

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        existing_entry = self._async_current_entries()[0]
        self._reauth_entry = existing_entry

        if user_input is None:
            # Pre-fill with existing values
            data_schema = OrderedDict()
            data_schema[
                vol.Required(
                    CONF_URL, default=existing_entry.data.get(CONF_URL, "")
                )
            ] = str
            data_schema[
                vol.Required(
                    CONF_API_KEY, default=existing_entry.data.get(CONF_API_KEY, "")
                )
            ] = str
            data_schema[
                vol.Optional(
                    CONF_PORT, default=existing_entry.data.get(CONF_PORT, DEFAULT_PORT)
                )
            ] = int
            data_schema[
                vol.Optional(
                    CONF_VERIFY_SSL,
                    default=existing_entry.data.get(CONF_VERIFY_SSL, False),
                )
            ] = bool

            return self.async_show_form(
                step_id="reauth",
                data_schema=vol.Schema(data_schema),
                errors=self._errors,
            )

        # Validate credentials
        valid = await self._test_credentials(
            user_input[CONF_URL],
            user_input[CONF_API_KEY],
            user_input[CONF_PORT],
            user_input[CONF_VERIFY_SSL],
        )

        if not valid:
            self._errors["base"] = "auth"
            # Re-show form with errors
            data_schema = OrderedDict()
            data_schema[
                vol.Required(
                    CONF_URL, default=user_input.get(CONF_URL, "")
                )
            ] = str
            data_schema[
                vol.Required(
                    CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")
                )
            ] = str
            data_schema[
                vol.Optional(
                    CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                )
            ] = int
            data_schema[
                vol.Optional(
                    CONF_VERIFY_SSL,
                    default=user_input.get(CONF_VERIFY_SSL, False),
                )
            ] = bool
            return self.async_show_form(
                step_id="reauth",
                data_schema=vol.Schema(data_schema),
                errors=self._errors,
            )

        # Update the config entry with new credentials
        new_data = {**existing_entry.data}
        new_data[CONF_URL] = user_input[CONF_URL]
        new_data[CONF_API_KEY] = user_input[CONF_API_KEY]
        new_data[CONF_PORT] = user_input[CONF_PORT]
        new_data[CONF_VERIFY_SSL] = user_input[CONF_VERIFY_SSL]

        self.hass.config_entries.async_update_entry(existing_entry, data=new_data)
        await self.hass.config_entries.async_reload(existing_entry.entry_id)

        return self.async_abort(reason="reauth_successful")

    def __init__(self):
        """Initialize."""
        self._errors = {}
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}
        _LOGGER.debug("Step user")

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            valid = await self._test_credentials(
                user_input[CONF_URL],
                user_input[CONF_API_KEY],
                user_input[CONF_PORT],
                user_input[CONF_VERIFY_SSL],
            )
            _LOGGER.debug("Testing of credentials returned: ")
            _LOGGER.debug(valid)
            if valid:
                # Set default calendar sync interval if not provided
                if CONF_CALENDAR_SYNC_INTERVAL not in user_input:
                    user_input[CONF_CALENDAR_SYNC_INTERVAL] = (
                        DEFAULT_CALENDAR_SYNC_INTERVAL
                    )
                return self.async_create_entry(title=NAME, data=user_input)

            self._errors["base"] = "auth"
            return await self._show_config_form(user_input)

        return await self._show_config_form(user_input)

    async def _show_config_form(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to edit the data."""
        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_URL, default="")] = str
        data_schema[
            vol.Required(
                CONF_API_KEY,
                default="",
            )
        ] = str
        data_schema[vol.Optional(CONF_PORT, default=DEFAULT_PORT)] = int
        data_schema[vol.Optional(CONF_VERIFY_SSL, default=False)] = bool
        data_schema[
            vol.Optional(
                CONF_CALENDAR_SYNC_INTERVAL, default=DEFAULT_CALENDAR_SYNC_INTERVAL
            )
        ] = int
        _LOGGER.debug("config form")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=self._errors,
        )

    async def _test_credentials(self, url, api_key, port, verify_ssl):
        """Return true if credentials is valid."""
        try:
            (base_url, path) = extract_base_url_and_path(url)
            client = Grocy(
                base_url, api_key, port=port, path=path, verify_ssl=verify_ssl
            )

            _LOGGER.debug("Testing credentials")

            def system_info():
                """Get system information from Grocy."""
                return client.get_system_info()

            await self.hass.async_add_executor_job(system_info)
            return True
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error(error)
        return False


class GrocyOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for Grocy."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._errors = {}

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Validate credentials if URL or API key changed
            url_changed = user_input[CONF_URL] != self.config_entry.data.get(CONF_URL)
            api_key_changed = user_input[CONF_API_KEY] != self.config_entry.data.get(CONF_API_KEY)
            port_changed = user_input[CONF_PORT] != self.config_entry.data.get(CONF_PORT)
            verify_ssl_changed = user_input[CONF_VERIFY_SSL] != self.config_entry.data.get(
                CONF_VERIFY_SSL, False
            )

            if url_changed or api_key_changed or port_changed or verify_ssl_changed:
                # Test credentials before saving
                valid = await self._test_credentials(
                    user_input[CONF_URL],
                    user_input[CONF_API_KEY],
                    user_input[CONF_PORT],
                    user_input[CONF_VERIFY_SSL],
                )
                if not valid:
                    self._errors["base"] = "auth"
                    return await self._show_options_form(user_input)

            # Update the config entry data with new options
            new_data = {**self.config_entry.data}
            new_data[CONF_URL] = user_input[CONF_URL]
            new_data[CONF_API_KEY] = user_input[CONF_API_KEY]
            new_data[CONF_PORT] = user_input[CONF_PORT]
            new_data[CONF_VERIFY_SSL] = user_input[CONF_VERIFY_SSL]
            new_data[CONF_CALENDAR_SYNC_INTERVAL] = user_input[CONF_CALENDAR_SYNC_INTERVAL]

            # Update the config entry
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

            # Reload the integration to apply changes
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data=user_input)

        return await self._show_options_form()

    async def _show_options_form(self, user_input=None):
        """Show the options form."""
        if user_input is None:
            user_input = {}

        # Show options form with current values
        data_schema = OrderedDict()
        data_schema[
            vol.Required(
                CONF_URL,
                default=user_input.get(
                    CONF_URL, self.config_entry.data.get(CONF_URL, "")
                ),
            )
        ] = str
        data_schema[
            vol.Required(
                CONF_API_KEY,
                default=user_input.get(
                    CONF_API_KEY, self.config_entry.data.get(CONF_API_KEY, "")
                ),
            )
        ] = str
        data_schema[
            vol.Optional(
                CONF_PORT,
                default=user_input.get(
                    CONF_PORT, self.config_entry.data.get(CONF_PORT, DEFAULT_PORT)
                ),
            )
        ] = int
        data_schema[
            vol.Optional(
                CONF_VERIFY_SSL,
                default=user_input.get(
                    CONF_VERIFY_SSL, self.config_entry.data.get(CONF_VERIFY_SSL, False)
                ),
            )
        ] = bool
        data_schema[
            vol.Optional(
                CONF_CALENDAR_SYNC_INTERVAL,
                default=user_input.get(
                    CONF_CALENDAR_SYNC_INTERVAL,
                    self.config_entry.data.get(
                        CONF_CALENDAR_SYNC_INTERVAL, DEFAULT_CALENDAR_SYNC_INTERVAL
                    ),
                ),
            )
        ] = int

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(data_schema),
            errors=self._errors,
        )

    async def _test_credentials(self, url, api_key, port, verify_ssl):
        """Return true if credentials is valid."""
        try:
            from .helpers import extract_base_url_and_path

            (base_url, path) = extract_base_url_and_path(url)
            client = Grocy(
                base_url, api_key, port=port, path=path, verify_ssl=verify_ssl
            )

            _LOGGER.debug("Testing credentials")

            def system_info():
                """Get system information from Grocy."""
                return client.get_system_info()

            await self.hass.async_add_executor_job(system_info)
            return True
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error(error)
        return False
