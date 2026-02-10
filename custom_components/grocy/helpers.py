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
        return model.model_dump(mode="json")
    if hasattr(model, "__dict__"):
        return {
            key: value
            for key, value in model.__dict__.items()
            if not key.startswith("_")
        }
    return {}
