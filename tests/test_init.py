from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.grocy import async_setup_entry, async_unload_entry
from custom_components.grocy.const import DOMAIN, PLATFORMS


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
