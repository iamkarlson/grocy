from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import hdrs

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
    CONF_API_KEY,
    CONF_PORT,
    CONF_URL,
)
from custom_components.grocy.grocy_data import (
    GrocyData,
    GrocyPictureView,
    async_setup_endpoint_for_image_proxy,
)
from tests.factories import (
    DummyBattery,
    DummyChore,
    DummyMealPlanItem,
    DummyProduct,
    DummyShoppingListProduct,
    DummyTask,
)


@pytest.fixture
def grocy_data(hass, mock_grocy) -> GrocyData:
    async def immediate_executor(func, *args):
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=immediate_executor)
    return GrocyData(hass, mock_grocy)


# ─── async_update_data dispatch ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_update_data_dispatches_to_correct_method(grocy_data) -> None:
    mock_update = AsyncMock(return_value=["stock_item"])
    grocy_data.entity_update_method[ATTR_STOCK] = mock_update
    result = await grocy_data.async_update_data(ATTR_STOCK)
    mock_update.assert_awaited_once()
    assert result == ["stock_item"]


@pytest.mark.asyncio
async def test_async_update_data_returns_none_for_unknown_key(grocy_data) -> None:
    result = await grocy_data.async_update_data("unknown_key")
    assert result is None


# ─── async_update_stock ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_update_stock_returns_products(grocy_data) -> None:
    product = DummyProduct()
    grocy_data.api.stock.current.return_value = [product]
    result = await grocy_data.async_update_stock()
    assert len(result) == 1
    grocy_data.api.stock.current.assert_called_once()


@pytest.mark.asyncio
async def test_async_update_stock_empty(grocy_data) -> None:
    grocy_data.api.stock.current.return_value = []
    result = await grocy_data.async_update_stock()
    assert result == []


# ─── async_update_chores ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_update_chores(grocy_data) -> None:
    chore = DummyChore()
    grocy_data.api.chores.list.return_value = [chore]
    result = await grocy_data.async_update_chores()
    assert result == [chore]
    grocy_data.api.chores.list.assert_called_once_with(get_details=True)


# ─── async_update_overdue_chores ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_update_overdue_chores(grocy_data) -> None:
    chore = DummyChore()
    grocy_data.api.chores.list.return_value = [chore]
    result = await grocy_data.async_update_overdue_chores()
    assert result == [chore]
    call_args = grocy_data.api.chores.list.call_args
    assert call_args.kwargs["get_details"] is True
    assert "query_filters" in call_args.kwargs
    filters = call_args.kwargs["query_filters"]
    assert len(filters) == 1
    assert "next_estimated_execution_time<" in filters[0]


# ─── async_update_tasks ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_update_tasks(grocy_data) -> None:
    task = DummyTask()
    grocy_data.api.tasks.list.return_value = [task]
    result = await grocy_data.async_update_tasks()
    assert result == [task]
    grocy_data.api.tasks.list.assert_called_once()


# ─── async_update_overdue_tasks ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_update_overdue_tasks(grocy_data) -> None:
    task = DummyTask()
    grocy_data.api.tasks.list.return_value = [task]
    result = await grocy_data.async_update_overdue_tasks()
    assert result == [task]
    call_args = grocy_data.api.tasks.list.call_args
    assert "query_filters" in call_args.kwargs
    filters = call_args.kwargs["query_filters"]
    assert len(filters) == 2
    assert "due_date<" in filters[0]


# ─── async_update_shopping_list ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_update_shopping_list(grocy_data) -> None:
    item = DummyShoppingListProduct()
    grocy_data.api.shopping_list.items.return_value = [item]
    result = await grocy_data.async_update_shopping_list()
    assert result == [item]
    grocy_data.api.shopping_list.items.assert_called_once_with(get_details=True)


# ─── async_update_expiring_products ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_update_expiring_products(grocy_data) -> None:
    product = DummyProduct()
    grocy_data.api.stock.due_products.return_value = [product]
    result = await grocy_data.async_update_expiring_products()
    assert result == [product]
    grocy_data.api.stock.due_products.assert_called_once_with(get_details=True)


# ─── async_update_expired_products ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_update_expired_products(grocy_data) -> None:
    product = DummyProduct()
    grocy_data.api.stock.expired_products.return_value = [product]
    result = await grocy_data.async_update_expired_products()
    assert result == [product]
    grocy_data.api.stock.expired_products.assert_called_once_with(get_details=True)


# ─── async_update_overdue_products ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_update_overdue_products(grocy_data) -> None:
    product = DummyProduct()
    grocy_data.api.stock.overdue_products.return_value = [product]
    result = await grocy_data.async_update_overdue_products()
    assert result == [product]
    grocy_data.api.stock.overdue_products.assert_called_once_with(get_details=True)


# ─── async_update_missing_products ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_update_missing_products(grocy_data) -> None:
    product = DummyProduct()
    grocy_data.api.stock.missing_products.return_value = [product]
    result = await grocy_data.async_update_missing_products()
    assert result == [product]
    grocy_data.api.stock.missing_products.assert_called_once_with(get_details=True)


# ─── async_update_meal_plan ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_update_meal_plan_sorts_by_day(grocy_data) -> None:
    day1 = DummyMealPlanItem(id=2, day=dt.date.today() + dt.timedelta(days=3))
    day2 = DummyMealPlanItem(id=1, day=dt.date.today() + dt.timedelta(days=1))
    grocy_data.api.meal_plan.items.return_value = [day1, day2]

    with patch(
        "custom_components.grocy.grocy_data.MealPlanItemWrapper"
    ) as mock_wrapper_cls:
        # Make wrappers that preserve meal_plan.day for sorting
        def make_wrapper(item):
            w = MagicMock()
            w.meal_plan = item
            return w

        mock_wrapper_cls.side_effect = make_wrapper
        result = await grocy_data.async_update_meal_plan()

    assert len(result) == 2
    # Should be sorted by day: day2 (earlier) first
    assert result[0].meal_plan.id == 1
    assert result[1].meal_plan.id == 2

    call_args = grocy_data.api.meal_plan.items.call_args
    assert call_args.kwargs["get_details"] is True
    assert "query_filters" in call_args.kwargs


@pytest.mark.asyncio
async def test_async_update_meal_plan_empty(grocy_data) -> None:
    grocy_data.api.meal_plan.items.return_value = []
    result = await grocy_data.async_update_meal_plan()
    assert result == []


# ─── async_update_batteries ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_update_batteries(grocy_data) -> None:
    battery = DummyBattery()
    grocy_data.api.batteries.list.return_value = [battery]
    result = await grocy_data.async_update_batteries()
    assert result == [battery]
    grocy_data.api.batteries.list.assert_called_once_with(get_details=True)


# ─── async_update_overdue_batteries ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_update_overdue_batteries(grocy_data) -> None:
    battery = DummyBattery()
    grocy_data.api.batteries.list.return_value = [battery]
    result = await grocy_data.async_update_overdue_batteries()
    assert result == [battery]
    call_args = grocy_data.api.batteries.list.call_args
    assert call_args.kwargs["get_details"] is True


# ─── async_get_config ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_get_config(grocy_data) -> None:
    mock_config = MagicMock()
    grocy_data.api.system.config.return_value = mock_config
    result = await grocy_data.async_get_config()
    assert result is mock_config
    grocy_data.api.system.config.assert_called_once()


# ─── async_setup_endpoint_for_image_proxy ─────────────────────────────────────


@pytest.mark.asyncio
async def test_async_setup_endpoint_registers_view(hass) -> None:
    config_data = {
        CONF_URL: "https://demo.grocy.info",
        CONF_API_KEY: "test-key",
        CONF_PORT: 9192,
    }
    hass.http = MagicMock()

    with patch(
        "custom_components.grocy.grocy_data.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = MagicMock()
        await async_setup_endpoint_for_image_proxy(hass, config_data)

    hass.http.register_view.assert_called_once()
    view = hass.http.register_view.call_args[0][0]
    assert isinstance(view, GrocyPictureView)


@pytest.mark.asyncio
async def test_async_setup_endpoint_with_path(hass) -> None:
    config_data = {
        CONF_URL: "https://demo.grocy.info/grocy",
        CONF_API_KEY: "test-key",
        CONF_PORT: 443,
    }
    hass.http = MagicMock()

    with patch(
        "custom_components.grocy.grocy_data.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value = MagicMock()
        await async_setup_endpoint_for_image_proxy(hass, config_data)

    view = hass.http.register_view.call_args[0][0]
    assert "grocy" in view._base_url


# ─── GrocyPictureView ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_picture_view_get_proxies_request() -> None:
    mock_session = MagicMock()
    response_body = b"\x89PNG\r\n"
    mock_resp = MagicMock()
    mock_resp.headers = {
        hdrs.CONTENT_TYPE: "image/png",
        hdrs.CONTENT_LENGTH: str(len(response_body)),
        "X-Custom-Header": "should-be-excluded",
    }
    mock_resp.read = AsyncMock(return_value=response_body)
    mock_resp.raise_for_status = MagicMock()

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_context.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = mock_context

    view = GrocyPictureView(mock_session, "https://grocy.local:9192", "api-key-123")

    request = MagicMock()
    request.query = {"width": "200"}

    response = await view.get(request, "productpictures", "abc123")

    mock_session.get.assert_called_once()
    call_url = mock_session.get.call_args[0][0]
    assert "/api/files/productpictures/abc123" in call_url
    assert "best_fit_width=200" in call_url

    call_headers = mock_session.get.call_args[1]["headers"]
    assert call_headers["GROCY-API-KEY"] == "api-key-123"

    assert response.body == response_body
    assert hdrs.CONTENT_TYPE in response.headers
    assert "X-Custom-Header" not in response.headers


@pytest.mark.asyncio
async def test_picture_view_uses_default_width() -> None:
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.headers = {}
    mock_resp.read = AsyncMock(return_value=b"img")
    mock_resp.raise_for_status = MagicMock()

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_context.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = mock_context

    view = GrocyPictureView(mock_session, "https://grocy.local:9192", "key")

    request = MagicMock()
    request.query = {}

    await view.get(request, "recipepictures", "xyz")

    call_url = mock_session.get.call_args[0][0]
    assert "best_fit_width=400" in call_url


def test_picture_view_requires_no_auth() -> None:
    assert GrocyPictureView.requires_auth is False


def test_picture_view_url_pattern() -> None:
    assert "{picture_type}" in GrocyPictureView.url
    assert "{filename}" in GrocyPictureView.url


# ─── All entity keys are mapped ──────────────────────────────────────────────


def test_all_entity_keys_have_update_methods(hass, mock_grocy) -> None:
    hass.async_add_executor_job = AsyncMock()
    data = GrocyData(hass, mock_grocy)
    expected_keys = {
        ATTR_STOCK,
        ATTR_CHORES,
        ATTR_TASKS,
        ATTR_SHOPPING_LIST,
        ATTR_EXPIRING_PRODUCTS,
        ATTR_EXPIRED_PRODUCTS,
        ATTR_OVERDUE_PRODUCTS,
        ATTR_MISSING_PRODUCTS,
        ATTR_MEAL_PLAN,
        ATTR_OVERDUE_CHORES,
        ATTR_OVERDUE_TASKS,
        ATTR_BATTERIES,
        ATTR_OVERDUE_BATTERIES,
    }
    assert set(data.entity_update_method.keys()) == expected_keys
