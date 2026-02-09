from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from grocy.data_models.generic import EntityType
from grocy.grocy_api_client import TransactionType

from custom_components.grocy import services
from custom_components.grocy.const import DOMAIN


@pytest.fixture
def coordinator(mock_grocy) -> SimpleNamespace:
    return SimpleNamespace(grocy_api=mock_grocy, entities=[])


@pytest.fixture(autouse=True)
async def stub_executor(hass):
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))


@pytest.mark.asyncio
async def test_add_product_service_converts_price(hass, coordinator) -> None:
    data = {
        services.SERVICE_PRODUCT_ID: 5,
        services.SERVICE_AMOUNT: 2.0,
        services.SERVICE_PRICE: "1.25",
    }

    await services.async_add_product_service(hass, coordinator, data)

    coordinator.grocy_api.stock.add.assert_called_once_with(5, 2.0, 1.25)


@pytest.mark.asyncio
async def test_add_product_service_defaults_price_zero(hass, coordinator) -> None:
    data = {
        services.SERVICE_PRODUCT_ID: 8,
        services.SERVICE_AMOUNT: 1.0,
        services.SERVICE_PRICE: "",
    }

    await services.async_add_product_service(hass, coordinator, data)

    coordinator.grocy_api.stock.add.assert_called_once_with(8, 1.0, 0.0)


@pytest.mark.asyncio
async def test_open_product_service_uses_defaults(hass, coordinator) -> None:
    data = {
        services.SERVICE_PRODUCT_ID: 4,
        services.SERVICE_AMOUNT: 3.0,
    }

    await services.async_open_product_service(hass, coordinator, data)

    coordinator.grocy_api.stock.open.assert_called_once_with(4, 3.0, False)


@pytest.mark.asyncio
async def test_consume_product_service_handles_transaction_type(
    hass, coordinator
) -> None:
    data = {
        services.SERVICE_PRODUCT_ID: 2,
        services.SERVICE_AMOUNT: 1.0,
        services.SERVICE_TRANSACTION_TYPE: "INVENTORY_CORRECTION",
        services.SERVICE_SPOILED: True,
        services.SERVICE_SUBPRODUCT_SUBSTITUTION: True,
    }

    await services.async_consume_product_service(hass, coordinator, data)

    coordinator.grocy_api.stock.consume.assert_called_once()
    _, args, kwargs = coordinator.grocy_api.stock.consume.mock_calls[0]
    assert args == (2, 1.0)
    assert kwargs["spoiled"] is True
    assert kwargs["allow_subproduct_substitution"] is True
    assert kwargs["transaction_type"] == TransactionType.INVENTORY_CORRECTION


@pytest.mark.asyncio
async def test_execute_chore_service_triggers_refresh(hass, coordinator) -> None:
    data = {
        services.SERVICE_CHORE_ID: 3,
        services.SERVICE_DONE_BY: "1",
        services.SERVICE_SKIPPED: False,
    }

    with patch(
        "custom_components.grocy.services._async_force_update_entity",
        new_callable=AsyncMock,
    ) as mock_refresh:
        await services.async_execute_chore_service(hass, coordinator, data)

    coordinator.grocy_api.chores.execute.assert_called_once_with(3, 1, skipped=False)
    mock_refresh.assert_awaited_once_with(coordinator, services.ATTR_CHORES)


@pytest.mark.asyncio
async def test_complete_task_service_triggers_refresh(hass, coordinator) -> None:
    data = {
        services.SERVICE_TASK_ID: 11,
    }

    with patch(
        "custom_components.grocy.services._async_force_update_entity",
        new_callable=AsyncMock,
    ) as mock_refresh:
        await services.async_complete_task_service(hass, coordinator, data)

    coordinator.grocy_api.tasks.complete.assert_called_once_with(11)
    mock_refresh.assert_awaited_once_with(coordinator, services.ATTR_TASKS)


@pytest.mark.asyncio
async def test_add_generic_service_refreshes_tasks(hass, coordinator) -> None:
    data = {
        services.SERVICE_ENTITY_TYPE: "tasks",
        services.SERVICE_DATA: {"name": "Task"},
    }

    with patch(
        "custom_components.grocy.services._post_generic_refresh",
        new_callable=AsyncMock,
    ) as mock_post:
        await services.async_add_generic_service(hass, coordinator, data)

    coordinator.grocy_api.generic.create.assert_called_once_with(
        EntityType.TASKS, data[services.SERVICE_DATA]
    )
    mock_post.assert_awaited_once_with(coordinator, EntityType.TASKS)


@pytest.mark.asyncio
async def test_update_generic_service_refreshes_entity(hass, coordinator) -> None:
    data = {
        services.SERVICE_ENTITY_TYPE: "chores",
        services.SERVICE_OBJECT_ID: 12,
        services.SERVICE_DATA: {"name": "Updated"},
    }

    with patch(
        "custom_components.grocy.services._post_generic_refresh",
        new_callable=AsyncMock,
    ) as mock_post:
        await services.async_update_generic_service(hass, coordinator, data)

    coordinator.grocy_api.generic.update.assert_called_once_with(
        EntityType.CHORES, 12, data[services.SERVICE_DATA]
    )
    mock_post.assert_awaited_once_with(coordinator, EntityType.CHORES)


@pytest.mark.asyncio
async def test_delete_generic_service_defaults_to_tasks(hass, coordinator) -> None:
    data = {
        services.SERVICE_OBJECT_ID: 9,
    }

    with patch(
        "custom_components.grocy.services._post_generic_refresh",
        new_callable=AsyncMock,
    ) as mock_post:
        await services.async_delete_generic_service(hass, coordinator, data)

    coordinator.grocy_api.generic.delete.assert_called_once_with(EntityType.TASKS, 9)
    mock_post.assert_awaited_once_with(coordinator, EntityType.TASKS)


@pytest.mark.asyncio
async def test_post_generic_refresh_updates_relevant_entities(coordinator) -> None:
    with patch(
        "custom_components.grocy.services._async_force_update_entity",
        new_callable=AsyncMock,
    ) as mock_refresh:
        await services._post_generic_refresh(coordinator, EntityType.TASKS)
        mock_refresh.assert_awaited_once_with(coordinator, EntityType.TASKS.value)

    with patch(
        "custom_components.grocy.services._async_force_update_entity",
        new_callable=AsyncMock,
    ) as mock_refresh:
        await services._post_generic_refresh(coordinator, EntityType.USER_FIELDS)
        mock_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_consume_recipe_service(hass, coordinator) -> None:
    data = {services.SERVICE_RECIPE_ID: 21}

    await services.async_consume_recipe_service(hass, coordinator, data)

    coordinator.grocy_api.recipes.consume.assert_called_once_with(21)


@pytest.mark.asyncio
async def test_track_battery_service(hass, coordinator) -> None:
    data = {services.SERVICE_BATTERY_ID: 6}

    await services.async_track_battery_service(hass, coordinator, data)

    coordinator.grocy_api.batteries.charge.assert_called_once_with(6)


@pytest.mark.asyncio
async def test_add_missing_products_to_shopping_list_defaults_list(
    hass, coordinator
) -> None:
    data: dict[str, int] = {}

    await services.async_add_missing_products_to_shopping_list(hass, coordinator, data)

    coordinator.grocy_api.shopping_list.add_missing_products.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_remove_product_in_shopping_list_defaults(hass, coordinator) -> None:
    data = {
        services.SERVICE_PRODUCT_ID: 4,
        services.SERVICE_AMOUNT: 2.0,
    }

    await services.async_remove_product_in_shopping_list(hass, coordinator, data)

    coordinator.grocy_api.shopping_list.remove_product.assert_called_once_with(
        4, 1, 2.0
    )


@pytest.mark.asyncio
async def test_remove_product_in_shopping_list_service_prefers_payload(
    hass, coordinator
) -> None:
    data = {
        services.SERVICE_PRODUCT_ID: 3,
        services.SERVICE_AMOUNT: 1.0,
        services.SERVICE_LIST_ID: 5,
    }

    await services.async_remove_product_in_shopping_list_service(
        hass, coordinator, data
    )

    coordinator.grocy_api.shopping_list.remove_product.assert_called_once_with(
        3, 5, 1.0
    )


@pytest.mark.asyncio
async def test_async_force_update_entity_updates_matching_entity() -> None:
    entity = SimpleNamespace(
        entity_description=SimpleNamespace(key=services.ATTR_TASKS),
        async_update_ha_state=AsyncMock(),
    )
    coordinator = SimpleNamespace(entities=[entity])

    await services._async_force_update_entity(coordinator, services.ATTR_TASKS)

    entity.async_update_ha_state.assert_awaited_once_with(force_refresh=True)


@pytest.mark.asyncio
async def test_async_force_update_entity_ignores_missing() -> None:
    coordinator = SimpleNamespace(entities=[])

    await services._async_force_update_entity(coordinator, services.ATTR_TASKS)


# ─── async_setup_services ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_setup_services_registers_all_services(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])

    await services.async_setup_services(hass, mock_config_entry)

    registered = hass.services.async_services().get(DOMAIN, {})
    for service_name, _schema in services.SERVICES_WITH_ACCOMPANYING_SCHEMA:
        assert service_name in registered, f"Service {service_name} not registered"


@pytest.mark.asyncio
async def test_async_setup_services_skips_if_already_registered(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])

    await services.async_setup_services(hass, mock_config_entry)
    count_before = len(hass.services.async_services().get(DOMAIN, {}))

    await services.async_setup_services(hass, mock_config_entry)
    count_after = len(hass.services.async_services().get(DOMAIN, {}))

    assert count_before == count_after


# ─── async_unload_services ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_unload_services_removes_all(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])

    await services.async_setup_services(hass, mock_config_entry)
    assert hass.services.async_services().get(DOMAIN)

    await services.async_unload_services(hass)

    assert not hass.services.async_services().get(DOMAIN)


@pytest.mark.asyncio
async def test_async_unload_services_noop_if_not_registered(hass) -> None:
    # Should not raise
    await services.async_unload_services(hass)


# ─── consume_product defaults to CONSUME transaction_type ─────────────────────


@pytest.mark.asyncio
async def test_consume_product_defaults_transaction_type(hass, coordinator) -> None:
    data = {
        services.SERVICE_PRODUCT_ID: 1,
        services.SERVICE_AMOUNT: 1.0,
    }

    await services.async_consume_product_service(hass, coordinator, data)

    _, args, kwargs = coordinator.grocy_api.stock.consume.mock_calls[0]
    assert kwargs["transaction_type"] == TransactionType.CONSUME


# ─── add_product with no price key ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_product_service_no_price_key(hass, coordinator) -> None:
    data = {
        services.SERVICE_PRODUCT_ID: 10,
        services.SERVICE_AMOUNT: 5.0,
    }

    await services.async_add_product_service(hass, coordinator, data)

    coordinator.grocy_api.stock.add.assert_called_once_with(10, 5.0, 0.0)


# ─── execute_chore with empty done_by ────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_chore_empty_done_by(hass, coordinator) -> None:
    data = {
        services.SERVICE_CHORE_ID: 7,
        services.SERVICE_DONE_BY: "",
    }

    with patch(
        "custom_components.grocy.services._async_force_update_entity",
        new_callable=AsyncMock,
    ):
        await services.async_execute_chore_service(hass, coordinator, data)

    coordinator.grocy_api.chores.execute.assert_called_once_with(
        7, None, skipped=False
    )


# ─── open_product with substitution enabled ──────────────────────────────────


@pytest.mark.asyncio
async def test_open_product_with_substitution(hass, coordinator) -> None:
    data = {
        services.SERVICE_PRODUCT_ID: 6,
        services.SERVICE_AMOUNT: 1.0,
        services.SERVICE_SUBPRODUCT_SUBSTITUTION: True,
    }

    await services.async_open_product_service(hass, coordinator, data)

    coordinator.grocy_api.stock.open.assert_called_once_with(6, 1.0, True)


# ─── remove_product_in_shopping_list with shopping_list_id key ────────────────


@pytest.mark.asyncio
async def test_remove_product_shopping_list_id_key(hass, coordinator) -> None:
    data = {
        services.SERVICE_PRODUCT_ID: 5,
        services.SERVICE_AMOUNT: 1.0,
        services.SERVICE_SHOPPING_LIST_ID: 3,
    }

    await services.async_remove_product_in_shopping_list(hass, coordinator, data)

    coordinator.grocy_api.shopping_list.remove_product.assert_called_once_with(5, 3, 1.0)


# ─── add_missing_products with explicit list_id ──────────────────────────────


@pytest.mark.asyncio
async def test_add_missing_products_explicit_list_id(hass, coordinator) -> None:
    data = {services.SERVICE_LIST_ID: 7}

    await services.async_add_missing_products_to_shopping_list(
        hass, coordinator, data
    )

    coordinator.grocy_api.shopping_list.add_missing_products.assert_called_once_with(7)


# ─── delete_generic with explicit entity_type ────────────────────────────────


@pytest.mark.asyncio
async def test_delete_generic_with_explicit_entity_type(hass, coordinator) -> None:
    data = {
        services.SERVICE_ENTITY_TYPE: "chores",
        services.SERVICE_OBJECT_ID: 5,
    }

    with patch(
        "custom_components.grocy.services._post_generic_refresh",
        new_callable=AsyncMock,
    ) as mock_post:
        await services.async_delete_generic_service(hass, coordinator, data)

    coordinator.grocy_api.generic.delete.assert_called_once_with(EntityType.CHORES, 5)
    mock_post.assert_awaited_once_with(coordinator, EntityType.CHORES)


# ─── _post_generic_refresh for chores ────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_generic_refresh_for_chores(coordinator) -> None:
    with patch(
        "custom_components.grocy.services._async_force_update_entity",
        new_callable=AsyncMock,
    ) as mock_refresh:
        await services._post_generic_refresh(coordinator, EntityType.CHORES)
        mock_refresh.assert_awaited_once_with(coordinator, EntityType.CHORES.value)


# ─── async_call_grocy_service dispatcher ─────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatcher_routes_add_product(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])
    await services.async_setup_services(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        services.SERVICE_ADD_PRODUCT,
        {services.SERVICE_PRODUCT_ID: 1, services.SERVICE_AMOUNT: 2.0},
        blocking=True,
    )

    mock_grocy.stock.add.assert_called_once()


@pytest.mark.asyncio
async def test_dispatcher_routes_open_product(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])
    await services.async_setup_services(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        services.SERVICE_OPEN_PRODUCT,
        {services.SERVICE_PRODUCT_ID: 1, services.SERVICE_AMOUNT: 1.0},
        blocking=True,
    )

    mock_grocy.stock.open.assert_called_once()


@pytest.mark.asyncio
async def test_dispatcher_routes_consume_product(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])
    await services.async_setup_services(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        services.SERVICE_CONSUME_PRODUCT,
        {services.SERVICE_PRODUCT_ID: 1, services.SERVICE_AMOUNT: 1.0},
        blocking=True,
    )

    mock_grocy.stock.consume.assert_called_once()


@pytest.mark.asyncio
async def test_dispatcher_routes_execute_chore(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])
    await services.async_setup_services(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        services.SERVICE_EXECUTE_CHORE,
        {services.SERVICE_CHORE_ID: 1},
        blocking=True,
    )

    mock_grocy.chores.execute.assert_called_once()


@pytest.mark.asyncio
async def test_dispatcher_routes_complete_task(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])
    await services.async_setup_services(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        services.SERVICE_COMPLETE_TASK,
        {services.SERVICE_TASK_ID: 1},
        blocking=True,
    )

    mock_grocy.tasks.complete.assert_called_once()


@pytest.mark.asyncio
async def test_dispatcher_routes_consume_recipe(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])
    await services.async_setup_services(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        services.SERVICE_CONSUME_RECIPE,
        {services.SERVICE_RECIPE_ID: 1},
        blocking=True,
    )

    mock_grocy.recipes.consume.assert_called_once()


@pytest.mark.asyncio
async def test_dispatcher_routes_track_battery(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])
    await services.async_setup_services(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        services.SERVICE_TRACK_BATTERY,
        {services.SERVICE_BATTERY_ID: 1},
        blocking=True,
    )

    mock_grocy.batteries.charge.assert_called_once()


@pytest.mark.asyncio
async def test_dispatcher_routes_add_generic(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])
    await services.async_setup_services(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        services.SERVICE_ADD_GENERIC,
        {services.SERVICE_ENTITY_TYPE: "tasks", services.SERVICE_DATA: {"name": "T"}},
        blocking=True,
    )

    mock_grocy.generic.create.assert_called_once()


@pytest.mark.asyncio
async def test_dispatcher_routes_update_generic(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])
    await services.async_setup_services(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        services.SERVICE_UPDATE_GENERIC,
        {
            services.SERVICE_ENTITY_TYPE: "tasks",
            services.SERVICE_OBJECT_ID: 1,
            services.SERVICE_DATA: {"name": "U"},
        },
        blocking=True,
    )

    mock_grocy.generic.update.assert_called_once()


@pytest.mark.asyncio
async def test_dispatcher_routes_delete_generic(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])
    await services.async_setup_services(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        services.SERVICE_DELETE_GENERIC,
        {services.SERVICE_ENTITY_TYPE: "tasks", services.SERVICE_OBJECT_ID: 1},
        blocking=True,
    )

    mock_grocy.generic.delete.assert_called_once()


@pytest.mark.asyncio
async def test_dispatcher_routes_add_missing_products(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])
    await services.async_setup_services(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        services.SERVICE_ADD_MISSING_PRODUCTS_TO_SHOPPING_LIST,
        {},
        blocking=True,
    )

    mock_grocy.shopping_list.add_missing_products.assert_called_once()


@pytest.mark.asyncio
async def test_dispatcher_routes_remove_product_in_shopping_list(
    hass, mock_config_entry, mock_grocy
) -> None:
    hass.data[DOMAIN] = SimpleNamespace(grocy_api=mock_grocy, entities=[])
    await services.async_setup_services(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        services.SERVICE_REMOVE_PRODUCT_IN_SHOPPING_LIST,
        {services.SERVICE_PRODUCT_ID: 1, services.SERVICE_AMOUNT: 1.0},
        blocking=True,
    )

    mock_grocy.shopping_list.remove_product.assert_called_once()


@pytest.mark.asyncio
async def test_sync_calendar_service_calls_calendar_update(hass, coordinator) -> None:
    """Test that sync_calendar service triggers calendar update."""
    # Create a mock calendar entity
    mock_calendar_entity = MagicMock()
    mock_calendar_entity.entity_description = SimpleNamespace(key="calendar")
    mock_calendar_entity._async_update_calendar = AsyncMock()

    # Add mock entity to coordinator
    coordinator.entities = [mock_calendar_entity]

    await services.async_sync_calendar_service(coordinator)

    mock_calendar_entity._async_update_calendar.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_calendar_service_handles_no_calendar_entity(
    hass, coordinator
) -> None:
    """Test that sync_calendar service handles missing calendar entity gracefully."""
    # No calendar entity in coordinator
    coordinator.entities = []

    # Should not raise an error
    await services.async_sync_calendar_service(coordinator)


@pytest.mark.asyncio
async def test_dispatcher_routes_sync_calendar(
    hass, mock_config_entry, mock_grocy
) -> None:
    """Test that the dispatcher routes sync_calendar service calls."""
    mock_calendar_entity = MagicMock()
    mock_calendar_entity.entity_description = SimpleNamespace(key="calendar")
    mock_calendar_entity._async_update_calendar = AsyncMock()

    hass.data[DOMAIN] = SimpleNamespace(
        grocy_api=mock_grocy, entities=[mock_calendar_entity]
    )
    await services.async_setup_services(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        services.SERVICE_SYNC_CALENDAR,
        {},
        blocking=True,
    )

    mock_calendar_entity._async_update_calendar.assert_awaited_once()
