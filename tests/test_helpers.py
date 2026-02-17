"""Helper function tests.

Features: meal_planning, cross_cutting
See: docs/FEATURES.md
"""

from __future__ import annotations

import base64
import datetime as dt
import warnings

import pytest
from pydantic import BaseModel

from custom_components.grocy.helpers import (
    MealPlanItemWrapper,
    extract_base_url_and_path,
    model_to_dict,
)
from tests.factories import (
    DummyMealPlanItem,
    DummyRecipe,
)


@pytest.mark.feature("cross_cutting")
def test_extract_base_url_and_path_variants() -> None:
    """Verify URL parsing for simple and complex URLs."""
    base, path = extract_base_url_and_path("https://demo.grocy.info")
    assert base == "https://demo.grocy.info"
    assert path == ""

    base, path = extract_base_url_and_path("https://demo.grocy.info/grocy/api/")
    assert base == "https://demo.grocy.info"
    assert path == "grocy/api"


@pytest.mark.feature("meal_planning")
def test_meal_plan_item_wrapper_generates_picture_url() -> None:
    """Verify wrapper generates correct picture URL."""
    item = DummyMealPlanItem(day=dt.date.today() + dt.timedelta(days=2))
    wrapper = MealPlanItemWrapper(item)

    encoded = base64.b64encode(item.recipe.picture_file_name.encode("ascii")).decode(
        "ascii"
    )
    assert wrapper.picture_url == f"/api/grocy/recipepictures/{encoded}"

    payload = wrapper.as_dict()
    assert payload["picture_url"] == wrapper.picture_url
    assert payload["recipe"]["picture_file_name"] == item.recipe.picture_file_name


@pytest.mark.feature("meal_planning")
def test_meal_plan_item_wrapper_handles_missing_picture() -> None:
    """Verify wrapper handles None picture."""
    recipe = DummyRecipe(picture_file_name=None)
    item = DummyMealPlanItem(recipe=recipe)
    wrapper = MealPlanItemWrapper(item)

    assert wrapper.picture_url is None


class WithAsDict:
    def as_dict(self) -> dict[str, int]:
        return {"a": 1}


class WithModelDump:
    def model_dump(self, mode: str = "json", **kwargs: object) -> dict[str, int]:
        assert mode == "json"
        return {"b": 2}


class WithDictAttrs:
    def __init__(self) -> None:
        self.c = 3
        self._ignore = "hidden"


class Empty:
    pass


@pytest.mark.feature("cross_cutting")
def test_model_to_dict_prefers_as_dict() -> None:
    """Verify serialization prefers as_dict()."""
    assert model_to_dict(WithAsDict()) == {"a": 1}


@pytest.mark.feature("cross_cutting")
def test_model_to_dict_falls_back_to_model_dump() -> None:
    """Verify serialization falls back to model_dump()."""
    assert model_to_dict(WithModelDump()) == {"b": 2}


@pytest.mark.feature("cross_cutting")
def test_model_to_dict_uses_dunder_dict() -> None:
    """Verify serialization falls back to __dict__."""
    assert model_to_dict(WithDictAttrs()) == {"c": 3}


@pytest.mark.feature("cross_cutting")
def test_model_to_dict_returns_empty_dict() -> None:
    """Verify empty object returns {}."""
    assert model_to_dict(Empty()) == {}


class _UserfieldModel(BaseModel):
    """Mimics a grocy-py model with a userfields field."""

    name: str
    userfields: dict | None = None


@pytest.mark.feature("cross_cutting")
def test_model_to_dict_suppresses_userfields_warning() -> None:
    """Verify model_to_dict does not emit PydanticSerializationUnexpectedValue.

    The Grocy API returns [] for empty userfields. grocy-py assigns this
    directly to the Pydantic model attribute, bypassing validation.
    model_to_dict must not emit warnings when serializing such models.
    See: https://github.com/iamkarlson/grocy/issues/33
    """
    model = _UserfieldModel(name="test")
    # Simulate grocy-py assigning [] directly (bypasses Pydantic validation)
    model.userfields = []  # type: ignore[assignment]

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = model_to_dict(model)

    assert result["name"] == "test"
    assert result["userfields"] == []
