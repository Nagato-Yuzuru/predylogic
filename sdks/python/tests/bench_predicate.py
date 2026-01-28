"""Benchmarks for predicate operations."""

from __future__ import annotations

from typing import TypedDict

import pytest

from predylogic.predicate import Predicate


class UserCtx(TypedDict):
    """User context for benchmarks."""

    age: int
    active: bool
    role: str


@pytest.fixture
def user_ctx() -> UserCtx:
    """Create a sample user context."""
    return {"age": 25, "active": True, "role": "admin"}


@pytest.mark.benchmark
def test_simple_predicate(user_ctx: UserCtx) -> None:
    """Benchmark simple predicate evaluation."""
    predicate = Predicate(lambda ctx: ctx["age"] >= 18)
    for _ in range(1000):
        predicate(user_ctx)


@pytest.mark.benchmark
def test_predicate_and(user_ctx: UserCtx) -> None:
    """Benchmark AND predicate composition."""
    adult = Predicate(lambda ctx: ctx["age"] >= 18)
    active = Predicate(lambda ctx: ctx["active"])
    combined = adult & active
    for _ in range(1000):
        combined(user_ctx)


@pytest.mark.benchmark
def test_predicate_or(user_ctx: UserCtx) -> None:
    """Benchmark OR predicate composition."""
    adult = Predicate(lambda ctx: ctx["age"] >= 18)
    active = Predicate(lambda ctx: ctx["active"])
    combined = adult | active
    for _ in range(1000):
        combined(user_ctx)


@pytest.mark.benchmark
def test_predicate_not(user_ctx: UserCtx) -> None:
    """Benchmark NOT predicate composition."""
    adult = Predicate(lambda ctx: ctx["age"] >= 18)
    not_adult = ~adult
    for _ in range(1000):
        not_adult(user_ctx)


@pytest.mark.benchmark
def test_complex_predicate_composition(user_ctx: UserCtx) -> None:
    """Benchmark complex predicate composition."""
    adult = Predicate(lambda ctx: ctx["age"] >= 18)
    active = Predicate(lambda ctx: ctx["active"])
    is_admin = Predicate(lambda ctx: ctx["role"] == "admin")

    # ((adult AND active) OR is_admin) AND NOT (age > 100)
    not_too_old = ~Predicate(lambda ctx: ctx["age"] > 100)
    complex_predicate = ((adult & active) | is_admin) & not_too_old

    for _ in range(1000):
        complex_predicate(user_ctx)
