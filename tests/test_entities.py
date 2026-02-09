from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import MagicMock

from grocy.data_models.task import Task
from homeassistant.components.todo import TodoItemStatus

from custom_components.grocy.binary_sensor import (
    BINARY_SENSORS,
    GrocyBinarySensorEntity,
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
)
from custom_components.grocy.coordinator import GrocyCoordinatorData
from custom_components.grocy.entity import GrocyEntity
from custom_components.grocy.sensor import SENSORS, GrocySensorEntity
from custom_components.grocy.todo import TODOS, GrocyTodoListEntity
from tests.factories import (
    DummyBattery,
    DummyChore,
    DummyMealPlanItem,
    DummyProduct,
    DummyShoppingListProduct,
    DummyTask,
)


def _build_sensor(key: str, data) -> GrocySensorEntity:
    description = next(description for description in SENSORS if description.key == key)
    entity = GrocySensorEntity.__new__(GrocySensorEntity)
    entity.entity_description = description
    entity.coordinator = SimpleNamespace(data=GrocyCoordinatorData())
    entity.coordinator.data[key] = data
    return entity


def _build_binary_sensor(key: str, data) -> GrocyBinarySensorEntity:
    description = next(
        description for description in BINARY_SENSORS if description.key == key
    )
    entity = GrocyBinarySensorEntity.__new__(GrocyBinarySensorEntity)
    entity.entity_description = description
    entity.coordinator = SimpleNamespace(data=GrocyCoordinatorData())
    entity.coordinator.data[key] = data
    return entity


def _build_todo(key: str, data) -> GrocyTodoListEntity:
    description = next(description for description in TODOS if description.key == key)
    entity = GrocyTodoListEntity.__new__(GrocyTodoListEntity)
    entity.entity_description = description
    entity.coordinator = SimpleNamespace(data=GrocyCoordinatorData())
    entity.coordinator.data[key] = data
    entity.hass = SimpleNamespace()
    entity._attr_supported_features = 0
    return entity


def test_sensor_native_value_counts_entities() -> None:
    entity = _build_sensor(ATTR_STOCK, [DummyProduct(), DummyProduct(id=2)])
    assert entity.native_value == 2


def test_sensor_extra_state_attributes_are_json_safe() -> None:
    entity = _build_sensor(ATTR_STOCK, [DummyProduct(id=99)])
    attributes = entity.extra_state_attributes
    assert attributes["count"] == 1
    assert attributes["products"][0]["id"] == 99


def test_sensor_native_value_defaults_to_zero() -> None:
    entity = _build_sensor(ATTR_STOCK, None)
    assert entity.native_value == 0


def test_binary_sensor_reports_on_state() -> None:
    entity = _build_binary_sensor(ATTR_OVERDUE_PRODUCTS, [DummyProduct()])
    assert entity.is_on is True
    attributes = entity.extra_state_attributes
    assert attributes["count"] == 1


def test_binary_sensor_reports_off_state() -> None:
    entity = _build_binary_sensor(ATTR_OVERDUE_PRODUCTS, [])
    assert entity.is_on is False


def test_todo_list_entity_exposes_items() -> None:
    due_date = dt.date.today() + dt.timedelta(days=1)
    tasks = [
        Task(
            id=7,
            name="Task",
            description="Task description",
            due_date=dt.datetime.combine(due_date, dt.time.min),
        )
    ]
    entity = _build_todo(ATTR_TASKS, tasks)

    todo_items = entity.todo_items
    assert len(todo_items) == 1
    item = todo_items[0]
    assert item.uid == "7"
    assert item.summary == "Task"
    assert item.status == TodoItemStatus.COMPLETED


def test_todo_list_entity_handles_empty_data() -> None:
    entity = _build_todo(ATTR_CHORES, [])
    assert entity.todo_items == []


# ─── Sensor coverage for each entity type ─────────────────────────────────────


def test_sensor_chores_counts() -> None:
    entity = _build_sensor(ATTR_CHORES, [DummyChore(), DummyChore(id=2)])
    assert entity.native_value == 2
    attrs = entity.extra_state_attributes
    assert attrs["count"] == 2
    assert "chores" in attrs


def test_sensor_tasks_counts() -> None:
    entity = _build_sensor(ATTR_TASKS, [DummyTask()])
    assert entity.native_value == 1
    attrs = entity.extra_state_attributes
    assert attrs["count"] == 1
    assert "tasks" in attrs


def test_sensor_batteries_counts() -> None:
    entity = _build_sensor(ATTR_BATTERIES, [DummyBattery()])
    assert entity.native_value == 1
    attrs = entity.extra_state_attributes
    assert "batteries" in attrs


def test_sensor_meal_plan_counts() -> None:
    entity = _build_sensor(ATTR_MEAL_PLAN, [DummyMealPlanItem()])
    assert entity.native_value == 1
    attrs = entity.extra_state_attributes
    assert "meals" in attrs


def test_sensor_shopping_list_counts() -> None:
    entity = _build_sensor(ATTR_SHOPPING_LIST, [DummyShoppingListProduct()])
    assert entity.native_value == 1
    attrs = entity.extra_state_attributes
    assert "products" in attrs


# ─── Binary sensor for each entity type ───────────────────────────────────────


def test_binary_sensor_expired_products_on() -> None:
    entity = _build_binary_sensor(ATTR_EXPIRED_PRODUCTS, [DummyProduct()])
    assert entity.is_on is True
    assert entity.extra_state_attributes["count"] == 1


def test_binary_sensor_expiring_products_off() -> None:
    entity = _build_binary_sensor(ATTR_EXPIRING_PRODUCTS, [])
    assert entity.is_on is False


def test_binary_sensor_missing_products() -> None:
    entity = _build_binary_sensor(ATTR_MISSING_PRODUCTS, [DummyProduct()])
    assert entity.is_on is True


def test_binary_sensor_overdue_chores() -> None:
    entity = _build_binary_sensor(ATTR_OVERDUE_CHORES, [DummyChore()])
    assert entity.is_on is True
    assert entity.extra_state_attributes["count"] == 1


def test_binary_sensor_overdue_tasks() -> None:
    entity = _build_binary_sensor(ATTR_OVERDUE_TASKS, [DummyTask()])
    assert entity.is_on is True


def test_binary_sensor_overdue_batteries() -> None:
    entity = _build_binary_sensor(ATTR_OVERDUE_BATTERIES, [DummyBattery()])
    assert entity.is_on is True


def test_binary_sensor_none_data() -> None:
    entity = _build_binary_sensor(ATTR_OVERDUE_PRODUCTS, None)
    assert entity.is_on is False


# ─── Sensor / binary_sensor extra_state_attributes when data is None ──────────


def test_sensor_extra_state_attributes_none_data() -> None:
    entity = _build_sensor(ATTR_STOCK, None)
    assert entity.extra_state_attributes is None


# ─── exists_fn coverage for sensor and binary sensor descriptions ─────────────


def test_sensor_exists_fn() -> None:
    for desc in SENSORS:
        assert desc.exists_fn([desc.key]) is True
        assert desc.exists_fn([]) is False


def test_binary_sensor_exists_fn() -> None:
    for desc in BINARY_SENSORS:
        assert desc.exists_fn([desc.key]) is True
        assert desc.exists_fn([]) is False


# ─── GrocyCoordinatorData dict-like access ────────────────────────────────────


def test_coordinator_data_setitem_getitem() -> None:
    data = GrocyCoordinatorData()
    data["stock"] = ["item1", "item2"]
    assert data["stock"] == ["item1", "item2"]
    assert data.stock == ["item1", "item2"]


def test_coordinator_data_defaults_to_none() -> None:
    data = GrocyCoordinatorData()
    assert data.stock is None
    assert data.tasks is None
    assert data.batteries is None
