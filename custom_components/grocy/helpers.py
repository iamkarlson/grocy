"""Helpers for Grocy."""

from __future__ import annotations

import base64
from typing import Any
from urllib.parse import urlparse

from grocy.data_models.meal_items import MealPlanItem


def extract_base_url_and_path(url: str) -> tuple[str, str]:
    """Extract the base url and path from a given URL."""
    parsed_url = urlparse(url)

    return (f"{parsed_url.scheme}://{parsed_url.netloc}", parsed_url.path.strip("/"))


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
        picture_file_name = self._recipe.get("picture_file_name")
        if picture_file_name:
            b64name = base64.b64encode(picture_file_name.encode("ascii"))
            return f"/api/grocy/recipepictures/{str(b64name, 'utf-8')}"
        return None

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
        if recipe and recipe.picture_file_name:
            b64name = base64.b64encode(recipe.picture_file_name.encode("ascii"))
            return f"/api/grocy/recipepictures/{str(b64name, 'utf-8')}"
        return None

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
