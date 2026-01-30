from __future__ import annotations

from dataclasses import dataclass

import pytest

from predylogic import is_predicate
from predylogic.register.errs import RegistryNameConflictError, RuleDefConflictError, RuleDefNotNamedError
from predylogic.register.registry import Registry, RegistryManager


@dataclass
class User:
    age: int
    active: bool


@pytest.fixture
def registry():
    return Registry[User]("test_registry")


def test_registry_creation():
    registry = Registry[User]("test_registry")
    assert registry.name == "test_registry"
    assert len(registry) == 0


def test_register_named_function(registry: Registry[User]):
    def is_adult(user: User) -> bool:
        return user.age >= 18

    predicate_producer = registry.register(is_adult, None)
    assert "is_adult" in registry
    assert registry["is_adult"] is predicate_producer

    predicate = predicate_producer()
    assert is_predicate(predicate)
    assert predicate(User(age=20, active=True))
    assert not predicate(User(age=16, active=True))


def test_register_with_alias(registry: Registry[User]):
    def is_adult(user: User) -> bool:
        return user.age >= 18

    predicate_producer = registry.register(is_adult, "is_of_legal_age")
    assert "is_of_legal_age" in registry
    assert "is_adult" not in registry
    assert registry["is_of_legal_age"] is predicate_producer


def test_register_lambda_with_alias(registry: Registry[User]):
    predicate_producer = registry.register(lambda user, age: user.age > age, "is_older_than")
    assert "is_older_than" in registry
    p = predicate_producer(25)
    assert p(User(age=30, active=True))
    assert not p(User(age=20, active=True))


def test_register_lambda_without_alias_raises_error(registry: Registry[User]):
    with pytest.raises(RuleDefNotNamedError):
        registry.register(lambda user: user.active, None)


def test_register_duplicate_name_raises_error(registry: Registry[User]):
    def is_active(user: User) -> bool:
        return user.active

    registry.register(is_active, None)
    with pytest.raises(RuleDefConflictError):
        registry.register(is_active, None)


def test_rule_def_decorator(registry: Registry[User]):
    @registry.rule_def()
    def is_active(user: User) -> bool:
        return user.active

    assert "is_active" in registry
    p = is_active()
    assert is_predicate(p)
    assert p(User(age=20, active=True))
    assert not p(User(age=20, active=False))


def test_rule_def_decorator_with_alias(registry: Registry[User]):
    @registry.rule_def("is_currently_active")
    def is_active(user: User) -> bool:
        return user.active

    assert "is_currently_active" in registry
    assert "is_active" not in registry


def test_registry_manager():
    manager = RegistryManager()
    registry1 = Registry[User]("registry1")
    registry2 = Registry[User]("registry2")

    manager.add_register("registry1", registry1)
    manager.add_register("registry2", registry2)

    assert manager.get_register("registry1") is registry1
    assert manager.get_register("registry2") is registry2
    assert manager.get_register("non_existent") is None


def test_registry_manager_add_duplicate_name_raises_error():
    manager = RegistryManager()
    registry1 = Registry[User]("registry1")
    manager.add_register("registry1", registry1)

    with pytest.raises(RegistryNameConflictError):
        manager.add_register("registry1", registry1)
