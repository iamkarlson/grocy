from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.grocy.const import (
    CONF_API_KEY,
    CONF_PORT,
    CONF_URL,
    CONF_VERIFY_SSL,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(name="config_entry_data")
def config_entry_data_fixture() -> dict[str, object]:
    return {
        CONF_URL: "https://demo.grocy.info",
        CONF_API_KEY: "test-token",
        CONF_PORT: 9192,
        CONF_VERIFY_SSL: False,
    }


@pytest.fixture(name="mock_config_entry")
def mock_config_entry_fixture(
    config_entry_data: dict[str, object],
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Grocy",
        data=config_entry_data,
        entry_id="test-entry",
    )
    return entry


@pytest.fixture(name="mock_grocy")
def mock_grocy_fixture() -> MagicMock:
    mock_client = MagicMock()
    mock_client.system.info.return_value = {"id": 1}
    mock_client.system.config.return_value = MagicMock(
        enabled_features={"FEATURE_FLAG_STOCK", "FEATURE_FLAG_TASKS"}
    )

    stock_api = MagicMock()
    stock_api._api = MagicMock()
    stock_api._api.get_stock.return_value = []
    stock_api.due_products.return_value = []
    stock_api.expired_products.return_value = []
    stock_api.overdue_products.return_value = []
    stock_api.missing_products.return_value = []
    mock_client.stock = stock_api

    chores_api = MagicMock()
    chores_api.list.return_value = []
    mock_client.chores = chores_api

    tasks_api = MagicMock()
    tasks_api.list.return_value = []
    tasks_api.complete = MagicMock()
    mock_client.tasks = tasks_api

    shopping_api = MagicMock()
    shopping_api.items.return_value = []
    shopping_api.remove_product = MagicMock()
    shopping_api.add_missing_products = MagicMock()
    mock_client.shopping_list = shopping_api

    recipes_api = MagicMock()
    recipes_api.consume = MagicMock()
    mock_client.recipes = recipes_api

    batteries_api = MagicMock()
    batteries_api.list.return_value = []
    batteries_api.charge = MagicMock()
    mock_client.batteries = batteries_api

    generic_api = MagicMock()
    mock_client.generic = generic_api

    return mock_client


@pytest.fixture(name="call_recorder")
def call_recorder_fixture() -> CallRecorder:
    return CallRecorder()


class CallRecorder:
    """Capture invocations for later assertions."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def wrap(self, name: str, func):  # type: ignore[no-untyped-def]
        def _wrapper(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return func(*args, **kwargs)

        return _wrapper


def build_namespace(**kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)
