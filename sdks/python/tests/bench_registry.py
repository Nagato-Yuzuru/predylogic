"""Benchmarks for registry operations."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from predylogic.register.registry import Registry


@dataclass
class User:
    """User model for benchmarks."""

    age: int
    active: bool
    role: str


@pytest.fixture
def registry() -> Registry[User]:
    """Create a registry with predefined rules."""
    reg = Registry[User]("bench_registry")

    @reg.rule_def()
    def is_adult(user: User) -> bool:
        return user.age >= 18

    @reg.rule_def()
    def is_active(user: User) -> bool:
        return user.active

    @reg.rule_def()
    def is_admin(user: User) -> bool:
        return user.role == "admin"

    @reg.rule_def()
    def is_senior(user: User, threshold: int = 65) -> bool:
        return user.age >= threshold

    return reg


@pytest.fixture
def user() -> User:
    """Create a sample user."""
    return User(age=30, active=True, role="admin")


@pytest.mark.benchmark
def test_rule_evaluation(registry: Registry[User], user: User) -> None:
    """Benchmark simple rule evaluation."""
    is_adult = registry["is_adult"]
    predicate = is_adult()
    for _ in range(1000):
        predicate(user)


@pytest.mark.benchmark
def test_rule_with_params(registry: Registry[User], user: User) -> None:
    """Benchmark rule evaluation with parameters."""
    is_senior = registry["is_senior"]
    predicate = is_senior(threshold=60)
    for _ in range(1000):
        predicate(user)


@pytest.mark.benchmark
def test_composed_rules(registry: Registry[User], user: User) -> None:
    """Benchmark composed rule evaluation."""
    is_adult = registry["is_adult"]
    is_active = registry["is_active"]
    is_admin = registry["is_admin"]

    # adult AND active AND admin
    predicate = is_adult() & is_active() & is_admin()
    for _ in range(1000):
        predicate(user)


@pytest.mark.benchmark
def test_registry_lookup(registry: Registry[User]) -> None:
    """Benchmark registry rule lookup."""
    for _ in range(1000):
        _ = registry["is_adult"]
        _ = registry["is_active"]
        _ = registry["is_admin"]


@pytest.mark.benchmark
def test_registry_registration() -> None:
    """Benchmark rule registration performance."""
    for _ in range(100):
        reg = Registry[User]("temp_registry")

        @reg.rule_def()
        def is_adult(user: User) -> bool:
            return user.age >= 18

        @reg.rule_def()
        def is_active(user: User) -> bool:
            return user.active

        @reg.rule_def()
        def is_admin(user: User) -> bool:
            return user.role == "admin"
