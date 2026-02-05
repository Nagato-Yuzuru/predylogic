"""
Shared fixtures for rule_engine tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import new_class
from typing import TypedDict, TypeVar, cast

import pytest
from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import BaseModel

from predylogic import Registry, RegistryManager
from predylogic.rule_engine.base import AndNode, LeafNode, NotNode, OrNode, RefNode

M = TypeVar("M", bound=BaseModel)
# ============================================================================
# Context Types (diverse class types to validate engine works with any class)
# ============================================================================


@dataclass
class User:
    """Dataclass context type."""

    age: int
    active: bool
    name: str = "Anonymous"


class OrderCtx(TypedDict):
    """TypedDict context type."""

    order_id: str
    total: float
    is_priority: bool


class Product:
    """Plain class context type."""

    def __init__(self, name: str, price: float, *, in_stock: bool):
        self.name = name
        self.price = price
        self.in_stock = in_stock


# ============================================================================
# Registry Fixtures
# ============================================================================


@pytest.fixture
def registry_manager() -> RegistryManager:
    """Provides a fresh RegistryManager instance."""
    return RegistryManager()


@pytest.fixture
def user_registry(registry_manager: RegistryManager) -> Registry[User]:
    """Provides a Registry for User context with sample rules."""
    registry = Registry[User]("user_registry")

    @registry.rule_def()
    def is_adult(user: User, min_age: int = 18) -> bool:
        """Check if user is at least min_age years old."""
        return user.age >= min_age

    @registry.rule_def()
    def is_active(user: User) -> bool:
        """Check if user is active."""
        return user.active

    @registry.rule_def()
    def is_named(user: User, name: str) -> bool:
        """Check if user has specific name."""
        return user.name == name

    registry_manager.add_register("user_registry", registry)
    return registry


@pytest.fixture
def order_registry(registry_manager: RegistryManager) -> Registry[OrderCtx]:
    """Provides a Registry for OrderCtx (TypedDict) with sample rules."""
    registry = Registry[OrderCtx]("order_registry")

    @registry.rule_def()
    def min_total(order: OrderCtx, amount: float) -> bool:
        """Check if order total meets minimum amount."""
        return order["total"] >= amount

    @registry.rule_def()
    def is_priority(order: OrderCtx) -> bool:
        """Check if order is priority."""
        return order["is_priority"]

    registry_manager.add_register("order_registry", registry)
    return registry


@pytest.fixture
def product_registry(registry_manager: RegistryManager) -> Registry[Product]:
    """Provides a Registry for Product (plain class) with sample rules."""
    registry = Registry[Product]("product_registry")

    @registry.rule_def()
    def min_price(product: Product, price: float) -> bool:
        """Check if product price meets minimum."""
        return product.price >= price

    @registry.rule_def()
    def in_stock(product: Product) -> bool:
        """Check if product is in stock."""
        return product.in_stock

    registry_manager.add_register("product_registry", registry)
    return registry


# ============================================================================
# Sample Context Instances
# ============================================================================


@pytest.fixture
def adult_user() -> User:
    """Provides an adult active user."""
    return User(age=25, active=True, name="Alice")


@pytest.fixture
def minor_user() -> User:
    """Provides a minor inactive user."""
    return User(age=16, active=False, name="Bob")


@pytest.fixture
def priority_order() -> OrderCtx:
    """Provides a priority order."""
    return {"order_id": "ORD-001", "total": 150.0, "is_priority": True}


@pytest.fixture
def regular_order() -> OrderCtx:
    """Provides a regular order."""
    return {"order_id": "ORD-002", "total": 50.0, "is_priority": False}


@pytest.fixture
def expensive_product() -> Product:
    """Provides an expensive in-stock product."""
    return Product(name="Laptop", price=1200.0, in_stock=True)


@pytest.fixture
def cheap_product() -> Product:
    """Provides a cheap out-of-stock product."""
    return Product(name="Cable", price=5.0, in_stock=False)


def model_mock(model: type[M]) -> type[ModelFactory[M]]:
    def f(ns):
        ns["__model__"] = model
        ns["__module__"] = __name__

    return cast(
        "type[ModelFactory[M]]",
        new_class(
            f"{model.__name__}Mock",
            (ModelFactory[M], model),
            {},
            f,
        ),
    )


def create_node_factories(rule_def_types):
    """
    Create factory classes for LogicNodes with proper generic types.

    Args:
        rule_def_types: The union type from SchemaGenerator.rule_def_types

    Returns:
        Tuple of (LeafFactory, RefFactory, AndFactory, OrFactory, NotFactory)
    """

    # Create factories for each node type with the correct generic
    leaf_factory = model_mock(LeafNode[rule_def_types])
    ref_factory = model_mock(RefNode[rule_def_types])
    and_factory = model_mock(AndNode[rule_def_types])
    or_factory = model_mock(OrNode[rule_def_types])
    not_factory = model_mock(NotNode[rule_def_types])

    return leaf_factory, ref_factory, and_factory, or_factory, not_factory
