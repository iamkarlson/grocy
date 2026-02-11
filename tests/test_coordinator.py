"""Coordinator tests for the data update loop.

Features: configuration_setup
See: docs/FEATURES.md#10-configuration--setup
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.grocy.coordinator import GrocyDataUpdateCoordinator

pytestmark = pytest.mark.feature("configuration_setup")


class DummyEntity:
    def __init__(self, key: str, enabled: bool = True) -> None:
        self.entity_description = SimpleNamespace(key=key)
        self.enabled = enabled
        self.entity_id = f"grocy.{key}"


@pytest.mark.asyncio
async def test_async_update_data_skips_disabled_entities() -> None:
    coordinator = GrocyDataUpdateCoordinator.__new__(GrocyDataUpdateCoordinator)
    coordinator.entities = [
        DummyEntity("stock", enabled=True),
        DummyEntity("tasks", enabled=False),
    ]

    coordinator.grocy_data = SimpleNamespace(
        async_update_data=AsyncMock(return_value=["item"])
    )

    result = await GrocyDataUpdateCoordinator._async_update_data(coordinator)

    coordinator.grocy_data.async_update_data.assert_awaited_once_with("stock")
    assert result.stock == ["item"]
    assert result.tasks is None


@pytest.mark.asyncio
async def test_async_update_data_raises_update_failed() -> None:
    coordinator = GrocyDataUpdateCoordinator.__new__(GrocyDataUpdateCoordinator)
    coordinator.entities = [DummyEntity("stock", enabled=True)]
    coordinator.grocy_data = SimpleNamespace(
        async_update_data=AsyncMock(side_effect=RuntimeError("boom"))
    )

    with pytest.raises(UpdateFailed) as captured:
        await GrocyDataUpdateCoordinator._async_update_data(coordinator)

    assert "boom" in str(captured.value)
