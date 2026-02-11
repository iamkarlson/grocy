"""Integration setup and teardown tests.

Features: configuration_setup
See: docs/FEATURES.md#10-configuration--setup
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryNotReady

pytestmark = pytest.mark.feature("configuration_setup")

from custom_components.grocy import (
    _async_get_available_entities,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.grocy.const import (
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
    DOMAIN,
    PLATFORMS,
)


@patch(
    "custom_components.grocy.async_setup_endpoint_for_image_proxy",
    new_callable=AsyncMock,
)
@patch(
    "custom_components.grocy.async_setup_services",
    new_callable=AsyncMock,
)
@patch(
    "custom_components.grocy._async_get_available_entities",
    new_callable=AsyncMock,
)
@patch("custom_components.grocy.GrocyDataUpdateCoordinator")
async def test_async_setup_entry_initializes_integration(
    mock_coordinator_cls,
    mock_available_entities,
    mock_setup_services,
    mock_setup_proxy,
    hass,
    mock_config_entry,
) -> None:
    coordinator = MagicMock()
    coordinator.grocy_data = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator_cls.return_value = coordinator
    mock_available_entities.return_value = ["stock"]

    hass.config_entries.async_forward_entry_setups = AsyncMock()

    result = await async_setup_entry(hass, mock_config_entry)

    assert result is True
    mock_available_entities.assert_called_once_with(coordinator.grocy_data)
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
        mock_config_entry, PLATFORMS
    )
    mock_setup_services.assert_awaited_once_with(hass, mock_config_entry)
    mock_setup_proxy.assert_awaited_once()
    assert hass.data[DOMAIN] is coordinator


@patch(
    "custom_components.grocy.async_setup_endpoint_for_image_proxy",
    new_callable=AsyncMock,
)
@patch(
    "custom_components.grocy.async_setup_services",
    new_callable=AsyncMock,
)
@patch(
    "custom_components.grocy._async_get_available_entities",
    new_callable=AsyncMock,
    side_effect=ConnectionRefusedError,
)
@patch("custom_components.grocy.GrocyDataUpdateCoordinator")
async def test_async_setup_entry_raises_not_ready(
    mock_coordinator_cls,
    mock_available_entities,
    mock_setup_services,
    mock_setup_proxy,
    hass,
    mock_config_entry,
) -> None:
    coordinator = MagicMock()
    coordinator.grocy_data = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator_cls.return_value = coordinator

    hass.config_entries.async_forward_entry_setups = AsyncMock()

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, mock_config_entry)

    mock_setup_services.assert_not_called()
    mock_setup_proxy.assert_not_called()
    assert DOMAIN not in hass.data


@patch(
    "custom_components.grocy.async_unload_services",
    new_callable=AsyncMock,
)
async def test_async_unload_entry_cleans_up(
    mock_unload_services, hass, mock_config_entry
) -> None:
    hass.data[DOMAIN] = coordinator = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    result = await async_unload_entry(hass, mock_config_entry)

    assert result is True
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        mock_config_entry, PLATFORMS
    )
    mock_unload_services.assert_awaited_once_with(hass)
    assert DOMAIN not in hass.data


@patch(
    "custom_components.grocy.async_unload_services",
    new_callable=AsyncMock,
)
async def test_async_unload_entry_platform_failure(
    mock_unload_services, hass, mock_config_entry
) -> None:
    hass.data[DOMAIN] = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

    result = await async_unload_entry(hass, mock_config_entry)

    assert result is False
    assert DOMAIN in hass.data
    mock_unload_services.assert_awaited_once_with(hass)


# ─── _async_get_available_entities ────────────────────────────────────────────


def _make_grocy_data(features: set[str]):
    grocy_data = MagicMock()
    config = MagicMock()
    config.enabled_features = features
    grocy_data.async_get_config = AsyncMock(return_value=config)
    return grocy_data


@pytest.mark.asyncio
async def test_available_entities_all_features() -> None:
    all_features = {
        "FEATURE_FLAG_STOCK",
        "FEATURE_FLAG_SHOPPINGLIST",
        "FEATURE_FLAG_TASKS",
        "FEATURE_FLAG_CHORES",
        "FEATURE_FLAG_RECIPES",
        "FEATURE_FLAG_BATTERIES",
    }
    grocy_data = _make_grocy_data(all_features)
    result = await _async_get_available_entities(grocy_data)

    expected = {
        ATTR_STOCK,
        ATTR_MISSING_PRODUCTS,
        ATTR_EXPIRED_PRODUCTS,
        ATTR_EXPIRING_PRODUCTS,
        ATTR_OVERDUE_PRODUCTS,
        ATTR_SHOPPING_LIST,
        ATTR_TASKS,
        ATTR_OVERDUE_TASKS,
        ATTR_CHORES,
        ATTR_OVERDUE_CHORES,
        ATTR_MEAL_PLAN,
        ATTR_BATTERIES,
        ATTR_OVERDUE_BATTERIES,
    }
    assert set(result) == expected


@pytest.mark.asyncio
async def test_available_entities_stock_only() -> None:
    grocy_data = _make_grocy_data({"FEATURE_FLAG_STOCK"})
    result = await _async_get_available_entities(grocy_data)

    assert ATTR_STOCK in result
    assert ATTR_MISSING_PRODUCTS in result
    assert ATTR_EXPIRED_PRODUCTS in result
    assert ATTR_EXPIRING_PRODUCTS in result
    assert ATTR_OVERDUE_PRODUCTS in result
    assert ATTR_TASKS not in result
    assert ATTR_CHORES not in result


@pytest.mark.asyncio
async def test_available_entities_tasks_only() -> None:
    grocy_data = _make_grocy_data({"FEATURE_FLAG_TASKS"})
    result = await _async_get_available_entities(grocy_data)

    assert set(result) == {ATTR_TASKS, ATTR_OVERDUE_TASKS}


@pytest.mark.asyncio
async def test_available_entities_chores_only() -> None:
    grocy_data = _make_grocy_data({"FEATURE_FLAG_CHORES"})
    result = await _async_get_available_entities(grocy_data)

    assert set(result) == {ATTR_CHORES, ATTR_OVERDUE_CHORES}


@pytest.mark.asyncio
async def test_available_entities_shopping_list_only() -> None:
    grocy_data = _make_grocy_data({"FEATURE_FLAG_SHOPPINGLIST"})
    result = await _async_get_available_entities(grocy_data)

    assert result == [ATTR_SHOPPING_LIST]


@pytest.mark.asyncio
async def test_available_entities_recipes_only() -> None:
    grocy_data = _make_grocy_data({"FEATURE_FLAG_RECIPES"})
    result = await _async_get_available_entities(grocy_data)

    assert result == [ATTR_MEAL_PLAN]


@pytest.mark.asyncio
async def test_available_entities_batteries_only() -> None:
    grocy_data = _make_grocy_data({"FEATURE_FLAG_BATTERIES"})
    result = await _async_get_available_entities(grocy_data)

    assert set(result) == {ATTR_BATTERIES, ATTR_OVERDUE_BATTERIES}


@pytest.mark.asyncio
async def test_available_entities_no_features() -> None:
    grocy_data = _make_grocy_data(set())
    result = await _async_get_available_entities(grocy_data)

    assert result == []


@pytest.mark.asyncio
async def test_available_entities_none_config() -> None:
    grocy_data = MagicMock()
    grocy_data.async_get_config = AsyncMock(return_value=None)
    result = await _async_get_available_entities(grocy_data)

    assert result == []


@pytest.mark.asyncio
async def test_async_setup_entry_raises_not_ready_on_timeout(
    hass, mock_config_entry
) -> None:
    with (
        patch("custom_components.grocy.GrocyDataUpdateCoordinator") as mock_cls,
        patch(
            "custom_components.grocy._async_get_available_entities",
            new_callable=AsyncMock,
            side_effect=TimeoutError,
        ),
        patch(
            "custom_components.grocy.async_setup_services",
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.grocy.async_setup_endpoint_for_image_proxy",
            new_callable=AsyncMock,
        ),
    ):
        coordinator = MagicMock()
        coordinator.grocy_data = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_cls.return_value = coordinator

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)


@pytest.mark.asyncio
async def test_async_setup_entry_raises_not_ready_on_os_error(
    hass, mock_config_entry
) -> None:
    with (
        patch("custom_components.grocy.GrocyDataUpdateCoordinator") as mock_cls,
        patch(
            "custom_components.grocy._async_get_available_entities",
            new_callable=AsyncMock,
            side_effect=OSError("Network unreachable"),
        ),
        patch(
            "custom_components.grocy.async_setup_services",
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.grocy.async_setup_endpoint_for_image_proxy",
            new_callable=AsyncMock,
        ),
    ):
        coordinator = MagicMock()
        coordinator.grocy_data = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_cls.return_value = coordinator

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)
