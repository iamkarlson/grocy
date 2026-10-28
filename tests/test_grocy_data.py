"""
GrocyData API interface tests.

Features: stock_management, shopping_list, chore_management, task_management,
          battery_tracking, meal_planning, image_proxy, cross_cutting
See: docs/FEATURES.md
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from aiohttp import ClientError, hdrs, web

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
    CONF_API_KEY,
    CONF_PORT,
    CONF_URL,
    CONF_VERIFY_SSL,
    DOMAIN,
)
from custom_components.grocy.grocy_data import (
    GrocyData,
    GrocyPictureView,
    async_setup_endpoint_for_image_proxy,
)
from custom_components.grocy.helpers import recipe_picture_url
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
    mock_grocy.system.time.return_value = _server_time("UTC", hours=0)
    return GrocyData(hass, mock_grocy, "https://exemple.com")


def _server_time(zone: str, hours: int) -> SimpleNamespace:
    """Build the system.time() answer of a Grocy server."""
    now = dt.datetime(2026, 10, 21, 12, 0, tzinfo=dt.UTC)
    return SimpleNamespace(
        timezone=zone, time_utc=now, time_local=now + dt.timedelta(hours=hours)
    )


# ─── async_update_data dispatch ───────────────────────────────────────────────


@pytest.mark.feature("cross_cutting")
@pytest.mark.asyncio
async def test_async_update_data_dispatches_to_correct_method(grocy_data) -> None:
    """Verify data dispatch routing."""
    mock_update = AsyncMock(return_value=["stock_item"])
    grocy_data.entity_update_method[ATTR_STOCK] = mock_update
    result = await grocy_data.async_update_data(ATTR_STOCK)
    mock_update.assert_awaited_once()
    assert result == ["stock_item"]


@pytest.mark.feature("cross_cutting")
@pytest.mark.asyncio
async def test_async_update_data_returns_none_for_unknown_key(grocy_data) -> None:
    """Verify unknown key returns None."""
    result = await grocy_data.async_update_data("unknown_key")
    assert result is None


# ─── async_update_stock ───────────────────────────────────────────────────────


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_update_stock_returns_products(grocy_data) -> None:
    """Verify stock data fetching returns products."""
    product = DummyProduct()
    grocy_data.api.stock.current.return_value = [product]
    result = await grocy_data.async_update_stock()
    assert len(result) == 1
    grocy_data.api.stock.current.assert_called_once()


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_update_stock_empty(grocy_data) -> None:
    """Verify stock data fetching handles empty list."""
    grocy_data.api.stock.current.return_value = []
    result = await grocy_data.async_update_stock()
    assert result == []


# ─── async_update_chores ──────────────────────────────────────────────────────


@pytest.mark.feature("chore_management")
@pytest.mark.asyncio
async def test_async_update_chores(grocy_data) -> None:
    """Verify chores data fetching with details."""
    chore = DummyChore()
    grocy_data.api.chores.list.return_value = [chore]
    result = await grocy_data.async_update_chores()
    assert result == [chore]
    grocy_data.api.chores.list.assert_called_once_with(get_details=True)


# ─── async_update_overdue_chores ──────────────────────────────────────────────


@pytest.mark.feature("chore_management")
@pytest.mark.asyncio
async def test_async_update_overdue_chores(grocy_data) -> None:
    """Verify overdue chores filtering with date query."""
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


@pytest.mark.feature("chore_management")
@pytest.mark.asyncio
async def test_overdue_filters_use_the_grocy_server_clock(grocy_data) -> None:
    """Grocy stores due times in its own time zone, not in the HA one (#83)."""
    zone = ZoneInfo("Pacific/Kiritimati")  # UTC+14, so the day differs from UTC
    grocy_data.api.system.time.return_value = _server_time(zone.key, hours=14)
    grocy_data.api.tasks.list.return_value = []
    grocy_data.api.chores.list.return_value = []

    before = dt.datetime.now(zone).replace(tzinfo=None)
    await grocy_data.async_update_overdue_tasks()
    await grocy_data.async_update_overdue_chores()
    after = dt.datetime.now(zone).replace(tzinfo=None)

    task_filter = grocy_data.api.tasks.list.call_args.kwargs["query_filters"][0]
    assert task_filter in {f"due_date<{before.date()}", f"due_date<{after.date()}"}
    chore_filter = grocy_data.api.chores.list.call_args.kwargs["query_filters"][0]
    sent = dt.datetime.fromisoformat(chore_filter.split("<")[1])
    assert before <= sent <= after
    # The zone is read once, not at each update.
    grocy_data.api.system.time.assert_called_once()


@pytest.mark.feature("chore_management")
@pytest.mark.asyncio
async def test_unknown_server_zone_name_uses_the_offset(grocy_data) -> None:
    """A zone name that zoneinfo does not know falls back to the UTC offset (#83)."""
    grocy_data.api.system.time.return_value = _server_time("Not/AZone", hours=14)
    grocy_data.api.chores.list.return_value = []

    await grocy_data.async_update_overdue_chores()

    chore_filter = grocy_data.api.chores.list.call_args.kwargs["query_filters"][0]
    sent = dt.datetime.fromisoformat(chore_filter.split("<")[1])
    expected = dt.datetime.now(dt.UTC).replace(tzinfo=None) + dt.timedelta(hours=14)
    assert abs(sent - expected) < dt.timedelta(minutes=1)


# ─── async_update_tasks ──────────────────────────────────────────────────────


@pytest.mark.feature("task_management")
@pytest.mark.asyncio
async def test_async_update_tasks(grocy_data) -> None:
    """Verify tasks data fetching."""
    task = DummyTask()
    grocy_data.api.tasks.list.return_value = [task]
    result = await grocy_data.async_update_tasks()
    assert result == [task]
    grocy_data.api.tasks.list.assert_called_once()


# ─── async_update_overdue_tasks ───────────────────────────────────────────────


@pytest.mark.feature("task_management")
@pytest.mark.asyncio
async def test_async_update_overdue_tasks(grocy_data) -> None:
    """Verify overdue tasks filtering with date query."""
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


@pytest.mark.feature("shopping_list")
@pytest.mark.asyncio
async def test_async_update_shopping_list(grocy_data) -> None:
    """Verify shopping list data fetching."""
    item = DummyShoppingListProduct()
    grocy_data.api.shopping_list.items.return_value = [item]
    result = await grocy_data.async_update_shopping_list()
    assert result == [item]
    grocy_data.api.shopping_list.items.assert_called_once_with(get_details=True)


# ─── async_update_expiring_products ───────────────────────────────────────────


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_update_expiring_products(grocy_data) -> None:
    """Verify Grocy's own default window is used when due_soon_days is unset."""
    product = DummyProduct()
    grocy_data.api.stock.due_products.return_value = [product]
    result = await grocy_data.async_update_expiring_products()
    assert result == [product]
    grocy_data.api.stock.due_products.assert_called_once_with(
        get_details=True, due_soon_days=None
    )


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_update_expiring_products_uses_due_soon_days(grocy_data) -> None:
    """Verify due_soon_days is passed to the API when configured."""
    grocy_data.due_soon_days = 7
    grocy_data.api.stock.due_products.return_value = []

    result = await grocy_data.async_update_expiring_products()

    assert result == []
    grocy_data.api.stock.due_products.assert_called_once_with(
        get_details=True, due_soon_days=7
    )


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_update_expiring_products_due_soon_days_zero(grocy_data) -> None:
    """Zero is a real window, not an "unset" sentinel, and must be forwarded."""
    grocy_data.due_soon_days = 0
    grocy_data.api.stock.due_products.return_value = []

    result = await grocy_data.async_update_expiring_products()

    assert result == []
    grocy_data.api.stock.due_products.assert_called_once_with(
        get_details=True, due_soon_days=0
    )


# ─── async_update_expired_products ────────────────────────────────────────────


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_update_expired_products(grocy_data) -> None:
    """Verify expired products data fetching."""
    product = DummyProduct()
    grocy_data.api.stock.expired_products.return_value = [product]
    result = await grocy_data.async_update_expired_products()
    assert result == [product]
    grocy_data.api.stock.expired_products.assert_called_once_with(get_details=True)


# ─── async_update_overdue_products ────────────────────────────────────────────


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_update_overdue_products(grocy_data) -> None:
    """Verify overdue products data fetching."""
    product = DummyProduct()
    grocy_data.api.stock.overdue_products.return_value = [product]
    result = await grocy_data.async_update_overdue_products()
    assert result == [product]
    grocy_data.api.stock.overdue_products.assert_called_once_with(get_details=True)


# ─── async_update_missing_products ────────────────────────────────────────────


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_update_missing_products(grocy_data) -> None:
    """Verify missing products data fetching."""
    product = DummyProduct()
    grocy_data.api.stock.missing_products.return_value = [product]
    result = await grocy_data.async_update_missing_products()
    assert result == [product]
    grocy_data.api.stock.missing_products.assert_called_once_with(get_details=True)


# ─── async_update_meal_plan ───────────────────────────────────────────────────


@pytest.mark.feature("meal_planning")
@pytest.mark.asyncio
async def test_async_update_meal_plan_sorts_by_day(grocy_data) -> None:
    """Verify meal plan sorted by date, filters from yesterday."""
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


@pytest.mark.feature("meal_planning")
@pytest.mark.asyncio
async def test_async_update_meal_plan_empty(grocy_data) -> None:
    """Verify empty meal plan handled."""
    grocy_data.api.meal_plan.items.return_value = []
    result = await grocy_data.async_update_meal_plan()
    assert result == []


# ─── async_update_batteries ───────────────────────────────────────────────────


@pytest.mark.feature("battery_tracking")
@pytest.mark.asyncio
async def test_async_update_batteries(grocy_data) -> None:
    """Verify batteries data fetching with details."""
    battery = DummyBattery()
    grocy_data.api.batteries.list.return_value = [battery]
    result = await grocy_data.async_update_batteries()
    assert result == [battery]
    grocy_data.api.batteries.list.assert_called_once_with(get_details=True)


# ─── async_update_overdue_batteries ───────────────────────────────────────────


@pytest.mark.feature("battery_tracking")
@pytest.mark.asyncio
async def test_async_update_overdue_batteries(grocy_data) -> None:
    """Verify overdue batteries data fetching."""
    battery = DummyBattery()
    grocy_data.api.batteries.list.return_value = [battery]
    result = await grocy_data.async_update_overdue_batteries()
    assert result == [battery]
    call_args = grocy_data.api.batteries.list.call_args
    assert call_args.kwargs["get_details"] is True


# ─── async_get_config ─────────────────────────────────────────────────────────


@pytest.mark.feature("cross_cutting")
@pytest.mark.asyncio
async def test_async_get_config(grocy_data) -> None:
    """Verify config retrieval from Grocy API."""
    mock_config = MagicMock()
    grocy_data.api.system.config.return_value = mock_config
    result = await grocy_data.async_get_config()
    assert result is mock_config
    grocy_data.api.system.config.assert_called_once()


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_get_config_stores_due_soon_days(grocy_data) -> None:
    """Verify STOCK_DUE_SOON_DAYS is read from Grocy user settings."""
    grocy_data.api.system.config.return_value = MagicMock()
    grocy_data.api.users.get_setting.return_value = "7"

    await grocy_data.async_get_config()

    assert grocy_data.due_soon_days == 7
    grocy_data.api.users.get_setting.assert_called_once_with("STOCK_DUE_SOON_DAYS")


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_get_config_stores_due_soon_days_lowercase_fallback(
    grocy_data,
) -> None:
    """Verify lowercase stock_due_soon_days is used when uppercase is absent."""
    grocy_data.api.system.config.return_value = MagicMock()
    grocy_data.api.users.get_setting.side_effect = [None, "7"]

    await grocy_data.async_get_config()

    assert grocy_data.due_soon_days == 7
    assert grocy_data.api.users.get_setting.call_count == 2
    grocy_data.api.users.get_setting.assert_any_call("STOCK_DUE_SOON_DAYS")
    grocy_data.api.users.get_setting.assert_any_call("stock_due_soon_days")


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_get_config_stores_due_soon_days_from_dict_payload(
    grocy_data,
) -> None:
    """Verify dict payloads from API/client are parsed correctly."""
    grocy_data.api.system.config.return_value = MagicMock()
    grocy_data.api.users.get_setting.side_effect = [None, {"value": "7"}]

    await grocy_data.async_get_config()

    assert grocy_data.due_soon_days == 7


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_get_config_due_soon_days_defaults_to_none(grocy_data) -> None:
    """Verify due_soon_days is None when STOCK_DUE_SOON_DAYS is absent."""
    grocy_data.api.system.config.return_value = MagicMock()
    grocy_data.api.users.get_setting.side_effect = [None, None]

    await grocy_data.async_get_config()

    assert grocy_data.due_soon_days is None


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_get_config_due_soon_days_handles_invalid_value(
    grocy_data,
) -> None:
    """Verify due_soon_days is None when STOCK_DUE_SOON_DAYS is non-numeric."""
    grocy_data.api.system.config.return_value = MagicMock()
    grocy_data.api.users.get_setting.return_value = "not-a-number"

    await grocy_data.async_get_config()

    assert grocy_data.due_soon_days is None


# ─── image proxy ──────────────────────────────────────────────────────────────

PICTURE = "Y29va2llcy5qcGc="  # base64 of "cookies.jpg"


def _proxy_hass(**data) -> SimpleNamespace:
    """Return a hass with a loaded entry, as the picture view sees it."""
    entry_data = {
        CONF_URL: "https://grocy.local",
        CONF_API_KEY: "key-1",
        CONF_PORT: 9192,
        CONF_VERIFY_SSL: False,
        **data,
    }
    return _hass_with_entries(SimpleNamespace(data=entry_data))


def _hass_with_entries(*entries) -> SimpleNamespace:
    """Return a hass whose loaded Grocy entries are the given ones."""

    def async_loaded_entries(domain: str) -> list:
        assert domain == DOMAIN
        return list(entries)

    return SimpleNamespace(
        config_entries=SimpleNamespace(async_loaded_entries=async_loaded_entries)
    )


def _picture_session(status=200, body=b"img", headers=None) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.headers = headers or {}
    resp.read = AsyncMock(return_value=body)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=resp)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.get.return_value = context
    return session


async def _get_picture(
    hass, picture_type="productpictures", filename=PICTURE, query=None, session=None
):
    session = session or _picture_session()
    with patch(
        "custom_components.grocy.grocy_data.async_get_clientsession",
        return_value=session,
    ) as get_session:
        response = await GrocyPictureView(hass).get(
            SimpleNamespace(query=query or {}), picture_type, filename
        )
    return response, session, get_session


@pytest.mark.feature("image_proxy")
@pytest.mark.asyncio
async def test_async_setup_endpoint_registers_view(hass) -> None:
    """The view is registered by async_setup, so once per run (#72)."""
    hass.http = MagicMock()

    async_setup_endpoint_for_image_proxy(hass)

    hass.http.register_view.assert_called_once()
    assert isinstance(hass.http.register_view.call_args[0][0], GrocyPictureView)


@pytest.mark.feature("image_proxy")
@pytest.mark.asyncio
async def test_picture_view_get_proxies_request() -> None:
    """Verify image proxying with correct headers."""
    body = b"\x89PNG\r\n"
    session = _picture_session(
        body=body,
        headers={
            hdrs.CONTENT_TYPE: "image/png",
            hdrs.CONTENT_LENGTH: str(len(body)),
            "X-Custom-Header": "should-be-excluded",
        },
    )

    response, _, _ = await _get_picture(
        _proxy_hass(), query={"width": "200"}, session=session
    )

    call_url = session.get.call_args[0][0]
    assert call_url == (
        f"https://grocy.local:9192/api/files/productpictures/{PICTURE}"
        "?force_serve_as=picture&best_fit_width=200"
    )
    assert session.get.call_args[1]["headers"]["GROCY-API-KEY"] == "key-1"
    assert response.body == body
    assert hdrs.CONTENT_TYPE in response.headers
    assert "X-Custom-Header" not in response.headers


@pytest.mark.feature("image_proxy")
@pytest.mark.asyncio
async def test_picture_view_uses_path_and_default_width() -> None:
    """Verify URL path handling for subpath installations and width 400."""
    hass = _proxy_hass(**{CONF_URL: "https://grocy.local/grocy", CONF_PORT: 443})

    _, session, _ = await _get_picture(hass, "recipepictures")

    assert session.get.call_args[0][0].startswith(
        "https://grocy.local:443/grocy/api/files/recipepictures/"
    )
    assert session.get.call_args[0][0].endswith("best_fit_width=400")


@pytest.mark.feature("image_proxy")
@pytest.mark.asyncio
async def test_picture_view_reads_the_current_entry() -> None:
    """A changed URL or API key applies without a restart (#72)."""
    hass = _proxy_hass()
    await _get_picture(hass)

    entry = hass.config_entries.async_loaded_entries(DOMAIN)[0]
    entry.data = {
        **entry.data,
        CONF_URL: "https://new-grocy.local",
        CONF_API_KEY: "key-2",
    }
    _, session, _ = await _get_picture(hass)

    assert session.get.call_args[0][0].startswith("https://new-grocy.local:9192/")
    assert session.get.call_args[1]["headers"]["GROCY-API-KEY"] == "key-2"


@pytest.mark.feature("image_proxy")
@pytest.mark.asyncio
@pytest.mark.parametrize("verify_ssl", [True, False])
async def test_picture_view_uses_verify_ssl(verify_ssl) -> None:
    """The proxy honours verify_ssl, as the calendar does (#73)."""
    _, _, get_session = await _get_picture(_proxy_hass(**{CONF_VERIFY_SSL: verify_ssl}))

    assert get_session.call_args.kwargs["verify_ssl"] is verify_ssl


@pytest.mark.feature("image_proxy")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("picture_type", "filename"),
    [
        ("userfiles", PICTURE),
        ("equipmentmanuals", PICTURE),
        ("productpictures", "..%2F..%2Fapi%2Fobjects"),
        ("productpictures", "not base64!"),
        ("productpictures", "YS9iLmpwZw=="),  # base64 of "a/b.jpg"
    ],
)
async def test_picture_view_rejects_other_groups_and_names(
    picture_type, filename
) -> None:
    """Only pictures can be read, and only by a plain file name."""
    session = _picture_session()

    with pytest.raises(web.HTTPNotFound):
        await _get_picture(_proxy_hass(), picture_type, filename, session=session)

    session.get.assert_not_called()


@pytest.mark.feature("image_proxy")
@pytest.mark.asyncio
async def test_picture_view_without_loaded_entry_is_not_found() -> None:
    """After the entry is unloaded, the view answers 404."""
    with pytest.raises(web.HTTPNotFound):
        await _get_picture(_hass_with_entries())


@pytest.mark.feature("image_proxy")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("width", "expected"), [("foo", 400), ("99999", 2000), ("-5", 1)]
)
async def test_picture_view_reads_width_safely(width, expected) -> None:
    """A bad width gives the default or the limit, not an error."""
    _, session, _ = await _get_picture(_proxy_hass(), query={"width": width})

    assert session.get.call_args[0][0].endswith(f"best_fit_width={expected}")


@pytest.mark.feature("image_proxy")
@pytest.mark.asyncio
async def test_picture_view_maps_grocy_errors() -> None:
    """A Grocy 404 is a 404; a connection error is a 502, not a traceback."""
    with pytest.raises(web.HTTPNotFound):
        await _get_picture(_proxy_hass(), session=_picture_session(status=404))

    for error in (ClientError(), TimeoutError()):
        session = MagicMock()
        session.get.side_effect = error
        with pytest.raises(web.HTTPBadGateway):
            await _get_picture(_proxy_hass(), session=session)


@pytest.mark.feature("image_proxy")
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("pizza.jpg", "/api/grocy/recipepictures/cGl6emEuanBn"),
        ("борщ.jpg", "/api/grocy/recipepictures/0LHQvtGA0YkuanBn"),
        ("Käsespätzle.jpg", "/api/grocy/recipepictures/S8Okc2VzcMOkdHpsZS5qcGc="),
        ("проверка-ü 1.txt", None),  # base64 contains "/", Grocy cannot route it
        (None, None),
    ],
)
def test_recipe_picture_url_encodes_utf8(name, expected) -> None:
    """Non-ASCII picture names no longer crash the attributes (#74)."""
    assert recipe_picture_url(name) == expected


@pytest.mark.feature("image_proxy")
def test_picture_view_requires_no_auth() -> None:
    """Verify no authentication required."""
    assert GrocyPictureView.requires_auth is False


@pytest.mark.feature("image_proxy")
def test_picture_view_url_pattern() -> None:
    """Verify URL pattern contains expected placeholders."""
    assert "{picture_type}" in GrocyPictureView.url
    assert "{filename}" in GrocyPictureView.url


# ─── All entity keys are mapped ──────────────────────────────────────────────


# ─── async_update_recipes ───────────────────────────────────────────────


@pytest.mark.feature("meal_planning")
@pytest.mark.asyncio
async def test_async_update_recipes(grocy_data) -> None:
    """Verify recipe data fetching and wrapping."""
    from grocy.data_models.generic import EntityType
    from grocy.grocy_api_client import RecipeFulfillmentResponse

    recipe_dict = {
        "id": 1,
        "name": "Pizza",
        "description": "Tasty",
        "picture_file_name": "pizza.jpg",
        "type": "normal",
    }
    grocy_data.api.generic.list.return_value = [recipe_dict]

    fulfillment_response = RecipeFulfillmentResponse(
        recipe_id=1,
        need_fulfilled=True,
        need_fulfilled_with_shopping_list=False,
    )
    grocy_data.api.recipes.all_fulfillment.return_value = [fulfillment_response]

    result = await grocy_data.async_update_recipes()

    assert len(result) == 1
    wrapped = result[0]
    assert wrapped.recipe == recipe_dict
    assert wrapped.all_ingredients_in_stock is True
    assert wrapped.picture_url == "/api/grocy/recipepictures/cGl6emEuanBn"
    assert wrapped.as_dict() == {
        "id": 1,
        "name": "Pizza",
        "description": "Tasty",
        "picture_file_name": "pizza.jpg",
        "all_ingredients_in_stock": True,
        "picture_url": "/api/grocy/recipepictures/cGl6emEuanBn",
        "type": "normal",
        "url": "https://exemple.com/recipes?recipe=1#fullscreen",
    }

    grocy_data.api.generic.list.assert_called_once_with(EntityType.RECIPES)
    grocy_data.api.recipes.all_fulfillment.assert_called_once()


@pytest.mark.feature("cross_cutting")
def test_all_entity_keys_have_update_methods(hass, mock_grocy) -> None:
    """Verify all 14 entity keys mapped to update methods."""
    hass.async_add_executor_job = AsyncMock()
    data = GrocyData(hass, mock_grocy, "https://exemple.com")
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
        ATTR_RECIPES,
    }
    assert set(data.entity_update_method.keys()) == expected_keys
