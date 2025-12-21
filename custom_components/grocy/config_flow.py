"""Adds config flow for Grocy."""

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


class GrocyFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Grocy."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
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

    def __init__(self):
        """Initialize."""
        self._errors = {}

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
