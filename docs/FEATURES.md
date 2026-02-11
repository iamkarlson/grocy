# Grocy Features Reference

This document describes all features provided by the Grocy custom component for Home Assistant. Each feature group lists its entities, services, and the tests that validate its behavior.

**All entities are disabled by default.** Enable the ones you need in Settings > Devices & Services > Grocy.

If you enable a todo entity (like `todo.grocy_stock`), you should also enable the corresponding sensor (like `sensor.grocy_stock`). Otherwise you may see "entity is unknown" errors.

---

## Table of Contents

1. [Stock Management](#1-stock-management)
2. [Shopping List](#2-shopping-list)
3. [Chore Management](#3-chore-management)
4. [Task Management](#4-task-management)
5. [Battery Tracking](#5-battery-tracking)
6. [Meal Planning](#6-meal-planning)
7. [Calendar](#7-calendar)
8. [Image Proxy](#8-image-proxy)
9. [Generic CRUD](#9-generic-crud)
10. [Configuration & Setup](#10-configuration--setup)

---

## 1. Stock Management

Track product inventory, monitor expiration dates, and manage stock through Home Assistant.

Requires Grocy feature flag: `FEATURE_FLAG_STOCK`

### Entities

#### Sensors

| Entity ID | State | Attributes | Icon |
|-----------|-------|------------|------|
| `sensor.grocy_stock` | Number of products in stock | `count`, `products` (list) | mdi:fridge-outline |

#### Binary Sensors

| Entity ID | ON when | Attributes | Icon |
|-----------|---------|------------|------|
| `binary_sensor.grocy_expired_products` | Products are expired | `count`, `expired_products` (list) | mdi:delete-alert-outline |
| `binary_sensor.grocy_expiring_products` | Products expiring soon | `count`, `expiring_products` (list) | mdi:clock-fast |
| `binary_sensor.grocy_overdue_products` | Products past best-before date | `count`, `overdue_products` (list) | mdi:alert-circle-check-outline |
| `binary_sensor.grocy_missing_products` | Products below minimum stock | `count`, `missing_products` (list) | mdi:flask-round-bottom-empty-outline |

#### Todo Lists

| Entity ID | Supports | Update behavior | Delete behavior |
|-----------|----------|----------------|-----------------|
| `todo.grocy_stock` | UPDATE, DELETE | Marking complete **consumes** the product (full available amount) | Deletes stock entry |

**Note:** Stock todo items cannot be created through Home Assistant. Use the Grocy UI to add products.

### Services

#### `grocy.add_product_to_stock`

Add a quantity of a product to stock.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product_id` | int | Yes | Grocy product ID |
| `amount` | float | Yes | Quantity to add |
| `price` | string | No | Price per unit (empty or omitted defaults to 0.0) |

#### `grocy.consume_product_from_stock`

Consume a quantity of a product from stock.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product_id` | int | Yes | Grocy product ID |
| `amount` | float | Yes | Quantity to consume |
| `spoiled` | bool | No | Mark as spoiled (default: false) |
| `allow_subproduct_substitution` | bool | No | Allow substitution (default: false) |
| `transaction_type` | string | No | Transaction type: `CONSUME`, `INVENTORY_CORRECTION`, etc. (default: `CONSUME`) |

#### `grocy.open_product`

Open a product in stock (e.g., open a package).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product_id` | int | Yes | Grocy product ID |
| `amount` | float | Yes | Quantity to open |
| `allow_subproduct_substitution` | bool | No | Allow substitution (default: false) |

### Test Coverage

| Test File | Test Function | What It Validates |
|-----------|---------------|-------------------|
| tests/test_entities.py | `test_sensor_native_value_counts_entities` | Stock sensor counts products correctly |
| tests/test_entities.py | `test_sensor_extra_state_attributes_are_json_safe` | Stock sensor attributes are JSON-serializable |
| tests/test_entities.py | `test_sensor_native_value_defaults_to_zero` | Stock sensor returns 0 when data is None |
| tests/test_entities.py | `test_sensor_extra_state_attributes_none_data` | Sensor attributes return None when data is None |
| tests/test_entities.py | `test_binary_sensor_reports_on_state` | Binary sensor reports ON when overdue products exist |
| tests/test_entities.py | `test_binary_sensor_reports_off_state` | Binary sensor reports OFF when no overdue products |
| tests/test_entities.py | `test_binary_sensor_expired_products_on` | Expired products binary sensor detects expiry |
| tests/test_entities.py | `test_binary_sensor_expiring_products_off` | Expiring products binary sensor OFF when empty |
| tests/test_entities.py | `test_binary_sensor_missing_products` | Missing products binary sensor detects low stock |
| tests/test_entities.py | `test_binary_sensor_none_data` | Binary sensor handles None data gracefully |
| tests/test_services.py | `test_add_product_service_converts_price` | Price string is converted to float |
| tests/test_services.py | `test_add_product_service_defaults_price_zero` | Empty price defaults to 0.0 |
| tests/test_services.py | `test_add_product_service_no_price_key` | Missing price key defaults to 0.0 |
| tests/test_services.py | `test_open_product_service_uses_defaults` | Open product uses default parameter values |
| tests/test_services.py | `test_open_product_with_substitution` | Open product handles substitution flag |
| tests/test_services.py | `test_consume_product_service_handles_transaction_type` | Consume product converts transaction type |
| tests/test_services.py | `test_consume_product_defaults_transaction_type` | Consume product defaults to CONSUME type |
| tests/test_services.py | `test_dispatcher_routes_add_product` | Service dispatcher routes add_product correctly |
| tests/test_services.py | `test_dispatcher_routes_open_product` | Service dispatcher routes open_product correctly |
| tests/test_services.py | `test_dispatcher_routes_consume_product` | Service dispatcher routes consume_product correctly |
| tests/test_todo.py | `test_todo_item_from_product_with_stock` | Product converts to todo item with amount in summary |
| tests/test_todo.py | `test_todo_item_from_product_zero_amount` | Zero-stock product shows as COMPLETED |
| tests/test_todo.py | `test_async_update_todo_item_complete_stock` | Completing stock todo consumes product |
| tests/test_todo.py | `test_async_update_todo_item_stock_needs_action_raises` | Uncompleting stock todo raises NotImplementedError |
| tests/test_todo.py | `test_todo_list_entity_stock_no_create` | Stock todo does not support CREATE |
| tests/test_grocy_data.py | `test_async_update_stock_returns_products` | Stock data fetching returns products |
| tests/test_grocy_data.py | `test_async_update_stock_empty` | Stock data fetching handles empty list |
| tests/test_grocy_data.py | `test_async_update_expiring_products` | Expiring products data fetching works |
| tests/test_grocy_data.py | `test_async_update_expired_products` | Expired products data fetching works |
| tests/test_grocy_data.py | `test_async_update_overdue_products` | Overdue products data fetching works |
| tests/test_grocy_data.py | `test_async_update_missing_products` | Missing products data fetching works |

---

## 2. Shopping List

Manage Grocy shopping lists from Home Assistant. Mark items done/undone and auto-add missing products.

Requires Grocy feature flag: `FEATURE_FLAG_SHOPPINGLIST`

### Entities

#### Sensors

| Entity ID | State | Attributes | Icon |
|-----------|-------|------------|------|
| `sensor.grocy_shopping_list` | Number of shopping list items | `count`, `products` (list) | mdi:cart-outline |

#### Todo Lists

| Entity ID | Supports | Update behavior | Delete behavior |
|-----------|----------|----------------|-----------------|
| `todo.grocy_shopping_list` | UPDATE, DELETE | Marking complete marks item **done** in Grocy; marking needs_action marks it **undone** | Deletes shopping list item |

**Note:** Shopping list is the only todo that supports toggling back to "needs action" (undone). All other entity types raise NotImplementedError when trying to uncomplete.

### Services

#### `grocy.add_missing_products_to_shopping_list`

Add all products below minimum stock level to a shopping list.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `list_id` | int | No | Shopping list ID (default: 1) |

#### `grocy.remove_product_in_shopping_list`

Remove a product from a shopping list.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product_id` | int | Yes | Grocy product ID |
| `amount` | float | Yes | Amount to remove |
| `list_id` | int | No | Shopping list ID (default: 1) |

### Test Coverage

| Test File | Test Function | What It Validates |
|-----------|---------------|-------------------|
| tests/test_entities.py | `test_sensor_shopping_list_counts` | Shopping list sensor counts items |
| tests/test_services.py | `test_add_missing_products_to_shopping_list_defaults_list` | Defaults to list ID 1 |
| tests/test_services.py | `test_add_missing_products_explicit_list_id` | Accepts explicit list ID |
| tests/test_services.py | `test_remove_product_in_shopping_list_defaults` | Remove product defaults to list 1 |
| tests/test_services.py | `test_remove_product_in_shopping_list_service_prefers_payload` | Prefers payload list_id over default |
| tests/test_services.py | `test_remove_product_shopping_list_id_key` | Accepts shopping_list_id key |
| tests/test_services.py | `test_mark_shopping_list_item_done` | Mark item as done |
| tests/test_services.py | `test_mark_shopping_list_item_undone` | Mark item as not done |
| tests/test_services.py | `test_dispatcher_routes_add_missing_products` | Dispatcher routes add_missing_products |
| tests/test_services.py | `test_dispatcher_routes_remove_product_in_shopping_list` | Dispatcher routes remove_product |
| tests/test_todo.py | `test_todo_item_from_shopping_list_product` | Shopping list item converts to todo |
| tests/test_todo.py | `test_todo_item_from_shopping_list_product_done` | Done item shows COMPLETED status |
| tests/test_todo.py | `test_todo_item_from_shopping_list_product_no_product` | Missing product shows "Unknown product" |
| tests/test_todo.py | `test_todo_item_from_shopping_list_product_string_done_flag` | Pydantic coerces string done flag |
| tests/test_todo.py | `test_async_update_todo_item_complete_shopping_list` | Completing marks item done |
| tests/test_todo.py | `test_async_update_todo_item_uncomplete_shopping_list` | Uncompleting marks item undone |
| tests/test_grocy_data.py | `test_async_update_shopping_list` | Shopping list data fetching |

---

## 3. Chore Management

Track and execute household chores. View upcoming and overdue chores.

Requires Grocy feature flag: `FEATURE_FLAG_CHORES`

### Entities

#### Sensors

| Entity ID | State | Attributes | Icon |
|-----------|-------|------------|------|
| `sensor.grocy_chores` | Number of chores | `count`, `chores` (list) | mdi:broom |

#### Binary Sensors

| Entity ID | ON when | Attributes | Icon |
|-----------|---------|------------|------|
| `binary_sensor.grocy_overdue_chores` | Chores are past due | `count`, `overdue_chores` (list) | mdi:alert-circle-check-outline |

#### Todo Lists

| Entity ID | Supports | Update behavior | Delete behavior |
|-----------|----------|----------------|-----------------|
| `todo.grocy_chores` | CREATE, UPDATE, DELETE | Marking complete **executes** the chore (done_by=1) | Deletes chore |

### Services

#### `grocy.execute_chore`

Execute (complete) a chore.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `chore_id` | int | Yes | Grocy chore ID |
| `done_by` | int | No | User ID who completed it (empty or omitted = None) |
| `track_execution_now` | bool | No | Track execution at current time |
| `skipped` | bool | No | Mark as skipped (default: false) |

After execution, the chores sensor is force-refreshed.

### Test Coverage

| Test File | Test Function | What It Validates |
|-----------|---------------|-------------------|
| tests/test_entities.py | `test_sensor_chores_counts` | Chores sensor counts correctly |
| tests/test_entities.py | `test_binary_sensor_overdue_chores` | Overdue chores binary sensor detects overdue |
| tests/test_services.py | `test_execute_chore_service_triggers_refresh` | Execute chore calls API and refreshes entity |
| tests/test_services.py | `test_execute_chore_empty_done_by` | Empty done_by is converted to None |
| tests/test_services.py | `test_dispatcher_routes_execute_chore` | Dispatcher routes execute_chore correctly |
| tests/test_todo.py | `test_todo_item_from_chore` | Chore converts to todo item |
| tests/test_todo.py | `test_todo_item_from_chore_date_only` | Date-only chore handled correctly |
| tests/test_todo.py | `test_async_create_todo_item_chore` | Creating chore todo sets period_type=manually |
| tests/test_todo.py | `test_async_update_todo_item_complete_chore` | Completing chore todo executes chore |
| tests/test_todo.py | `test_async_update_todo_item_chore_needs_action_raises` | Uncompleting chore raises NotImplementedError |
| tests/test_grocy_data.py | `test_async_update_chores` | Chores data fetching with details |
| tests/test_grocy_data.py | `test_async_update_overdue_chores` | Overdue chores filtering with query |

---

## 4. Task Management

Track tasks with due dates. Create, complete, and delete tasks.

Requires Grocy feature flag: `FEATURE_FLAG_TASKS`

### Entities

#### Sensors

| Entity ID | State | Attributes | Icon |
|-----------|-------|------------|------|
| `sensor.grocy_tasks` | Number of tasks | `count`, `tasks` (list) | mdi:checkbox-marked-circle-outline |

#### Binary Sensors

| Entity ID | ON when | Attributes | Icon |
|-----------|---------|------------|------|
| `binary_sensor.grocy_overdue_tasks` | Tasks are past due | `count`, `overdue_tasks` (list) | mdi:alert-circle-check-outline |

#### Todo Lists

| Entity ID | Supports | Update behavior | Delete behavior |
|-----------|----------|----------------|-----------------|
| `todo.grocy_tasks` | CREATE, UPDATE, DELETE | Marking complete **completes** the task | Deletes task |

### Services

#### `grocy.complete_task`

Complete a task.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | int | Yes | Grocy task ID |

After completion, the tasks sensor is force-refreshed.

### Test Coverage

| Test File | Test Function | What It Validates |
|-----------|---------------|-------------------|
| tests/test_entities.py | `test_sensor_tasks_counts` | Tasks sensor counts correctly |
| tests/test_entities.py | `test_binary_sensor_overdue_tasks` | Overdue tasks binary sensor |
| tests/test_entities.py | `test_todo_list_entity_exposes_items` | Task todo items are exposed correctly |
| tests/test_entities.py | `test_todo_list_entity_handles_empty_data` | Empty task list handled |
| tests/test_services.py | `test_complete_task_service_triggers_refresh` | Complete task calls API and refreshes entity |
| tests/test_services.py | `test_dispatcher_routes_complete_task` | Dispatcher routes complete_task |
| tests/test_todo.py | `test_todo_item_from_task` | Task converts to todo item with correct fields |
| tests/test_todo.py | `test_todo_item_from_task_overdue` | Overdue task shows NEEDS_ACTION status |
| tests/test_todo.py | `test_async_create_todo_item_task` | Creating task todo calls add_generic |
| tests/test_todo.py | `test_async_update_todo_item_complete_task` | Completing task todo calls complete_task |
| tests/test_todo.py | `test_async_update_todo_item_task_needs_action_raises` | Uncompleting task raises NotImplementedError |
| tests/test_todo.py | `test_async_delete_todo_items_calls_delete_for_each_uid` | Delete calls delete_generic per item |
| tests/test_grocy_data.py | `test_async_update_tasks` | Tasks data fetching |
| tests/test_grocy_data.py | `test_async_update_overdue_tasks` | Overdue tasks filtering with date query |

---

## 5. Battery Tracking

Track battery charge cycles and get alerts when batteries need charging.

Requires Grocy feature flag: `FEATURE_FLAG_BATTERIES`

### Entities

#### Sensors

| Entity ID | State | Attributes | Icon |
|-----------|-------|------------|------|
| `sensor.grocy_batteries` | Number of batteries | `count`, `batteries` (list) | mdi:battery |

#### Binary Sensors

| Entity ID | ON when | Attributes | Icon |
|-----------|---------|------------|------|
| `binary_sensor.grocy_overdue_batteries` | Batteries need charging | `count`, `overdue_batteries` (list) | mdi:battery-charging-10 |

#### Todo Lists

| Entity ID | Supports | Update behavior | Delete behavior |
|-----------|----------|----------------|-----------------|
| `todo.grocy_batteries` | CREATE, UPDATE, DELETE | Marking complete **tracks battery charge** | Deletes battery |

### Services

#### `grocy.track_battery`

Record a battery charge/replacement.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `battery_id` | int | Yes | Grocy battery ID |

### Test Coverage

| Test File | Test Function | What It Validates |
|-----------|---------------|-------------------|
| tests/test_entities.py | `test_sensor_batteries_counts` | Batteries sensor counts correctly |
| tests/test_entities.py | `test_binary_sensor_overdue_batteries` | Overdue batteries binary sensor |
| tests/test_services.py | `test_track_battery_service` | Track battery calls charge API |
| tests/test_services.py | `test_dispatcher_routes_track_battery` | Dispatcher routes track_battery |
| tests/test_todo.py | `test_todo_item_from_battery` | Battery converts to todo item |
| tests/test_todo.py | `test_todo_item_from_battery_overdue` | Overdue battery shows NEEDS_ACTION |
| tests/test_todo.py | `test_todo_list_entity_batteries_supports_create` | Battery todo supports CREATE |
| tests/test_todo.py | `test_async_create_todo_item_battery` | Creating battery todo calls add_generic |
| tests/test_todo.py | `test_async_update_todo_item_complete_battery` | Completing battery todo tracks charge |
| tests/test_todo.py | `test_async_update_todo_item_battery_needs_action_raises` | Uncompleting battery raises NotImplementedError |
| tests/test_grocy_data.py | `test_async_update_batteries` | Batteries data fetching with details |
| tests/test_grocy_data.py | `test_async_update_overdue_batteries` | Overdue batteries data fetching |

---

## 6. Meal Planning

View meal plans and consume recipes (remove ingredients from stock).

Requires Grocy feature flag: `FEATURE_FLAG_RECIPES`

### Entities

#### Sensors

| Entity ID | State | Attributes | Icon |
|-----------|-------|------------|------|
| `sensor.grocy_meal_plan` | Number of upcoming meals | `count`, `meals` (list) | mdi:silverware-variant |

#### Todo Lists

| Entity ID | Supports | Update behavior | Delete behavior |
|-----------|----------|----------------|-----------------|
| `todo.grocy_meal_plan` | UPDATE, DELETE | Marking complete **consumes the recipe** (removes ingredients from stock) and deletes the meal plan entry | Deletes meal plan entry |

**Note:** Meal plan todo items cannot be created through Home Assistant. Use the Grocy UI to plan meals.

### Services

#### `grocy.consume_recipe`

Consume a recipe (deduct all ingredients from stock).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `recipe_id` | int | Yes | Grocy recipe ID |

### Test Coverage

| Test File | Test Function | What It Validates |
|-----------|---------------|-------------------|
| tests/test_entities.py | `test_sensor_meal_plan_counts` | Meal plan sensor counts correctly |
| tests/test_services.py | `test_consume_recipe_service` | Consume recipe calls API |
| tests/test_services.py | `test_dispatcher_routes_consume_recipe` | Dispatcher routes consume_recipe |
| tests/test_todo.py | `test_todo_item_from_meal_plan_item` | Meal plan item converts to todo |
| tests/test_todo.py | `test_todo_item_from_meal_plan_item_wrapper` | MealPlanItemWrapper converts to todo |
| tests/test_todo.py | `test_async_update_todo_item_complete_meal_plan` | Completing meal plan consumes recipe and deletes entry |
| tests/test_todo.py | `test_async_update_todo_item_meal_plan_needs_action_raises` | Uncompleting meal plan raises NotImplementedError |
| tests/test_grocy_data.py | `test_async_update_meal_plan_sorts_by_day` | Meal plan sorted by date, filters from yesterday |
| tests/test_grocy_data.py | `test_async_update_meal_plan_empty` | Empty meal plan handled |
| tests/test_helpers.py | `test_meal_plan_item_wrapper_generates_picture_url` | Wrapper generates correct picture URL |
| tests/test_helpers.py | `test_meal_plan_item_wrapper_handles_missing_picture` | Wrapper handles None picture |

---

## 7. Calendar

Sync Grocy's iCal calendar feed into Home Assistant's calendar. Includes chores, tasks, meal plans, product expirations, and all other Grocy events.

### Entities

| Entity ID | Description | Icon |
|-----------|-------------|------|
| `calendar.grocy_calendar` | All Grocy events from iCal feed | mdi:calendar |

The calendar syncs at a configurable interval (default: 5 minutes), separate from the 30-second poll interval of other entities.

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `calendar_sync_interval` | 5 | Minutes between calendar syncs |
| `calendar_fix_timezone` | true | Treat UTC times as local time (workaround for Grocy addon timezone bug) |

**Timezone fix:** The Grocy addon may send local times incorrectly marked as UTC in the iCal feed. When enabled (default), UTC times from Grocy are treated as local time without conversion. Disable this if your Grocy instance correctly sends UTC times.

### Services

#### `grocy.sync_calendar`

Manually trigger a calendar sync. No parameters.

### Test Coverage

| Test File | Test Function | What It Validates |
|-----------|---------------|-------------------|
| tests/test_calendar.py | `test_utc_event_treated_as_local_time_when_fix_enabled` | UTC times treated as local when fix enabled |
| tests/test_calendar.py | `test_naive_datetime_converted_from_utc` | Naive datetimes assumed UTC and converted |
| tests/test_calendar.py | `test_utc_event_converted_to_local_when_fix_disabled` | Proper UTC-to-local conversion when fix disabled |
| tests/test_calendar.py | `test_all_day_event_single_day` | Single-day all-day event handling |
| tests/test_calendar.py | `test_all_day_event_multi_day` | Multi-day event spanning |
| tests/test_calendar.py | `test_all_day_event_no_end_date` | All-day event without end date defaults to end of day |
| tests/test_calendar.py | `test_event_without_end_time_defaults_to_one_hour` | Timed event without end defaults to 1 hour |
| tests/test_calendar.py | `test_multiple_events_sorted_by_start_time` | Events sorted chronologically |
| tests/test_calendar.py | `test_event_property_returns_next_event` | Next upcoming event returned correctly |
| tests/test_calendar.py | `test_event_property_returns_none_when_no_events` | Empty calendar returns None |
| tests/test_calendar.py | `test_http_error_handling` | HTTP errors handled gracefully |
| tests/test_calendar.py | `test_daylight_saving_time_transition` | DST transition handling |
| tests/test_calendar.py | `test_different_timezone_pacific` | US/Pacific timezone validation |
| tests/test_calendar.py | `test_fix_timezone_defaults_to_true` | Default timezone fix setting |
| tests/test_calendar.py | `test_fix_timezone_can_be_disabled` | Explicit disable option |
| tests/test_calendar.py | `test_sync_interval_default` | Default 5-minute sync interval |
| tests/test_calendar.py | `test_sync_interval_custom` | Custom sync interval |
| tests/test_services.py | `test_sync_calendar_service_calls_calendar_update` | Sync service triggers calendar update |
| tests/test_services.py | `test_sync_calendar_service_handles_no_calendar_entity` | Missing calendar entity handled gracefully |
| tests/test_services.py | `test_dispatcher_routes_sync_calendar` | Dispatcher routes sync_calendar |

---

## 8. Image Proxy

Proxies product and recipe images from Grocy through Home Assistant. This allows dashboards to display Grocy images without direct access to the Grocy API.

### HTTP Endpoint

`/api/grocy/{picture_type}/{filename}`

- `picture_type`: `productpictures` or `recipepictures`
- `filename`: Base64-encoded filename from Grocy
- Optional query parameter: `width` (default: 400)
- No authentication required

### Test Coverage

| Test File | Test Function | What It Validates |
|-----------|---------------|-------------------|
| tests/test_grocy_data.py | `test_async_setup_endpoint_registers_view` | Endpoint registration |
| tests/test_grocy_data.py | `test_async_setup_endpoint_with_path` | URL path handling for subpath installations |
| tests/test_grocy_data.py | `test_picture_view_get_proxies_request` | Image proxying with correct headers |
| tests/test_grocy_data.py | `test_picture_view_uses_default_width` | Default width=400 |
| tests/test_grocy_data.py | `test_picture_view_requires_no_auth` | No authentication required |
| tests/test_grocy_data.py | `test_picture_view_url_pattern` | URL pattern contains expected placeholders |

---

## 9. Generic CRUD

Create, update, and delete any Grocy entity type through generic services. Useful for automations that need to manage Grocy entities not covered by specific services.

### Services

#### `grocy.add_generic`

Create a new entity of any type.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity_type` | string | Yes | Entity type: `tasks`, `chores`, `batteries`, etc. |
| `data` | object | Yes | Entity data (fields depend on entity type) |

After creation, the corresponding sensor is refreshed (for tasks and chores).

#### `grocy.update_generic`

Update an existing entity.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity_type` | string | Yes | Entity type |
| `object_id` | int | Yes | Grocy object ID |
| `data` | object | Yes | Updated fields |

#### `grocy.delete_generic`

Delete an entity.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity_type` | string | Yes | Entity type (defaults to `tasks` if omitted) |
| `object_id` | int | Yes | Grocy object ID |

### Test Coverage

| Test File | Test Function | What It Validates |
|-----------|---------------|-------------------|
| tests/test_services.py | `test_add_generic_service_refreshes_tasks` | Add generic creates entity and refreshes |
| tests/test_services.py | `test_update_generic_service_refreshes_entity` | Update generic updates and refreshes |
| tests/test_services.py | `test_delete_generic_service_defaults_to_tasks` | Delete generic defaults entity_type to tasks |
| tests/test_services.py | `test_delete_generic_with_explicit_entity_type` | Delete generic accepts explicit entity_type |
| tests/test_services.py | `test_post_generic_refresh_updates_relevant_entities` | Refresh only updates tasks/chores entities |
| tests/test_services.py | `test_post_generic_refresh_for_chores` | Refresh works for chores entity type |
| tests/test_services.py | `test_dispatcher_routes_add_generic` | Dispatcher routes add_generic |
| tests/test_services.py | `test_dispatcher_routes_update_generic` | Dispatcher routes update_generic |
| tests/test_services.py | `test_dispatcher_routes_delete_generic` | Dispatcher routes delete_generic |

---

## 10. Configuration & Setup

Integration setup, reconfiguration, reauthentication, and feature detection.

### Configuration Flow

- **Initial setup**: URL, API Key, Port, Verify SSL, Calendar Sync Interval, Fix Timezone
- **Reconfigure**: Change any setting after setup (triggers integration reload)
- **Reauthenticate**: Update API key when it expires or changes
- **Single instance**: Only one Grocy integration per Home Assistant instance

### Feature Detection

The integration queries Grocy's configuration to detect which features are enabled. Only entities for enabled features are created. Feature flags:

| Grocy Feature Flag | Entities Created |
|--------------------|------------------|
| `FEATURE_FLAG_STOCK` | stock, expired_products, expiring_products, overdue_products, missing_products |
| `FEATURE_FLAG_SHOPPINGLIST` | shopping_list |
| `FEATURE_FLAG_TASKS` | tasks, overdue_tasks |
| `FEATURE_FLAG_CHORES` | chores, overdue_chores |
| `FEATURE_FLAG_RECIPES` | meal_plan |
| `FEATURE_FLAG_BATTERIES` | batteries, overdue_batteries |

### Data Coordinator

All entities (except calendar) are updated every 30 seconds via the data coordinator. Only enabled entities are fetched to minimize API calls.

### Test Coverage

| Test File | Test Function | What It Validates |
|-----------|---------------|-------------------|
| tests/test_config_flow.py | `test_user_step_creates_entry` | Successful entry creation |
| tests/test_config_flow.py | `test_user_step_handles_auth_failure` | Invalid API key error handling |
| tests/test_config_flow.py | `test_user_step_handles_connection_error` | Connection refused error |
| tests/test_config_flow.py | `test_user_step_handles_timeout_error` | Timeout error |
| tests/test_config_flow.py | `test_abort_when_configured` | Single instance enforcement |
| tests/test_config_flow.py | `test_credentials_use_full_payload` | Full credential validation with path extraction |
| tests/test_config_flow.py | `test_reconfigure_step_shows_form` | Reconfigure form display |
| tests/test_config_flow.py | `test_reconfigure_step_updates_entry` | Successful reconfiguration |
| tests/test_config_flow.py | `test_reconfigure_step_handles_error` | Error during reconfiguration |
| tests/test_config_flow.py | `test_reauth_step_shows_confirm_form` | Reauth form display |
| tests/test_config_flow.py | `test_reauth_confirm_updates_entry` | Successful reauth |
| tests/test_config_flow.py | `test_reauth_confirm_handles_error` | Error during reauth |
| tests/test_init.py | `test_async_setup_entry_initializes_integration` | Full setup flow: coordinator, services, proxy, platforms |
| tests/test_init.py | `test_async_setup_entry_raises_not_ready` | Connection failure raises ConfigEntryNotReady |
| tests/test_init.py | `test_async_setup_entry_raises_not_ready_on_timeout` | Timeout raises ConfigEntryNotReady |
| tests/test_init.py | `test_async_setup_entry_raises_not_ready_on_os_error` | OS error raises ConfigEntryNotReady |
| tests/test_init.py | `test_async_unload_entry_cleans_up` | Unload cleans up data and services |
| tests/test_init.py | `test_async_unload_entry_platform_failure` | Partial cleanup on platform failure |
| tests/test_init.py | `test_available_entities_all_features` | All features enabled creates all entities |
| tests/test_init.py | `test_available_entities_stock_only` | Stock-only creates stock entities |
| tests/test_init.py | `test_available_entities_tasks_only` | Tasks-only creates task entities |
| tests/test_init.py | `test_available_entities_chores_only` | Chores-only creates chore entities |
| tests/test_init.py | `test_available_entities_shopping_list_only` | Shopping-list-only creates shopping entities |
| tests/test_init.py | `test_available_entities_recipes_only` | Recipes-only creates meal plan entities |
| tests/test_init.py | `test_available_entities_batteries_only` | Batteries-only creates battery entities |
| tests/test_init.py | `test_available_entities_no_features` | No features creates no entities |
| tests/test_init.py | `test_available_entities_none_config` | None config returns empty list |
| tests/test_coordinator.py | `test_async_update_data_skips_disabled_entities` | Disabled entities are not updated |
| tests/test_coordinator.py | `test_async_update_data_raises_update_failed` | Errors propagated as UpdateFailed |

---

## Cross-Cutting Tests

These tests validate infrastructure shared across all features.

| Test File | Test Function | What It Validates |
|-----------|---------------|-------------------|
| tests/test_entities.py | `test_sensor_exists_fn` | All sensor descriptions have correct exists_fn |
| tests/test_entities.py | `test_binary_sensor_exists_fn` | All binary sensor descriptions have correct exists_fn |
| tests/test_entities.py | `test_coordinator_data_setitem_getitem` | CoordinatorData dict-like access |
| tests/test_entities.py | `test_coordinator_data_defaults_to_none` | CoordinatorData defaults to None |
| tests/test_todo.py | `test_calculate_days_until_none_returns_zero` | Days calculation handles None |
| tests/test_todo.py | `test_calculate_days_until_date_only_future` | Future date calculation |
| tests/test_todo.py | `test_calculate_days_until_date_only_past` | Past date calculation |
| tests/test_todo.py | `test_calculate_days_until_datetime` | Datetime calculation |
| tests/test_todo.py | `test_calculate_days_until_datetime_date_only` | Datetime as date calculation |
| tests/test_todo.py | `test_calculate_item_status_overdue` | Overdue status mapping |
| tests/test_todo.py | `test_calculate_item_status_future` | Future status mapping |
| tests/test_todo.py | `test_todo_item_raises_for_unknown_type` | Unknown type raises NotImplementedError |
| tests/test_todo.py | `test_get_grocy_item_finds_by_id` | Item lookup by ID |
| tests/test_todo.py | `test_get_grocy_item_finds_meal_plan_wrapper` | MealPlanItemWrapper lookup |
| tests/test_todo.py | `test_todo_items_none_data` | None data returns empty list |
| tests/test_todo.py | `test_todo_exists_fn_checks_available_entities` | Todo exists_fn validation |
| tests/test_todo.py | `test_async_create_todo_item_unsupported_raises` | Unsupported create raises error |
| tests/test_services.py | `test_async_setup_services_registers_all_services` | All 13 services registered |
| tests/test_services.py | `test_async_setup_services_skips_if_already_registered` | No duplicate registration |
| tests/test_services.py | `test_async_unload_services_removes_all` | All services removed on unload |
| tests/test_services.py | `test_async_unload_services_noop_if_not_registered` | Graceful no-op if not registered |
| tests/test_services.py | `test_async_force_update_entity_updates_matching_entity` | Force update targets correct entity |
| tests/test_services.py | `test_async_force_update_entity_ignores_missing` | Force update handles missing entity |
| tests/test_grocy_data.py | `test_async_update_data_dispatches_to_correct_method` | Data dispatch routing |
| tests/test_grocy_data.py | `test_async_update_data_returns_none_for_unknown_key` | Unknown key returns None |
| tests/test_grocy_data.py | `test_async_get_config` | Config retrieval from Grocy API |
| tests/test_grocy_data.py | `test_all_entity_keys_have_update_methods` | All 13 entity keys mapped to update methods |
| tests/test_helpers.py | `test_extract_base_url_and_path_variants` | URL parsing for simple and complex URLs |
| tests/test_helpers.py | `test_model_to_dict_prefers_as_dict` | Serialization prefers as_dict() |
| tests/test_helpers.py | `test_model_to_dict_falls_back_to_model_dump` | Serialization falls back to model_dump() |
| tests/test_helpers.py | `test_model_to_dict_uses_dunder_dict` | Serialization falls back to __dict__ |
| tests/test_helpers.py | `test_model_to_dict_returns_empty_dict` | Empty object returns {} |
| tests/test_json_encoder.py | `test_encodes_date` | JSON encodes date objects |
| tests/test_json_encoder.py | `test_encodes_time` | JSON encodes time objects |
| tests/test_json_encoder.py | `test_encodes_datetime_via_parent` | JSON encodes datetime objects |
| tests/test_json_encoder.py | `test_encodes_regular_types` | JSON passes through regular types |
| tests/test_json_encoder.py | `test_encodes_date_min` | JSON encodes minimum date |
| tests/test_json_encoder.py | `test_encodes_time_with_microseconds` | JSON encodes time with microseconds |
