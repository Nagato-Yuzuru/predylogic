from __future__ import annotations

from typing import TypedDict

from predylogic import predicate


class UserCtx(TypedDict):
    age: int
    active: bool


def test_predicate_combinations():
    adult = predicate(lambda ctx: ctx["age"] >= 18)
    active = predicate(lambda ctx: ctx["active"])

    adult_and_active = adult & active
    active_or_adult = active | adult
    not_adult = ~adult

    assert adult_and_active({"age": 25, "active": True})
    assert not adult_and_active({"age": 25, "active": False})

    assert active_or_adult({"age": 17, "active": True})
    assert not active_or_adult({"age": 16, "active": False})

    assert not_adult({"age": 16, "active": True})
    assert not not_adult({"age": 21, "active": True})
