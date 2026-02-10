from __future__ import annotations

import base64
import datetime as dt

from custom_components.grocy.helpers import (
    MealPlanItemWrapper,
    extract_base_url_and_path,
    model_to_dict,
)
from tests.factories import (
    DummyMealPlanItem,
    DummyRecipe,
)


def test_extract_base_url_and_path_variants() -> None:
    base, path = extract_base_url_and_path("https://demo.grocy.info")
    assert base == "https://demo.grocy.info"
    assert path == ""

    base, path = extract_base_url_and_path("https://demo.grocy.info/grocy/api/")
    assert base == "https://demo.grocy.info"
    assert path == "grocy/api"


def test_meal_plan_item_wrapper_generates_picture_url() -> None:
    item = DummyMealPlanItem(day=dt.date.today() + dt.timedelta(days=2))
    wrapper = MealPlanItemWrapper(item)

    encoded = base64.b64encode(item.recipe.picture_file_name.encode("ascii")).decode(
        "ascii"
    )
    assert wrapper.picture_url == f"/api/grocy/recipepictures/{encoded}"

    payload = wrapper.as_dict()
    assert payload["picture_url"] == wrapper.picture_url
    assert payload["recipe"]["picture_file_name"] == item.recipe.picture_file_name


def test_meal_plan_item_wrapper_handles_missing_picture() -> None:
    recipe = DummyRecipe(picture_file_name=None)
    item = DummyMealPlanItem(recipe=recipe)
    wrapper = MealPlanItemWrapper(item)

    assert wrapper.picture_url is None



class WithAsDict:
    def as_dict(self) -> dict[str, int]:
        return {"a": 1}


class WithModelDump:
    def model_dump(self, mode: str = "json") -> dict[str, int]:
        assert mode == "json"
        return {"b": 2}


class WithDictAttrs:
    def __init__(self) -> None:
        self.c = 3
        self._ignore = "hidden"


class Empty:
    pass


def test_model_to_dict_prefers_as_dict() -> None:
    assert model_to_dict(WithAsDict()) == {"a": 1}


def test_model_to_dict_falls_back_to_model_dump() -> None:
    assert model_to_dict(WithModelDump()) == {"b": 2}


def test_model_to_dict_uses_dunder_dict() -> None:
    assert model_to_dict(WithDictAttrs()) == {"c": 3}


def test_model_to_dict_returns_empty_dict() -> None:
    assert model_to_dict(Empty()) == {}
