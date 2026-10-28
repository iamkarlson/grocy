"""
Custom integration to integrate Grocy with Home Assistant.

For more details about this integration, please refer to
https://github.com/iamkarlson/grocy
"""

from __future__ import annotations

import logging
from http import HTTPStatus

from aiohttp import ClientConnectorError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from grocy.errors import GrocyError

from .config_flow import async_migrate_entry
from .const import (
    ATTR_BATTERIES,
    ATTR_CHORES,
    ATTR_EXPIRED_PRODUCTS,
    ATTR_EXPIRING_PRODUCTS,
    ATTR_MEAL_PLAN,
    ATTR_MISSING_PRODUCTS,
    ATTR_OVERDUE_BATTERIES,
    ATTR_OVERDUE_CHORES,
    ATTR_OVERDUE_PRODUCTS,
    ATTR_OVERDUE_TASKS,
    ATTR_RECIPES,
    ATTR_SHOPPING_LIST,
    ATTR_STOCK,
    ATTR_TASKS,
    DOMAIN,
    PLATFORMS,
    STARTUP_MESSAGE,
)
from .coordinator import GrocyConfigEntry, GrocyDataUpdateCoordinator
from .grocy_data import GrocyData, async_setup_endpoint_for_image_proxy
from .services import async_setup_services

__all__ = ["async_migrate_entry"]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions and the picture proxy once per Home Assistant run."""
    async_setup_services(hass)
    async_setup_endpoint_for_image_proxy(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: GrocyConfigEntry):
    """Set up this integration using UI."""
    _LOGGER.info(STARTUP_MESSAGE)

    coordinator: GrocyDataUpdateCoordinator = GrocyDataUpdateCoordinator(
        hass, config_entry
    )

    try:
        coordinator.available_entities = await _async_get_available_entities(
            coordinator.grocy_data
        )
        await coordinator.async_config_entry_first_refresh()
    except (
        ConnectionRefusedError,
        ClientConnectorError,
        OSError,
        TimeoutError,
    ) as error:
        _LOGGER.warning("Unable to connect to Grocy: %s", error)
        raise ConfigEntryNotReady(f"Unable to connect to Grocy: {error}") from error
    except GrocyError as error:
        # 401: the API key is wrong or revoked. 403: its user cannot read the config.
        if error.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            raise ConfigEntryAuthFailed(
                f"Grocy rejected the API key: {error}"
            ) from error
        raise ConfigEntryNotReady(f"Grocy answered with an error: {error}") from error

    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: GrocyConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def _async_get_available_entities(grocy_data: GrocyData) -> list[str]:
    """Return a list of available entities based on enabled Grocy features."""
    available_entities = []
    grocy_config = await grocy_data.async_get_config()
    if grocy_config:
        if "FEATURE_FLAG_STOCK" in grocy_config.enabled_features:
            available_entities.append(ATTR_STOCK)
            available_entities.append(ATTR_MISSING_PRODUCTS)
            available_entities.append(ATTR_EXPIRED_PRODUCTS)
            available_entities.append(ATTR_EXPIRING_PRODUCTS)
            available_entities.append(ATTR_OVERDUE_PRODUCTS)

        if "FEATURE_FLAG_SHOPPINGLIST" in grocy_config.enabled_features:
            available_entities.append(ATTR_SHOPPING_LIST)

        if "FEATURE_FLAG_TASKS" in grocy_config.enabled_features:
            available_entities.append(ATTR_TASKS)
            available_entities.append(ATTR_OVERDUE_TASKS)

        if "FEATURE_FLAG_CHORES" in grocy_config.enabled_features:
            available_entities.append(ATTR_CHORES)
            available_entities.append(ATTR_OVERDUE_CHORES)

        if "FEATURE_FLAG_RECIPES" in grocy_config.enabled_features:
            available_entities.append(ATTR_MEAL_PLAN)
            available_entities.append(ATTR_RECIPES)

        if "FEATURE_FLAG_BATTERIES" in grocy_config.enabled_features:
            available_entities.append(ATTR_BATTERIES)
            available_entities.append(ATTR_OVERDUE_BATTERIES)

    _LOGGER.debug("Available entities: %s", available_entities)

    return available_entities
