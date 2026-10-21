"""
Todo list platform tests.

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
from homeassistant.components.todo.services import _async_remove_completed_items
from homeassistant.exceptions import HomeAssistantError

from custom_components.grocy.const import (
    ATTR_BATTERIES,
    ATTR_CHORES,
    ATTR_MEAL_PLAN,
    ATTR_SHOPPING_LIST,
    ATTR_STOCK,
    ATTR_TASKS,
    CHORE_DONE_BY_API_KEY_OWNER,
    CHORE_DONE_BY_ASSIGNED_USER,
    CONF_CHORE_DONE_BY,
)
from custom_components.grocy.coordinator import GrocyCoordinatorData
from custom_components.grocy.helpers import MealPlanItemWrapper
from custom_components.grocy.todo import (
    TODOS,
    GrocyTodoItem,
    GrocyTodoListEntity,
)
from tests.factories import (
    DummyMealPlanItem,
    DummyRecipe,
)

# ─── GrocyTodoItem from Task ─────────────────────────────────────────────────


@pytest.mark.feature("task_management")
def test_todo_item_from_task() -> None:
    """Verify task converts to todo item with correct fields."""
    due = dt.datetime.combine(dt.date.today() + dt.timedelta(days=2), dt.time.min)
    task = Task(id=7, name="Buy groceries", description="Weekly shopping", due_date=due)
    item = GrocyTodoItem(task, ATTR_TASKS)

    assert item.uid == "7"
    assert item.summary == "Buy groceries"
    assert item.description == "Weekly shopping"
    assert item.status == TodoItemStatus.NEEDS_ACTION


@pytest.mark.feature("task_management")
def test_todo_item_from_task_overdue() -> None:
    """Verify overdue task shows NEEDS_ACTION status."""
    due = dt.datetime.combine(dt.date.today() - dt.timedelta(days=1), dt.time.min)
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
    assert item.status == TodoItemStatus.NEEDS_ACTION


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
    assert item.status == TodoItemStatus.NEEDS_ACTION


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
    assert item.status == TodoItemStatus.NEEDS_ACTION


@pytest.mark.feature("meal_planning")
def test_todo_item_from_meal_plan_item_missing_recipe() -> None:
    """Verify meal plan item with missing recipe does not raise and uses fallback."""
    mpi = MealPlanItem(
        id=51,
        day=dt.date.today() + dt.timedelta(days=1),
        recipe=None,
        type=MealPlanItemType.RECIPE,
    )
    item = GrocyTodoItem(mpi, ATTR_MEAL_PLAN)

    assert item.uid == "51"
    assert item.summary == "Unknown recipe"
    assert item.description is None


@pytest.mark.feature("meal_planning")
@pytest.mark.parametrize("item_type", [*MealPlanItemType, "dessert"])
def test_todo_item_from_meal_plan_item_any_type(
    item_type: MealPlanItemType | str,
) -> None:
    """Enum types and unknown string types both become a todo item (#69)."""
    mpi = MealPlanItem(
        id=52,
        day=dt.date.today() + dt.timedelta(days=1),
        recipe=None,
        type=item_type,
    )

    assert mpi.type == item_type
    assert isinstance(mpi.type, MealPlanItemType) == (item_type != "dessert")

    item = GrocyTodoItem(mpi, ATTR_MEAL_PLAN)

    assert item.uid == "52"
    assert item.summary == "Unknown recipe"


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


def _build_todo(key: str, data, entry_data: dict | None = None) -> GrocyTodoListEntity:
    description = next(d for d in TODOS if d.key == key)
    entity = GrocyTodoListEntity.__new__(GrocyTodoListEntity)
    entity.entity_description = description
    entity.coordinator = SimpleNamespace(
        data=GrocyCoordinatorData(),
        async_refresh=AsyncMock(),
        config_entry=SimpleNamespace(data=entry_data or {}),
    )
    entity.coordinator.data[key] = data
    entity.hass = SimpleNamespace()
    entity._attr_supported_features = 0
    return entity


def _features_for(key: str) -> TodoListEntityFeature:
    desc = next(d for d in TODOS if d.key == key)
    entity = GrocyTodoListEntity(MagicMock(), desc, MagicMock(entry_id="test"))
    return entity.supported_features


@pytest.mark.feature("battery_tracking")
def test_todo_list_entity_batteries_supports_create() -> None:
    """Battery, chore and task lists accept new items; the constructor decides."""
    for key in (ATTR_BATTERIES, ATTR_CHORES, ATTR_TASKS):
        assert _features_for(key) & TodoListEntityFeature.CREATE_TODO_ITEM, key


@pytest.mark.feature("stock_management")
def test_todo_list_entity_stock_no_create() -> None:
    """Stock, shopping list and meal plan lists do not offer CREATE."""
    for key in (ATTR_STOCK, ATTR_SHOPPING_LIST, ATTR_MEAL_PLAN):
        features = _features_for(key)
        assert not features & TodoListEntityFeature.CREATE_TODO_ITEM, key
        assert features & TodoListEntityFeature.UPDATE_TODO_ITEM, key


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
    # Without done_by, Grocy logs the chore for the owner of the API key (#81).
    assert "done_by" not in call_data


@pytest.mark.feature("chore_management")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("option", "assigned_user", "expected"),
    [
        (CHORE_DONE_BY_API_KEY_OWNER, 3, None),
        (CHORE_DONE_BY_ASSIGNED_USER, 3, 3),
        (CHORE_DONE_BY_ASSIGNED_USER, None, None),
    ],
)
async def test_complete_chore_done_by_follows_the_option(
    option, assigned_user, expected
) -> None:
    """The chore is logged for the API key owner or the assigned user (#81)."""
    chore = SimpleNamespace(id=5, next_execution_assigned_to_user_id=assigned_user)
    entity = _build_todo(ATTR_CHORES, [chore], {CONF_CHORE_DONE_BY: option})
    todo_item = SimpleNamespace(uid="5", status=TodoItemStatus.COMPLETED)

    with patch(
        "custom_components.grocy.todo.async_execute_chore_service",
        new_callable=AsyncMock,
    ) as mock_exec:
        await GrocyTodoListEntity.async_update_todo_item(entity, todo_item)

    assert mock_exec.call_args[0][2].get("done_by") == expected


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


@pytest.mark.feature("chore_management")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key", "item"),
    [
        (
            ATTR_CHORES,
            Chore(
                id=7,
                name="Vacuum",
                next_estimated_execution_time=dt.datetime.now() + dt.timedelta(days=3),
                track_date_only=False,
            ),
        ),
        (
            ATTR_TASKS,
            Task(
                id=8, name="Pay rent", due_date=dt.date.today() + dt.timedelta(days=5)
            ),
        ),
        (
            ATTR_BATTERIES,
            Battery(
                id=9,
                name="Remote",
                next_estimated_charge_time=dt.date.today() + dt.timedelta(days=30),
            ),
        ),
    ],
)
async def test_remove_completed_items_keeps_items_not_due_yet(key, item) -> None:
    """Clear completed must not delete chores, tasks or batteries that are due later."""
    entity = _build_todo(key, [item])

    with patch(
        "custom_components.grocy.todo.async_delete_generic_service",
        new_callable=AsyncMock,
    ) as mock_delete:
        await _async_remove_completed_items(entity, None)

    mock_delete.assert_not_awaited()


@pytest.mark.feature("shopping_list")
@pytest.mark.asyncio
async def test_remove_completed_items_removes_done_shopping_list_items() -> None:
    """Clear completed still removes shopping list items that are done."""
    done = ShoppingListProduct(id=3, amount=1.0, product=_make_product(), done=True)
    entity = _build_todo(ATTR_SHOPPING_LIST, [done])

    with patch(
        "custom_components.grocy.todo.async_delete_generic_service",
        new_callable=AsyncMock,
    ) as mock_delete:
        await _async_remove_completed_items(entity, None)

    assert mock_delete.call_args[0][2]["object_id"] == "3"


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


@pytest.mark.feature("cross_cutting")
@pytest.mark.parametrize("data", [[], None])
def test_get_grocy_item_removed_in_grocy_raises_clear_error(data) -> None:
    """An item removed in Grocy after the last update gives a clear error (#80)."""
    entity = _build_todo(ATTR_TASKS, data)

    with pytest.raises(HomeAssistantError, match="not in the last data from Grocy"):
        entity._get_grocy_item("7")


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
