"""
Custom integration to integrate Grocy with Home Assistant.

For more details about this integration, please refer to
https://github.com/iamkarlson/grocy
"""

from __future__ import annotations

import logging

from aiohttp import ClientConnectorError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

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
    ATTR_SHOPPING_LIST,
    ATTR_STOCK,
    ATTR_TASKS,
    CONF_CALENDAR_FIX_TIMEZONE,
    CONF_CALENDAR_SYNC_INTERVAL,
    DEFAULT_CALENDAR_SYNC_INTERVAL,
    DOMAIN,
    PLATFORMS,
    STARTUP_MESSAGE,
)
from .coordinator import GrocyDataUpdateCoordinator
from .grocy_data import GrocyData, async_setup_endpoint_for_image_proxy
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
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

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    await async_setup_services(hass, config_entry)
    await async_setup_endpoint_for_image_proxy(hass, config_entry.data)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await async_unload_services(hass)
    if unloaded := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        del hass.data[DOMAIN]

    return unloaded


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

        if "FEATURE_FLAG_BATTERIES" in grocy_config.enabled_features:
            available_entities.append(ATTR_BATTERIES)
            available_entities.append(ATTR_OVERDUE_BATTERIES)

    _LOGGER.debug("Available entities: %s", available_entities)

    return available_entities


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    version = config_entry.version or 1  # Default to version 1 if None
    _LOGGER.info(
        "Starting migration for config entry: %s (current version: %s, target version: 2)",
        config_entry.entry_id,
        version,
    )

    new_data = {**config_entry.data}
    updated = False
    target_version = 2
    version_2 = 2

    # Migrate from version 1 to 2
    if version < version_2:
        _LOGGER.info("Migrating from version %s to version %s", version, version_2)
        # Add calendar_sync_interval if not present
        if CONF_CALENDAR_SYNC_INTERVAL not in new_data:
            new_data[CONF_CALENDAR_SYNC_INTERVAL] = DEFAULT_CALENDAR_SYNC_INTERVAL
            _LOGGER.debug(
                "Added %s: %s",
                CONF_CALENDAR_SYNC_INTERVAL,
                DEFAULT_CALENDAR_SYNC_INTERVAL,
            )
        # Add fix_timezone if not present
        if CONF_CALENDAR_FIX_TIMEZONE not in new_data:
            new_data[CONF_CALENDAR_FIX_TIMEZONE] = True
            _LOGGER.debug("Added %s: %s", CONF_CALENDAR_FIX_TIMEZONE, True)
        updated = True
        version = version_2

    # Migrate old constant name to new one (if present)
    old_constant = "calendar_fix_datetime_for_addon"
    if old_constant in new_data:
        _LOGGER.info(
            "Migrating old constant name '%s' to '%s'",
            old_constant,
            CONF_CALENDAR_FIX_TIMEZONE,
        )
        new_data[CONF_CALENDAR_FIX_TIMEZONE] = new_data.pop(old_constant)
        updated = True

    # Ensure we're at the target version
    if version < target_version:
        _LOGGER.warning(
            "Config entry version %s is less than target version %s, updating",
            version,
            target_version,
        )
        version = target_version
        updated = True

    if updated:
        _LOGGER.info(
            "Updating config entry to version %s with data: %s",
            version,
            new_data,
        )
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, version=version
        )
        _LOGGER.info(
            "Successfully migrated config entry from version %s to version %s",
            config_entry.version,
            version,
        )
    else:
        _LOGGER.debug("No migration needed for config entry (version %s)", version)

    return True
