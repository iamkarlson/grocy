from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any


@dataclass
class DummyRecipe:
    id: int = 1
    name: str = "Recipe"
    description: str | None = "Recipe description"
    picture_file_name: str | None = "recipe.jpg"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "picture_file_name": self.picture_file_name,
        }


@dataclass
class DummyMealPlanItem:
    id: int = 1
    day: dt.date = field(default_factory=lambda: dt.date.today() + dt.timedelta(days=1))
    recipe: DummyRecipe = field(default_factory=DummyRecipe)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "day": self.day.isoformat(),
            "recipe": self.recipe.as_dict() if self.recipe else None,
        }


@dataclass
class DummyChore:
    id: int = 1
    name: str = "Chore"
    description: str | None = "Chore description"
    next_estimated_execution_time: dt.datetime | dt.date | None = field(
        default_factory=lambda: dt.datetime.now() + dt.timedelta(days=1)
    )
    track_date_only: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "next_estimated_execution_time": self.next_estimated_execution_time,
            "track_date_only": self.track_date_only,
        }


@dataclass
class DummyBattery:
    id: int = 1
    name: str = "Battery"
    description: str | None = "Battery description"
    next_estimated_charge_time: dt.date | None = field(
        default_factory=lambda: dt.date.today() + dt.timedelta(days=1)
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "next_estimated_charge_time": self.next_estimated_charge_time,
        }


@dataclass
class DummyTask:
    id: int = 1
    name: str = "Task"
    description: str | None = "Task description"
    due_date: dt.date | None = field(default_factory=lambda: dt.date.today())

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "due_date": self.due_date,
        }


@dataclass
class DummyProduct:
    id: int = 1
    name: str = "Product"
    available_amount: float = 1.0
    description: str | None = "Product description"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "available_amount": self.available_amount,
            "description": self.description,
        }


@dataclass
class DummyCurrentStockProduct:
    picture_file_name: str | None = "product.jpg"

    def as_dict(self) -> dict[str, Any]:
        return {"picture_file_name": self.picture_file_name}


@dataclass
class DummyCurrentStockResponse:
    product: DummyCurrentStockProduct = field(default_factory=DummyCurrentStockProduct)
    available_amount: float = 1.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "available_amount": self.available_amount,
            "product": self.product.as_dict() if self.product else None,
        }


@dataclass
class DummyShoppingProduct:
    name: str = "Listed product"

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name}


@dataclass
class DummyShoppingListProduct:
    id: int = 1
    amount: float = 2.0
    note: str | None = "Need soon"
    product: DummyShoppingProduct | None = field(default_factory=DummyShoppingProduct)
    done: bool | None = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "amount": self.amount,
            "note": self.note,
            "done": self.done,
            "product": self.product.as_dict() if self.product else None,
        }


def as_namespace(obj: Any) -> SimpleNamespace:
    return SimpleNamespace(**obj.as_dict())
