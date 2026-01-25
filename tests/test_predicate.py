from __future__ import annotations

import inspect
from typing import TypedDict, get_type_hints

import pytest

from predylogic.predicate import Predicate
from predylogic.register import Registry, rule_def
from predylogic.register.registry import RegistryManager


class UserCtx(TypedDict):
    age: int
    active: bool


@pytest.fixture
def manager():
    return RegistryManager()


@pytest.fixture
def register(manager):
    return Registry[UserCtx]("test_register", _manager=manager)


def test_rule_registration_and_manager_lookup(register: Registry[UserCtx], manager: RegistryManager):
    @rule_def(register)
    def is_user_over_age(user_ctx: UserCtx, threshold: int) -> bool:
        return user_ctx["age"] >= threshold

    assert manager.get_register("test_register") is register
    assert manager.get_register("missing") is None

    assert "is_user_over_age" in register
    assert register["is_user_over_age"] is is_user_over_age

    predicate = is_user_over_age(18)
    assert isinstance(predicate, Predicate)
    assert predicate({"age": 18, "active": True})
    assert not predicate({"age": 17, "active": True})


def test_predicate_combinations():
    adult = Predicate(lambda ctx: ctx["age"] >= 18)
    active = Predicate(lambda ctx: ctx["active"])

    adult_and_active = adult & active
    active_or_adult = active | adult
    not_adult = ~adult

    assert adult_and_active({"age": 25, "active": True})
    assert not adult_and_active({"age": 25, "active": False})

    assert active_or_adult({"age": 17, "active": True})
    assert not active_or_adult({"age": 16, "active": False})

    assert not_adult({"age": 16, "active": True})
    assert not not_adult({"age": 21, "active": True})


def test_rule_def_signature(register: Registry[UserCtx]):
    @rule_def(register)
    def has_minimum_age(ctx: UserCtx, threshold: int, *, strict: bool = False) -> bool:
        return ctx["age"] >= threshold if strict else ctx["age"] > threshold - 1

    sig = inspect.signature(has_minimum_age)
    assert list(sig.parameters) == ["threshold", "strict"]
    assert sig.parameters["threshold"].annotation == "int"
    assert sig.parameters["strict"].annotation == "bool"
    assert sig.parameters["strict"].default is False
    assert sig.return_annotation is Predicate

    type_hints = get_type_hints(has_minimum_age)
    assert type_hints["threshold"] is int
    assert type_hints["strict"] is bool
    assert type_hints["return"] is Predicate

    predicate = has_minimum_age(18, strict=True)
    assert isinstance(predicate, Predicate)
    assert predicate({"age": 20, "active": True})
    assert not predicate({"age": 16, "active": True})
