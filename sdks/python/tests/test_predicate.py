from __future__ import annotations

from typing import TypedDict

import pytest

from predylogic import Trace, predicate


class UserCtx(TypedDict):
    age: int
    active: bool


@pytest.fixture
def calls() -> dict[str, int]:
    return {}


def _count(calls: dict[str, int], key: str) -> None:
    calls[key] = calls.get(key, 0) + 1


def make_leaf_bool(calls: dict[str, int], key: str, *, value: bool):
    """Leaf that returns a plain bool."""

    def _fn(_: UserCtx) -> bool:
        _count(calls, key)
        return value

    return predicate(_fn, name=key, desc=key)


def make_leaf_raiser(calls: dict[str, int], key: str, exc: Exception):
    """Leaf that raises; used with fail_skip tests."""

    def _fn(_: UserCtx) -> bool:
        _count(calls, key)
        raise exc

    return predicate(_fn, name=key, desc=key)


def _flatten_ops(t: Trace) -> list[str]:
    ops = [t.operator]
    for c in t.children:
        ops.extend(_flatten_ops(c))
    return ops


def test_predicate_combinations():
    adult = predicate(lambda ctx: ctx["age"] >= 18, name="adult")
    active = predicate(lambda ctx: ctx["active"], name="active")

    adult_and_active = adult & active
    active_or_adult = active | adult
    not_adult = ~adult

    assert adult_and_active({"age": 25, "active": True})
    assert not adult_and_active({"age": 25, "active": False})

    assert active_or_adult({"age": 17, "active": True})
    assert not active_or_adult({"age": 16, "active": False})

    assert not_adult({"age": 16, "active": True})
    assert not not_adult({"age": 21, "active": True})


def test_call_trace_flag_changes_return_type(calls: dict[str, int]):
    ctx: UserCtx = {"age": 20, "active": True}

    p_bool = make_leaf_bool(calls, "p_bool", value=True)
    res_bool = p_bool(ctx, trace=False)
    assert isinstance(res_bool, bool)
    assert res_bool is True

    p_leaf = make_leaf_bool(calls, "p_leaf", value=True)
    res_trace = p_leaf(ctx, trace=True)
    assert isinstance(res_trace, Trace)
    assert repr(res_trace)
    assert res_trace.operator == "leaf"
    assert res_trace.success is True


def test_fail_skip_in_and_context_uses_identity_true(calls: dict[str, int]):
    ctx: UserCtx = {"age": 20, "active": True}

    left = make_leaf_raiser(calls, "left", ValueError("boom"))
    right = make_leaf_bool(calls, "right", value=False)
    p = left & right

    assert p(ctx, trace=False, fail_skip=(ValueError,)) is False

    calls.clear()

    res = p(ctx, trace=True, fail_skip=(ValueError,), short_circuit=False)
    assert isinstance(res, Trace)
    assert repr(res)
    assert res.operator == "and"
    assert res.success is False
    assert len(res.children) == 2

    left_t, right_t = res.children

    # Left-to-right order: left evaluated first.
    assert left_t.operator == "SKIP"
    assert left_t.success is True  # AND identity
    assert isinstance(left_t.error, ValueError)

    assert right_t.operator == "leaf"
    assert right_t.success is False


def test_fail_skip_in_or_context_uses_identity_false(calls: dict[str, int]):
    ctx: UserCtx = {"age": 20, "active": True}

    left = make_leaf_raiser(calls, "left", ValueError("boom"))
    right = make_leaf_bool(calls, "right", value=True)
    p = left | right

    assert p(ctx, trace=False, fail_skip=(ValueError,)) is True

    calls.clear()

    res = p(ctx, trace=True, fail_skip=(ValueError,), short_circuit=False)
    assert isinstance(res, Trace)
    assert repr(res)
    assert res.operator == "or"
    assert res.success is True
    assert len(res.children) == 2

    left_t, right_t = res.children

    assert left_t.operator == "SKIP"
    assert left_t.success is False  # OR identity
    assert isinstance(left_t.error, ValueError)

    assert right_t.operator == "leaf"
    assert right_t.success is True


def test_trace_short_circuit_controls_collection_for_and(calls: dict[str, int]):
    ctx: UserCtx = {"age": 20, "active": True}

    first = make_leaf_bool(calls, "first", value=False)
    second = make_leaf_bool(calls, "second", value=True)
    p = first & second

    res_sc = p(ctx, trace=True, short_circuit=True)
    assert isinstance(res_sc, Trace)
    assert res_sc.operator == "and"
    assert res_sc.success is False
    assert calls.get("first", 0) == 1
    assert calls.get("second", 0) == 0
    assert len(res_sc.children) == 1

    calls.clear()

    res_full = p(ctx, trace=True, short_circuit=False)
    assert isinstance(res_full, Trace)
    assert repr(res_full)
    assert res_full.operator == "and"
    assert res_full.success is False
    assert calls.get("first", 0) == 1
    assert calls.get("second", 0) == 1
    assert len(res_full.children) == 2


def test_trace_short_circuit_controls_collection_for_or(calls: dict[str, int]):
    ctx: UserCtx = {"age": 20, "active": True}

    first = make_leaf_bool(calls, "first", value=True)
    second = make_leaf_bool(calls, "second", value=False)
    p = first | second

    res_sc = p(ctx, trace=True, short_circuit=True)
    assert isinstance(res_sc, Trace)
    assert repr(res_sc)
    assert res_sc.operator == "or"
    assert res_sc.success is True
    assert calls.get("first", 0) == 1
    assert calls.get("second", 0) == 0
    assert len(res_sc.children) == 1

    calls.clear()

    res_full = p(ctx, trace=True, short_circuit=False)
    assert isinstance(res_full, Trace)
    assert repr(res_full)
    assert res_full.operator == "or"
    assert res_full.success is True
    assert calls.get("first", 0) == 1
    assert calls.get("second", 0) == 1
    assert len(res_full.children) == 2


def test_fail_skip_does_not_catch_unlisted_exceptions(calls: dict[str, int]):
    ctx: UserCtx = {"age": 20, "active": True}
    p = make_leaf_raiser(calls, "boom", KeyError("nope"))

    with pytest.raises(KeyError):
        p(ctx, trace=False, fail_skip=(ValueError,))

    with pytest.raises(KeyError):
        p(ctx, trace=True, fail_skip=(ValueError,))
