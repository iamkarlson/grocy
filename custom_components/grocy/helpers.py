"""Helpers for Grocy."""

from __future__ import annotations

import base64
from typing import Any
from urllib.parse import urlparse, urlunparse

from grocy.data_models.meal_items import MealPlanItem


def _picture_url(picture_group: str, picture_file_name: str | None) -> str | None:
    """
    Return the proxy URL of a picture in the given group, or None.

    Grocy expects the file name as base64 of its UTF-8 bytes (#74). When the
    base64 form contains "/", neither Home Assistant nor Grocy can route it.
    """
    if not picture_file_name:
        return None
    encoded = base64.b64encode(picture_file_name.encode("utf-8")).decode("ascii")
    if "/" in encoded:
        return None
    return f"/api/grocy/{picture_group}/{encoded}"


def recipe_picture_url(picture_file_name: str | None) -> str | None:
    """Return the proxy URL of a recipe picture, or None."""
    return _picture_url("recipepictures", picture_file_name)


def product_picture_url(picture_file_name: str | None) -> str | None:
    """Return the proxy URL of a product picture, or None."""
    return _picture_url("productpictures", picture_file_name)


def extract_base_url_and_path(url: str) -> tuple[str, str]:
    """Extract the base url and path from a given URL."""
    parsed_url = urlparse(url)

    return (f"{parsed_url.scheme}://{parsed_url.netloc}", parsed_url.path.strip("/"))


def split_url_and_port(url: str, port: int) -> tuple[str, int]:
    """
    Return the URL without an explicit port, and the port to use.

    A port written into the URL (``http://host:9283``) wins over ``port``,
    because the integration appends the port field to the URL and
    ``http://host:9283:9192`` cannot be reached. Without an explicit port
    both values come back unchanged.
    """
    parsed_url = urlparse(url)
    try:
        explicit_port = parsed_url.port
    except ValueError:
        return url, port
    if explicit_port is None:
        return url, port

    host = parsed_url.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    if parsed_url.username:
        userinfo = parsed_url.username
        if parsed_url.password:
            userinfo = f"{userinfo}:{parsed_url.password}"
        host = f"{userinfo}@{host}"

    return urlunparse(parsed_url._replace(netloc=host)), explicit_port


class RecipeWrapper:
    """Wrapper around a grocy Recipe dictionary with fulfillment information."""

    def __init__(
        self, recipe: dict[str, Any], need_fulfilled: bool, grocy_url: str
    ) -> None:
        self._recipe = recipe
        self._need_fulfilled = need_fulfilled
        self._grocy_url = grocy_url

    @property
    def recipe(self) -> dict[str, Any]:
        """Return the wrapped recipe dict."""
        return self._recipe

    @property
    def all_ingredients_in_stock(self) -> bool:
        """Return whether all ingredients are in stock."""
        return self._need_fulfilled

    @property
    def picture_url(self) -> str | None:
        """Proxy URL to the picture."""
        return recipe_picture_url(self._recipe.get("picture_file_name"))

    @property
    def url(self) -> str | None:
        """Return the recipe link URL."""
        return (
            self._grocy_url
            + "/recipes?recipe="
            + str(self._recipe.get("id"))
            + "#fullscreen"
        )

    def as_dict(self) -> dict[str, Any]:
        """Return serialized attributes including the proxy picture URL and in stock status."""
        props = dict(self._recipe)
        props["all_ingredients_in_stock"] = self.all_ingredients_in_stock
        props["picture_url"] = self.picture_url
        props["url"] = self.url
        return props


class MealPlanItemWrapper:
    """Wrapper around a grocy MealPlanItem."""

    def __init__(self, meal_plan: MealPlanItem) -> None:
        self._meal_plan = meal_plan

    @property
    def meal_plan(self) -> MealPlanItem:
        """Return the wrapped MealPlanItem."""
        return self._meal_plan

    @property
    def picture_url(self) -> str | None:
        """Proxy URL to the picture."""
        recipe = self.meal_plan.recipe
        return recipe_picture_url(recipe.picture_file_name if recipe else None)

    def as_dict(self) -> dict[str, Any]:
        """Return serialized attributes including the proxy picture URL."""
        props = model_to_dict(self.meal_plan)
        props["picture_url"] = self.picture_url
        return props


def model_to_dict(model: Any) -> dict[str, Any]:
    """Convert Grocy model objects into serializable dictionaries."""
    if hasattr(model, "as_dict"):
        return model.as_dict()
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json", warnings=False)
    if hasattr(model, "__dict__"):
        return {
            key: value
            for key, value in model.__dict__.items()
            if not key.startswith("_")
        }
    return {}


def product_to_dict(product: Any) -> dict[str, Any]:
    """Convert a Grocy product into a dictionary including its picture URL."""
    props = model_to_dict(product)
    props["picture_url"] = product_picture_url(
        getattr(product, "picture_file_name", None)
    )
    return props
