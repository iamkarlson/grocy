"""Communication with Grocy API."""

from __future__ import annotations

import base64
import logging
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone, tzinfo
from http import HTTPStatus
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiohttp import ClientError, hdrs, web
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.http import HomeAssistantView

from grocy import Grocy
from grocy.data_models.battery import Battery
from grocy.data_models.chore import Chore
from grocy.data_models.generic import EntityType
from grocy.data_models.product import Product

from .const import (
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
from .helpers import MealPlanItemWrapper, RecipeWrapper, extract_base_url_and_path

_LOGGER = logging.getLogger(__name__)


class GrocyData:
    """Handles communication and gets the data."""

    def __init__(self, hass: HomeAssistant, api: Grocy, grocy_url: str) -> None:
        """Initialize Grocy data."""
        self.hass = hass
        self.api = api
        self.due_soon_days: int | None = None
        self.entity_update_method = {
            ATTR_STOCK: self.async_update_stock,
            ATTR_CHORES: self.async_update_chores,
            ATTR_TASKS: self.async_update_tasks,
            ATTR_SHOPPING_LIST: self.async_update_shopping_list,
            ATTR_EXPIRING_PRODUCTS: self.async_update_expiring_products,
            ATTR_EXPIRED_PRODUCTS: self.async_update_expired_products,
            ATTR_OVERDUE_PRODUCTS: self.async_update_overdue_products,
            ATTR_MISSING_PRODUCTS: self.async_update_missing_products,
            ATTR_MEAL_PLAN: self.async_update_meal_plan,
            ATTR_OVERDUE_CHORES: self.async_update_overdue_chores,
            ATTR_OVERDUE_TASKS: self.async_update_overdue_tasks,
            ATTR_BATTERIES: self.async_update_batteries,
            ATTR_OVERDUE_BATTERIES: self.async_update_overdue_batteries,
            ATTR_RECIPES: self.async_update_recipes,
        }
        self._grocy_url = grocy_url
        self._server_zone: tzinfo | None = None

    def _server_now(self) -> datetime:
        """
        Return the current time on the Grocy server clock, as a naive datetime.

        Grocy stores due times in server local time, which can differ from the
        Home Assistant time zone (#83). The zone is read once from Grocy, so
        call this from the executor.
        """
        if self._server_zone is None:
            server_time = self.api.system.time()
            try:
                self._server_zone = ZoneInfo(server_time.timezone)
            except ZoneInfoNotFoundError, ValueError:
                offset = server_time.time_local - server_time.time_utc
                self._server_zone = timezone(offset)
        return datetime.now(self._server_zone).replace(tzinfo=None)

    async def async_update_data(self, entity_key):
        """Update data."""
        if entity_key in self.entity_update_method:
            return await self.entity_update_method[entity_key]()

    def _add_picture_file_names(self, products: list[Product]) -> None:
        """
        Fill in the picture file name of each product, in place.

        ``Product.from_stock_response`` leaves ``picture_file_name`` unset, so
        stock products carry no picture. Reading the details of every product
        would be one request each, while the product entities carry the same
        file names in a single request.
        """
        try:
            entities = self.api.generic.list(EntityType.PRODUCTS)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.debug("Could not read the product pictures from Grocy")
            return

        file_names = {
            str(entity.get("id")): entity.get("picture_file_name")
            for entity in entities
            if isinstance(entity, Mapping)
        }
        for product in products:
            product.picture_file_name = file_names.get(str(product.id))

    async def async_update_stock(self) -> list[Product]:
        """Update stock data."""

        def wrapper() -> list[Product]:
            products = self.api.stock.current()
            self._add_picture_file_names(products)
            return products

        return await self.hass.async_add_executor_job(wrapper)

    async def async_update_chores(self):
        """Update chores data."""

        def wrapper() -> list[Chore]:
            return self.api.chores.list(get_details=True)

        return await self.hass.async_add_executor_job(wrapper)

    async def async_update_overdue_chores(self):
        """Update overdue chores data."""

        def wrapper():
            query_filter = [f"next_estimated_execution_time<{self._server_now()}"]
            return self.api.chores.list(get_details=True, query_filters=query_filter)

        return await self.hass.async_add_executor_job(wrapper)

    async def async_get_config(self):
        """Get the configuration from Grocy."""

        def wrapper():
            config = self.api.system.config()
            try:
                # Some Grocy setups expose this key in lowercase only.
                for key in ("STOCK_DUE_SOON_DAYS", "stock_due_soon_days"):
                    raw_val = self.api.users.get_setting(key)
                    _LOGGER.debug("Read user setting %s from Grocy: %r", key, raw_val)

                    val = raw_val
                    if isinstance(raw_val, dict):
                        # Handle alternative payload shapes returned by library/API.
                        for field in ("value", "setting_value"):
                            if field in raw_val:
                                val = raw_val[field]
                                break

                    if val is None:
                        continue

                    try:
                        self.due_soon_days = int(val)
                        _LOGGER.debug(
                            "Using due_soon_days=%s from key %s",
                            self.due_soon_days,
                            key,
                        )
                        break
                    except TypeError, ValueError:
                        _LOGGER.debug(
                            "Ignoring invalid due soon setting value for key %s: %r",
                            key,
                            val,
                        )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.debug("Could not read STOCK_DUE_SOON_DAYS from Grocy")
            return config

        return await self.hass.async_add_executor_job(wrapper)

    async def async_update_tasks(self):
        """Update tasks data."""
        return await self.hass.async_add_executor_job(self.api.tasks.list)

    async def async_update_overdue_tasks(self):
        """Update overdue tasks data."""

        def wrapper():
            and_query_filter = [
                f"due_date<{self._server_now().date()}",
                # It's not possible to pass an empty value to Grocy
                # so use a regex that matches non-empty values
                # to exclude empty str due_date.
                r"due_date§.*\S.*",
            ]
            return self.api.tasks.list(query_filters=and_query_filter)

        return await self.hass.async_add_executor_job(wrapper)

    async def async_update_shopping_list(self):
        """Update shopping list data."""

        def wrapper():
            return self.api.shopping_list.items(get_details=True)

        return await self.hass.async_add_executor_job(wrapper)

    async def async_update_expiring_products(self):
        """Update expiring products data."""

        def wrapper():
            # Pass the Grocy-configured due_soon_days through. Without it the
            # API defaults to 5 days regardless of the STOCK_DUE_SOON_DAYS
            # system setting.
            _LOGGER.debug(
                "Fetching expiring products with due_soon_days=%s",
                self.due_soon_days,
            )
            return self.api.stock.due_products(
                get_details=True, due_soon_days=self.due_soon_days
            )

        return await self.hass.async_add_executor_job(wrapper)

    async def async_update_expired_products(self):
        """Update expired products data."""

        def wrapper():
            return self.api.stock.expired_products(get_details=True)

        return await self.hass.async_add_executor_job(wrapper)

    async def async_update_overdue_products(self):
        """Update overdue products data."""

        def wrapper():
            return self.api.stock.overdue_products(get_details=True)

        return await self.hass.async_add_executor_job(wrapper)

    async def async_update_missing_products(self):
        """Update missing products data."""

        def wrapper():
            return self.api.stock.missing_products(get_details=True)

        return await self.hass.async_add_executor_job(wrapper)

    async def async_update_meal_plan(self):
        """Update meal plan data."""

        def wrapper():
            # The >= condition is broken before Grocy 3.3.1.
            # So use > to maintain backward compatibility.
            yesterday = self._server_now() - timedelta(1)
            query_filter = [f"day>{yesterday.date()}"]
            meal_plan = self.api.meal_plan.items(
                get_details=True, query_filters=query_filter
            )
            plan = [MealPlanItemWrapper(item) for item in meal_plan]
            return sorted(plan, key=lambda item: item.meal_plan.day)

        return await self.hass.async_add_executor_job(wrapper)

    async def async_update_batteries(self) -> list[Battery]:
        """Update batteries."""

        def wrapper():
            return self.api.batteries.list(get_details=True)

        return await self.hass.async_add_executor_job(wrapper)

    async def async_update_overdue_batteries(self) -> list[Battery]:
        """Update overdue batteries."""

        def wrapper():
            filter_query = [f"next_estimated_charge_time<{self._server_now()}"]
            return self.api.batteries.list(filter_query, get_details=True)

        return await self.hass.async_add_executor_job(wrapper)

    async def async_update_recipes(self) -> list[RecipeWrapper]:
        """Update recipes data."""

        def wrapper() -> list[RecipeWrapper]:
            recipes = self.api.generic.list(EntityType.RECIPES) or []
            fulfillment = self.api.recipes.all_fulfillment() or []

            fulfillment_map = {f.recipe_id: f.need_fulfilled for f in fulfillment}

            wrapped_recipes = []
            for r in recipes:
                recipe_id = r.get("id")
                need_fulfilled = fulfillment_map.get(recipe_id, False)
                recipe_wrapper = RecipeWrapper(r, need_fulfilled, self._grocy_url)
                if recipe_wrapper.recipe["type"] == "normal":
                    wrapped_recipes.append(recipe_wrapper)
            return wrapped_recipes

        return await self.hass.async_add_executor_job(wrapper)


# Only the picture groups that the integration links to. Other groups, for
# example userfiles, must not be readable through this view without a login.
PICTURE_GROUPS = frozenset({"recipepictures", "productpictures"})
DEFAULT_PICTURE_WIDTH = 400
MAX_PICTURE_WIDTH = 2000
_PICTURE_VIEW_REGISTERED = f"{DOMAIN}_picture_view_registered"
_FORWARDED_HEADERS = (
    hdrs.CACHE_CONTROL,
    hdrs.CONTENT_DISPOSITION,
    hdrs.CONTENT_LENGTH,
    hdrs.CONTENT_TYPE,
    hdrs.CONTENT_ENCODING,
)


async def async_setup_endpoint_for_image_proxy(hass: HomeAssistant) -> None:
    """
    Register the picture proxy view once per Home Assistant run.

    Home Assistant cannot remove a view, and a second registration never
    answers (#72). The view reads the settings of the entry on each request.
    """
    if hass.data.get(_PICTURE_VIEW_REGISTERED):
        return
    hass.http.register_view(GrocyPictureView(hass))
    hass.data[_PICTURE_VIEW_REGISTERED] = True


def _grocy_base_url(data: Mapping[str, Any]) -> str:
    """Return the Grocy URL with port and path from the entry data."""
    (base_url, path) = extract_base_url_and_path(data.get(CONF_URL) or "")
    port = data.get(CONF_PORT)
    return f"{base_url}:{port}/{path}" if path else f"{base_url}:{port}"


def _is_file_name(encoded: str) -> bool:
    """Return True if the value is base64 of a file name without a path."""
    try:
        name = base64.b64decode(encoded, validate=True).decode("utf-8")
    except ValueError:  # also binascii.Error and UnicodeDecodeError
        return False
    return bool(name) and "/" not in name and "\\" not in name


def _picture_width(raw: str | None) -> int:
    """Return the requested picture width, or the default for a bad value."""
    try:
        width = int(raw) if raw is not None else DEFAULT_PICTURE_WIDTH
    except ValueError:
        return DEFAULT_PICTURE_WIDTH
    return min(max(width, 1), MAX_PICTURE_WIDTH)


class GrocyPictureView(HomeAssistantView):
    """Proxy Grocy pictures, so that dashboards can show them without the API key."""

    requires_auth = False
    url = "/api/grocy/{picture_type}/{filename}"
    name = "api:grocy:picture"

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def get(self, request, picture_type: str, filename: str) -> web.Response:
        """GET request for the image."""
        coordinator = self._hass.data.get(DOMAIN)
        if (
            coordinator is None
            or picture_type not in PICTURE_GROUPS
            or not _is_file_name(filename)
        ):
            raise web.HTTPNotFound

        # Read the settings now, so that a changed URL or API key applies at once.
        data = coordinator.config_entry.data
        width = _picture_width(request.query.get("width"))
        url = f"{_grocy_base_url(data)}/api/files/{picture_type}/{filename}"
        url = f"{url}?force_serve_as=picture&best_fit_width={width}"
        headers = {"GROCY-API-KEY": data[CONF_API_KEY], "accept": "*/*"}
        session = async_get_clientsession(
            self._hass, verify_ssl=data.get(CONF_VERIFY_SSL, False)
        )

        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status != HTTPStatus.OK:
                    raise web.HTTPNotFound
                response_headers = {
                    name: value
                    for name, value in resp.headers.items()
                    if name in _FORWARDED_HEADERS
                }
                body = await resp.read()
        except (ClientError, TimeoutError) as error:
            raise web.HTTPBadGateway from error
        return web.Response(body=body, headers=response_headers)
