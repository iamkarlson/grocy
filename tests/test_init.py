"""
Integration setup and teardown tests.

Features: configuration_setup
See: docs/FEATURES.md#10-configuration-setup
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests
from grocy.errors import GrocyError
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.grocy import (
    _async_get_available_entities,
    async_setup,
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
    ATTR_RECIPES,
    ATTR_SHOPPING_LIST,
    ATTR_STOCK,
    ATTR_TASKS,
    DOMAIN,
    PLATFORMS,
)

pytestmark = pytest.mark.feature("configuration_setup")


@patch(
    "custom_components.grocy._async_get_available_entities",
    new_callable=AsyncMock,
)
@patch("custom_components.grocy.GrocyDataUpdateCoordinator")
async def test_async_setup_entry_initializes_integration(
    mock_coordinator_cls,
    mock_available_entities,
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
    assert mock_config_entry.runtime_data is coordinator


@patch(
    "custom_components.grocy._async_get_available_entities",
    new_callable=AsyncMock,
    side_effect=ConnectionRefusedError,
)
@patch("custom_components.grocy.GrocyDataUpdateCoordinator")
async def test_async_setup_entry_raises_not_ready(
    mock_coordinator_cls,
    mock_available_entities,
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

    assert not hasattr(mock_config_entry, "runtime_data")


@pytest.mark.parametrize("unloaded", [True, False])
async def test_async_unload_entry_unloads_platforms(
    hass, mock_config_entry, unloaded
) -> None:
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=unloaded)

    assert await async_unload_entry(hass, mock_config_entry) is unloaded
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        mock_config_entry, PLATFORMS
    )


async def test_async_setup_registers_actions_and_picture_view(hass) -> None:
    """Actions and the picture view are registered once per run, not per entry."""
    hass.http = MagicMock()

    assert await async_setup(hass, {}) is True

    assert hass.services.async_services().get(DOMAIN)
    hass.http.register_view.assert_called_once()


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
        ATTR_RECIPES,
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

    assert set(result) == {ATTR_MEAL_PLAN, ATTR_RECIPES}


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
    ):
        coordinator = MagicMock()
        coordinator.grocy_data = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_cls.return_value = coordinator

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)


def _grocy_error(status: int, body: bytes = b"") -> GrocyError:
    response = requests.Response()
    response.status_code = status
    response._content = body
    return GrocyError(response)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, ConfigEntryAuthFailed),
        (403, ConfigEntryAuthFailed),
        (500, ConfigEntryNotReady),
        (200, ConfigEntryNotReady),  # the empty HTML page of an unknown route
    ],
)
async def test_async_setup_entry_maps_grocy_errors(
    hass, mock_config_entry, status, expected
) -> None:
    """A Grocy error at setup starts re-authentication or a retry (#75)."""
    with (
        patch("custom_components.grocy.GrocyDataUpdateCoordinator") as mock_cls,
        patch(
            "custom_components.grocy._async_get_available_entities",
            new_callable=AsyncMock,
            side_effect=_grocy_error(status),
        ),
    ):
        coordinator = MagicMock()
        coordinator.grocy_data = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_cls.return_value = coordinator

        with pytest.raises(expected):
            await async_setup_entry(hass, mock_config_entry)
