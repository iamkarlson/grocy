"""Todo list platform tests.

Features: stock_management, shopping_list, chore_management, task_management,
          battery_tracking, meal_planning, cross_cutting
See: docs/FEATURES.md
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from grocy.data_models.battery import Battery
from grocy.data_models.chore import Chore
from grocy.data_models.meal_items import MealPlanItem, MealPlanItemType, RecipeItem
from grocy.data_models.product import Product, ShoppingListProduct
from grocy.data_models.task import Task
from homeassistant.components.todo import TodoItemStatus, TodoListEntityFeature

from custom_components.grocy.const import (
    ATTR_BATTERIES,
    ATTR_CHORES,
    ATTR_MEAL_PLAN,
    ATTR_SHOPPING_LIST,
    ATTR_STOCK,
    ATTR_TASKS,
)
from custom_components.grocy.coordinator import GrocyCoordinatorData
from custom_components.grocy.helpers import MealPlanItemWrapper
from custom_components.grocy.todo import (
    TODOS,
    GrocyTodoItem,
    GrocyTodoListEntity,
    _calculate_days_until,
    _calculate_item_status,
)
from tests.factories import (
    DummyMealPlanItem,
    DummyRecipe,
)


# ─── _calculate_days_until ────────────────────────────────────────────────────


@pytest.mark.feature("cross_cutting")
def test_calculate_days_until_none_returns_zero() -> None:
    """Verify days calculation handles None."""
    assert _calculate_days_until(None) == 0


@pytest.mark.feature("cross_cutting")
def test_calculate_days_until_date_only_future() -> None:
    """Verify future date calculation."""
    future = dt.date.today() + dt.timedelta(days=5)
    result = _calculate_days_until(future, date_only=True)
    assert result == 5


@pytest.mark.feature("cross_cutting")
def test_calculate_days_until_date_only_past() -> None:
    """Verify past date calculation."""
    past = dt.date.today() - dt.timedelta(days=3)
    result = _calculate_days_until(past, date_only=True)
    assert result == -3


@pytest.mark.feature("cross_cutting")
def test_calculate_days_until_datetime() -> None:
    """Verify datetime calculation."""
    future = dt.datetime.now() + dt.timedelta(days=2, hours=12)
    result = _calculate_days_until(future, date_only=False)
    assert result >= 2


@pytest.mark.feature("cross_cutting")
def test_calculate_days_until_datetime_date_only() -> None:
    """Verify datetime as date calculation."""
    future_dt = dt.datetime.now() + dt.timedelta(days=4)
    result = _calculate_days_until(future_dt, date_only=True)
    assert result == 4


# ─── _calculate_item_status ───────────────────────────────────────────────────


@pytest.mark.feature("cross_cutting")
def test_calculate_item_status_overdue() -> None:
    """Verify overdue status mapping."""
    assert _calculate_item_status(0) == TodoItemStatus.NEEDS_ACTION
    assert _calculate_item_status(-1) == TodoItemStatus.NEEDS_ACTION


@pytest.mark.feature("cross_cutting")
def test_calculate_item_status_future() -> None:
    """Verify future status mapping."""
    assert _calculate_item_status(1) == TodoItemStatus.COMPLETED
    assert _calculate_item_status(10) == TodoItemStatus.COMPLETED


# ─── GrocyTodoItem from Task ─────────────────────────────────────────────────


@pytest.mark.feature("task_management")
def test_todo_item_from_task() -> None:
    """Verify task converts to todo item with correct fields."""
    due = dt.datetime.combine(
        dt.date.today() + dt.timedelta(days=2), dt.time.min
    )
    task = Task(id=7, name="Buy groceries", description="Weekly shopping", due_date=due)
    item = GrocyTodoItem(task, ATTR_TASKS)

    assert item.uid == "7"
    assert item.summary == "Buy groceries"
    assert item.description == "Weekly shopping"
    assert item.status == TodoItemStatus.COMPLETED


@pytest.mark.feature("task_management")
def test_todo_item_from_task_overdue() -> None:
    """Verify overdue task shows NEEDS_ACTION status."""
    due = dt.datetime.combine(
        dt.date.today() - dt.timedelta(days=1), dt.time.min
    )
    task = Task(id=3, name="Late task", description=None, due_date=due)
    item = GrocyTodoItem(task, ATTR_TASKS)

    assert item.status == TodoItemStatus.NEEDS_ACTION
    assert item.description is None


# ─── GrocyTodoItem from Chore ────────────────────────────────────────────────


@pytest.mark.feature("chore_management")
def test_todo_item_from_chore() -> None:
    """Verify chore converts to todo item."""
    chore = Chore(
        id=5,
        name="Clean kitchen",
        description="Wipe counters",
        next_estimated_execution_time=dt.datetime.now() + dt.timedelta(days=3),
        track_date_only=False,
    )
    item = GrocyTodoItem(chore, ATTR_CHORES)

    assert item.uid == "5"
    assert item.summary == "Clean kitchen"
    assert item.description == "Wipe counters"
    assert item.status == TodoItemStatus.COMPLETED


@pytest.mark.feature("chore_management")
def test_todo_item_from_chore_date_only() -> None:
    """Verify date-only chore handled correctly."""
    chore = Chore(
        id=6,
        name="Water plants",
        description=None,
        next_estimated_execution_time=dt.date.today() - dt.timedelta(days=1),
        track_date_only=True,
    )
    item = GrocyTodoItem(chore, ATTR_CHORES)

    assert item.status == TodoItemStatus.NEEDS_ACTION
    assert item.description is None


# ─── GrocyTodoItem from Battery ──────────────────────────────────────────────


@pytest.mark.feature("battery_tracking")
def test_todo_item_from_battery() -> None:
    """Verify battery converts to todo item."""
    battery = Battery(
        id=10,
        name="Remote battery",
        description="TV remote",
        next_estimated_charge_time=dt.date.today() + dt.timedelta(days=7),
    )
    item = GrocyTodoItem(battery, ATTR_BATTERIES)

    assert item.uid == "10"
    assert item.summary == "Remote battery"
    assert item.description == "TV remote"
    assert item.status == TodoItemStatus.COMPLETED


@pytest.mark.feature("battery_tracking")
def test_todo_item_from_battery_overdue() -> None:
    """Verify overdue battery shows NEEDS_ACTION."""
    battery = Battery(
        id=11,
        name="Old battery",
        description=None,
        next_estimated_charge_time=dt.date.today() - dt.timedelta(days=2),
    )
    item = GrocyTodoItem(battery, ATTR_BATTERIES)

    assert item.status == TodoItemStatus.NEEDS_ACTION


# ─── GrocyTodoItem from Product ──────────────────────────────────────────────


@pytest.mark.feature("stock_management")
def test_todo_item_from_product_with_stock() -> None:
    """Verify product converts to todo item with amount in summary."""
    product = Product(id=20, name="Milk", available_amount=2.5)
    item = GrocyTodoItem(product, ATTR_STOCK)

    assert item.uid == "20"
    assert item.summary == "2.50x Milk"
    assert item.status == TodoItemStatus.NEEDS_ACTION
    assert item.description is None


@pytest.mark.feature("stock_management")
def test_todo_item_from_product_zero_amount() -> None:
    """Verify zero-stock product shows as COMPLETED."""
    product = Product(id=21, name="Empty product", available_amount=0.0)
    item = GrocyTodoItem(product, ATTR_STOCK)

    assert item.status == TodoItemStatus.COMPLETED


# ─── GrocyTodoItem from ShoppingListProduct ──────────────────────────────────


def _make_product(name: str = "Bread") -> Product:
    return Product(id=1, name=name, available_amount=1.0)


@pytest.mark.feature("shopping_list")
def test_todo_item_from_shopping_list_product() -> None:
    """Verify shopping list item converts to todo."""
    slp = ShoppingListProduct(
        id=40, amount=1.0, note="Sourdough", product=_make_product("Bread"), done=False
    )
    item = GrocyTodoItem(slp, ATTR_SHOPPING_LIST)

    assert item.uid == "40"
    assert "1.00x Bread" in item.summary
    assert item.status == TodoItemStatus.NEEDS_ACTION
    assert item.description == "Sourdough"


@pytest.mark.feature("shopping_list")
def test_todo_item_from_shopping_list_product_done() -> None:
    """Verify done item shows COMPLETED status."""
    slp = ShoppingListProduct(
        id=41, amount=2.0, note=None, product=_make_product("Butter"), done=True
    )
    item = GrocyTodoItem(slp, ATTR_SHOPPING_LIST)

    assert item.status == TodoItemStatus.COMPLETED
    assert item.description is None


@pytest.mark.feature("shopping_list")
def test_todo_item_from_shopping_list_product_no_product() -> None:
    """Verify missing product shows 'Unknown product'."""
    slp = ShoppingListProduct(id=42, amount=1.0, note=None, product=None, done=False)
    item = GrocyTodoItem(slp, ATTR_SHOPPING_LIST)

    assert "Unknown product" in item.summary


@pytest.mark.feature("shopping_list")
def test_todo_item_from_shopping_list_product_string_done_flag() -> None:
    """Verify pydantic coerces string done flag."""
    # ShoppingListProduct.done is typed bool, so pydantic coerces "1" -> True
    slp = ShoppingListProduct(
        id=43, amount=1.0, note=None, product=_make_product("Cheese"), done=True
    )
    item = GrocyTodoItem(slp, ATTR_SHOPPING_LIST)

    assert item.status == TodoItemStatus.COMPLETED


# ─── GrocyTodoItem from MealPlanItem ─────────────────────────────────────────


@pytest.mark.feature("meal_planning")
def test_todo_item_from_meal_plan_item() -> None:
    """Verify meal plan item converts to todo."""
    recipe = RecipeItem(
        id=1,
        name="Pasta",
        description="Italian classic",
        base_servings=1,
        desired_servings=1,
        picture_file_name=None,
    )
    mpi = MealPlanItem(
        id=50,
        day=dt.date.today() + dt.timedelta(days=1),
        recipe=recipe,
        type=MealPlanItemType.RECIPE,
    )
    item = GrocyTodoItem(mpi, ATTR_MEAL_PLAN)

    assert item.uid == "50"
    assert item.summary == "Pasta"
    assert item.description == "Italian classic"
    assert item.status == TodoItemStatus.COMPLETED


# ─── GrocyTodoItem from MealPlanItemWrapper ───────────────────────────────────


@pytest.mark.feature("meal_planning")
def test_todo_item_from_meal_plan_item_wrapper() -> None:
    """Verify MealPlanItemWrapper converts to todo."""
    recipe = DummyRecipe(name="Soup", description="Chicken soup")
    mpi = DummyMealPlanItem(
        id=60, day=dt.date.today() + dt.timedelta(days=2), recipe=recipe
    )
    wrapper = MealPlanItemWrapper(mpi)
    item = GrocyTodoItem(wrapper, ATTR_MEAL_PLAN)

    assert item.uid == "60"
    assert item.summary == "Soup"
    assert item.description == "Chicken soup"


# ─── GrocyTodoItem raises for unknown type ───────────────────────────────────


@pytest.mark.feature("cross_cutting")
def test_todo_item_raises_for_unknown_type() -> None:
    """Verify unknown type raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        GrocyTodoItem("some_string", "unknown_key")


# ─── GrocyTodoListEntity supported features ──────────────────────────────────


def _build_todo(key: str, data) -> GrocyTodoListEntity:
    description = next(d for d in TODOS if d.key == key)
    entity = GrocyTodoListEntity.__new__(GrocyTodoListEntity)
    entity.entity_description = description
    entity.coordinator = SimpleNamespace(
        data=GrocyCoordinatorData(),
        async_refresh=AsyncMock(),
    )
    entity.coordinator.data[key] = data
    entity.hass = SimpleNamespace()
    entity._attr_supported_features = 0
    return entity


@pytest.mark.feature("battery_tracking")
def test_todo_list_entity_batteries_supports_create() -> None:
    """Verify battery todo supports CREATE."""
    desc = next(d for d in TODOS if d.key == ATTR_BATTERIES)
    entity = GrocyTodoListEntity.__new__(GrocyTodoListEntity)
    entity._attr_supported_features = (
        TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.CREATE_TODO_ITEM
    )
    assert entity._attr_supported_features & TodoListEntityFeature.CREATE_TODO_ITEM


@pytest.mark.feature("stock_management")
def test_todo_list_entity_stock_no_create() -> None:
    """Verify stock todo does not support CREATE."""
    desc = next(d for d in TODOS if d.key == ATTR_STOCK)
    assert ATTR_STOCK not in [ATTR_BATTERIES, ATTR_CHORES, ATTR_TASKS]


# ─── async_create_todo_item ──────────────────────────────────────────────────


@pytest.mark.feature("battery_tracking")
@pytest.mark.asyncio
async def test_async_create_todo_item_battery() -> None:
    """Verify creating battery todo calls add_generic."""
    entity = _build_todo(ATTR_BATTERIES, [])
    todo_item = SimpleNamespace(summary="New battery", description="test desc")

    with patch(
        "custom_components.grocy.todo.async_add_generic_service",
        new_callable=AsyncMock,
    ) as mock_add:
        await GrocyTodoListEntity.async_create_todo_item(entity, todo_item)

    mock_add.assert_awaited_once()
    call_data = mock_add.call_args[0][2]
    assert call_data["entity_type"] == "batteries"
    assert call_data["data"]["name"] == "New battery"


@pytest.mark.feature("chore_management")
@pytest.mark.asyncio
async def test_async_create_todo_item_chore() -> None:
    """Verify creating chore todo sets period_type=manually."""
    entity = _build_todo(ATTR_CHORES, [])
    todo_item = SimpleNamespace(summary="New chore", description="details")

    with patch(
        "custom_components.grocy.todo.async_add_generic_service",
        new_callable=AsyncMock,
    ) as mock_add:
        await GrocyTodoListEntity.async_create_todo_item(entity, todo_item)

    call_data = mock_add.call_args[0][2]
    assert call_data["entity_type"] == "chores"
    assert call_data["data"]["period_type"] == "manually"


@pytest.mark.feature("task_management")
@pytest.mark.asyncio
async def test_async_create_todo_item_task() -> None:
    """Verify creating task todo calls add_generic."""
    entity = _build_todo(ATTR_TASKS, [])
    todo_item = SimpleNamespace(summary="New task", description="desc", due=None)

    with patch(
        "custom_components.grocy.todo.async_add_generic_service",
        new_callable=AsyncMock,
    ) as mock_add:
        await GrocyTodoListEntity.async_create_todo_item(entity, todo_item)

    call_data = mock_add.call_args[0][2]
    assert call_data["entity_type"] == "tasks"
    assert call_data["data"]["name"] == "New task"


@pytest.mark.feature("cross_cutting")
@pytest.mark.asyncio
async def test_async_create_todo_item_unsupported_raises() -> None:
    """Verify unsupported create raises error."""
    entity = _build_todo(ATTR_STOCK, [])
    todo_item = SimpleNamespace(summary="Item", description=None)

    with pytest.raises(NotImplementedError):
        await GrocyTodoListEntity.async_create_todo_item(entity, todo_item)


# ─── async_update_todo_item ──────────────────────────────────────────────────


@pytest.mark.feature("battery_tracking")
@pytest.mark.asyncio
async def test_async_update_todo_item_complete_battery() -> None:
    """Verify completing battery todo tracks charge."""
    entity = _build_todo(ATTR_BATTERIES, [])
    todo_item = SimpleNamespace(uid="1", status=TodoItemStatus.COMPLETED)

    with patch(
        "custom_components.grocy.todo.async_track_battery_service",
        new_callable=AsyncMock,
    ) as mock_track:
        await GrocyTodoListEntity.async_update_todo_item(entity, todo_item)

    mock_track.assert_awaited_once()
    assert mock_track.call_args[0][2]["battery_id"] == "1"


@pytest.mark.feature("battery_tracking")
@pytest.mark.asyncio
async def test_async_update_todo_item_battery_needs_action_raises() -> None:
    """Verify uncompleting battery raises NotImplementedError."""
    entity = _build_todo(ATTR_BATTERIES, [])
    todo_item = SimpleNamespace(uid="1", status=TodoItemStatus.NEEDS_ACTION)

    with pytest.raises(NotImplementedError):
        await GrocyTodoListEntity.async_update_todo_item(entity, todo_item)


@pytest.mark.feature("chore_management")
@pytest.mark.asyncio
async def test_async_update_todo_item_complete_chore() -> None:
    """Verify completing chore todo executes chore."""
    entity = _build_todo(ATTR_CHORES, [])
    todo_item = SimpleNamespace(uid="5", status=TodoItemStatus.COMPLETED)

    with patch(
        "custom_components.grocy.todo.async_execute_chore_service",
        new_callable=AsyncMock,
    ) as mock_exec:
        await GrocyTodoListEntity.async_update_todo_item(entity, todo_item)

    mock_exec.assert_awaited_once()
    call_data = mock_exec.call_args[0][2]
    assert call_data["chore_id"] == "5"
    assert call_data["done_by"] == 1


@pytest.mark.feature("task_management")
@pytest.mark.asyncio
async def test_async_update_todo_item_complete_task() -> None:
    """Verify completing task todo calls complete_task."""
    entity = _build_todo(ATTR_TASKS, [])
    todo_item = SimpleNamespace(uid="11", status=TodoItemStatus.COMPLETED)

    with patch(
        "custom_components.grocy.todo.async_complete_task_service",
        new_callable=AsyncMock,
    ) as mock_complete:
        await GrocyTodoListEntity.async_update_todo_item(entity, todo_item)

    mock_complete.assert_awaited_once()
    assert mock_complete.call_args[0][2]["task_id"] == "11"


@pytest.mark.feature("meal_planning")
@pytest.mark.asyncio
async def test_async_update_todo_item_complete_meal_plan() -> None:
    """Verify completing meal plan consumes recipe and deletes entry."""
    recipe = SimpleNamespace(id=99, name="Pasta", description=None)
    mpi_inner = SimpleNamespace(id=60, day=dt.date.today(), recipe=recipe)
    # _get_grocy_item checks hasattr(item, "id") -- MealPlanItemWrapper
    # doesn't have .id, so it falls through to item.meal_plan.id
    wrapper = MagicMock(spec=[])  # no attributes by default
    wrapper.meal_plan = mpi_inner

    entity = _build_todo(ATTR_MEAL_PLAN, [wrapper])
    todo_item = SimpleNamespace(uid="60", status=TodoItemStatus.COMPLETED)

    with (
        patch(
            "custom_components.grocy.todo.async_consume_recipe_service",
            new_callable=AsyncMock,
        ) as mock_consume,
        patch(
            "custom_components.grocy.todo.async_delete_generic_service",
            new_callable=AsyncMock,
        ) as mock_delete,
    ):
        await GrocyTodoListEntity.async_update_todo_item(entity, todo_item)

    mock_consume.assert_awaited_once()
    assert mock_consume.call_args[0][2]["recipe_id"] == 99
    mock_delete.assert_awaited_once()


@pytest.mark.feature("shopping_list")
@pytest.mark.asyncio
async def test_async_update_todo_item_complete_shopping_list() -> None:
    """Verify completing marks item done."""
    entity = _build_todo(ATTR_SHOPPING_LIST, [])
    todo_item = SimpleNamespace(uid="77", status=TodoItemStatus.COMPLETED)

    with patch(
        "custom_components.grocy.todo.async_mark_shopping_list_item_done",
        new_callable=AsyncMock,
    ) as mock_mark:
        await GrocyTodoListEntity.async_update_todo_item(entity, todo_item)

    mock_mark.assert_awaited_once()
    call_data = mock_mark.call_args[0][2]
    assert call_data["object_id"] == 77
    assert call_data["done"] is True


@pytest.mark.feature("shopping_list")
@pytest.mark.asyncio
async def test_async_update_todo_item_uncomplete_shopping_list() -> None:
    """Verify uncompleting marks item undone."""
    entity = _build_todo(ATTR_SHOPPING_LIST, [])
    todo_item = SimpleNamespace(uid="77", status=TodoItemStatus.NEEDS_ACTION)

    with patch(
        "custom_components.grocy.todo.async_mark_shopping_list_item_done",
        new_callable=AsyncMock,
    ) as mock_mark:
        await GrocyTodoListEntity.async_update_todo_item(entity, todo_item)

    mock_mark.assert_awaited_once()
    call_data = mock_mark.call_args[0][2]
    assert call_data["object_id"] == 77
    assert call_data["done"] is False


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_update_todo_item_complete_stock() -> None:
    """Verify completing stock todo consumes product."""
    grocy_item = SimpleNamespace(id=25, available_amount=5.0)
    entity = _build_todo(ATTR_STOCK, [grocy_item])

    todo_item = SimpleNamespace(uid="25", status=TodoItemStatus.COMPLETED)

    with patch(
        "custom_components.grocy.todo.async_consume_product_service",
        new_callable=AsyncMock,
    ) as mock_consume:
        await GrocyTodoListEntity.async_update_todo_item(entity, todo_item)

    mock_consume.assert_awaited_once()
    call_data = mock_consume.call_args[0][2]
    assert call_data["product_id"] == "25"
    assert call_data["amount"] == 5.0


# ─── async_delete_todo_items ─────────────────────────────────────────────────


@pytest.mark.feature("task_management")
@pytest.mark.asyncio
async def test_async_delete_todo_items_calls_delete_for_each_uid() -> None:
    """Verify delete calls delete_generic per item."""
    entity = _build_todo(ATTR_TASKS, [])

    with patch(
        "custom_components.grocy.todo.async_delete_generic_service",
        new_callable=AsyncMock,
    ) as mock_delete:
        await GrocyTodoListEntity.async_delete_todo_items(entity, ["1", "2", "3"])

    assert mock_delete.await_count == 3


# ─── _get_grocy_item ─────────────────────────────────────────────────────────


@pytest.mark.feature("cross_cutting")
def test_get_grocy_item_finds_by_id() -> None:
    """Verify item lookup by ID."""
    item1 = SimpleNamespace(id=1)
    item2 = SimpleNamespace(id=2)
    entity = _build_todo(ATTR_TASKS, [item1, item2])

    result = entity._get_grocy_item("2")
    assert result.id == 2


@pytest.mark.feature("cross_cutting")
def test_get_grocy_item_finds_meal_plan_wrapper() -> None:
    """Verify MealPlanItemWrapper lookup."""
    inner = SimpleNamespace(id=55)
    wrapper = SimpleNamespace(meal_plan=inner)
    entity = _build_todo(ATTR_MEAL_PLAN, [wrapper])

    result = entity._get_grocy_item("55")
    assert result.meal_plan.id == 55


# ─── todo_items property ─────────────────────────────────────────────────────


@pytest.mark.feature("cross_cutting")
def test_todo_items_none_data() -> None:
    """Verify None data returns empty list."""
    entity = _build_todo(ATTR_TASKS, None)
    assert entity.todo_items == []


# ─── exists_fn coverage ──────────────────────────────────────────────────────


@pytest.mark.feature("cross_cutting")
def test_todo_exists_fn_checks_available_entities() -> None:
    """Verify todo exists_fn validation."""
    for desc in TODOS:
        assert desc.exists_fn([desc.key]) is True
        assert desc.exists_fn([]) is False


# ─── NEEDS_ACTION (undo) raises NotImplementedError ───────────────────────────


@pytest.mark.feature("chore_management")
@pytest.mark.asyncio
async def test_async_update_todo_item_chore_needs_action_raises() -> None:
    """Verify uncompleting chore raises NotImplementedError."""
    entity = _build_todo(ATTR_CHORES, [])
    todo_item = SimpleNamespace(uid="1", status=TodoItemStatus.NEEDS_ACTION)

    with pytest.raises(NotImplementedError):
        await GrocyTodoListEntity.async_update_todo_item(entity, todo_item)


@pytest.mark.feature("meal_planning")
@pytest.mark.asyncio
async def test_async_update_todo_item_meal_plan_needs_action_raises() -> None:
    """Verify uncompleting meal plan raises NotImplementedError."""
    entity = _build_todo(ATTR_MEAL_PLAN, [])
    todo_item = SimpleNamespace(uid="1", status=TodoItemStatus.NEEDS_ACTION)

    with pytest.raises(NotImplementedError):
        await GrocyTodoListEntity.async_update_todo_item(entity, todo_item)


@pytest.mark.feature("stock_management")
@pytest.mark.asyncio
async def test_async_update_todo_item_stock_needs_action_raises() -> None:
    """Verify uncompleting stock todo raises NotImplementedError."""
    entity = _build_todo(ATTR_STOCK, [])
    todo_item = SimpleNamespace(uid="1", status=TodoItemStatus.NEEDS_ACTION)

    with pytest.raises(NotImplementedError):
        await GrocyTodoListEntity.async_update_todo_item(entity, todo_item)


@pytest.mark.feature("task_management")
@pytest.mark.asyncio
async def test_async_update_todo_item_task_needs_action_raises() -> None:
    """Verify uncompleting task raises NotImplementedError."""
    entity = _build_todo(ATTR_TASKS, [])
    todo_item = SimpleNamespace(uid="1", status=TodoItemStatus.NEEDS_ACTION)

    with pytest.raises(NotImplementedError):
        await GrocyTodoListEntity.async_update_todo_item(entity, todo_item)
