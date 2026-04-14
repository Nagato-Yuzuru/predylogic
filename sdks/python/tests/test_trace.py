"""
Test suite for Trace — PredyLogic's core observability mechanism.

Covers:
- Trace tree structure correctness (flat N-ary, not nested binary)
- Short-circuit behavior and children collection
- fail_skip interaction with Trace
- Nested compositions (and/or/not combinations)
- DefaultTraceStyle rendering
"""

from __future__ import annotations

from typing import TypedDict

import pytest
from predylogic import Trace, all_of, any_of, predicate
from predylogic.trace.trace import DefaultTraceStyle

# ============================================================================
# Helpers
# ============================================================================


class Ctx(TypedDict):
    value: int


def leaf(name: str, *, result: bool):
    """Create a named leaf predicate with a fixed result."""
    return predicate(lambda _: result, name=name, desc=name)


def leaf_raiser(name: str, exc: Exception):
    """Create a named leaf that raises on evaluation."""

    def _fn(_: Ctx) -> bool:
        raise exc

    return predicate(_fn, name=name, desc=name)


CTX: Ctx = {"value": 1}


def collect_operators(t: Trace) -> list[str]:
    """Flatten all operators in a trace tree (pre-order)."""
    ops = [t.operator]
    for c in t.children:
        ops.extend(collect_operators(c))
    return ops  # ty:ignore[invalid-return-type]


def collect_leaf_names(t: Trace) -> list[str]:
    """Collect names of all leaf nodes in pre-order."""
    names = []
    if t.operator == "leaf" and t.node and t.node.name:
        names.append(t.node.name)
    for c in t.children:
        names.extend(collect_leaf_names(c))
    return names


# ============================================================================
# 1. Trace Tree Structure
# ============================================================================


class TestTraceTreeStructure:
    """Verify Trace tree mirrors the logical structure — flat N-ary, not nested binary."""

    def test_single_leaf(self):
        """Single leaf produces a leaf Trace."""
        p = leaf("A", result=True)
        t = p(CTX, trace=True)

        assert isinstance(t, Trace)
        assert t.operator == "leaf"
        assert t.success is True
        assert t.children == ()
        assert t.node is not None
        assert t.node.name == "A"

    def test_two_children_and(self):
        """AND with 2 children — baseline, should be flat."""
        p = all_of([leaf("A", result=True), leaf("B", result=False)])
        t = p(CTX, trace=True, short_circuit=False)

        assert t.operator == "and"
        assert t.success is False
        assert len(t.children) == 2
        assert t.children[0].operator == "leaf"
        assert t.children[1].operator == "leaf"

    def test_two_children_or(self):
        """OR with 2 children — baseline, should be flat."""
        p = any_of([leaf("A", result=False), leaf("B", result=True)])
        t = p(CTX, trace=True, short_circuit=False)

        assert t.operator == "or"
        assert t.success is True
        assert len(t.children) == 2
        assert t.children[0].operator == "leaf"
        assert t.children[1].operator == "leaf"

    def test_three_children_and_is_flat(self):
        """
        CRITICAL: all_of([A, B, C]) must produce a flat AND node with 3 children,
        not a left-leaning nested tree.

        Expected:
            and -> [A, B, C]

        NOT:
            and -> [and -> [A, B], C]
        """
        p = all_of([
            leaf("A", result=True),
            leaf("B", result=False),
            leaf("C", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert t.operator == "and"
        assert t.success is False
        assert len(t.children) == 3, (
            f"Expected 3 flat children, got {len(t.children)}. Operators: {[c.operator for c in t.children]}"
        )
        assert all(c.operator == "leaf" for c in t.children)
        assert collect_leaf_names(t) == ["A", "B", "C"]

    def test_three_children_or_is_flat(self):
        """
        CRITICAL: any_of([A, B, C]) must produce a flat OR node with 3 children.
        """
        p = any_of([
            leaf("A", result=False),
            leaf("B", result=True),
            leaf("C", result=False),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert t.operator == "or"
        assert t.success is True
        assert len(t.children) == 3, (
            f"Expected 3 flat children, got {len(t.children)}. Operators: {[c.operator for c in t.children]}"
        )
        assert all(c.operator == "leaf" for c in t.children)
        assert collect_leaf_names(t) == ["A", "B", "C"]

    def test_four_children_and_is_flat(self):
        """4 children AND — no nesting at any level."""
        p = all_of([
            leaf("A", result=True),
            leaf("B", result=True),
            leaf("C", result=True),
            leaf("D", result=False),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert t.operator == "and"
        assert len(t.children) == 4
        assert all(c.operator == "leaf" for c in t.children)
        assert t.success is False

    def test_four_children_or_is_flat(self):
        """4 children OR — no nesting at any level."""
        p = any_of([
            leaf("A", result=False),
            leaf("B", result=False),
            leaf("C", result=True),
            leaf("D", result=False),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert t.operator == "or"
        assert len(t.children) == 4
        assert all(c.operator == "leaf" for c in t.children)
        assert t.success is True

    def test_chained_and_operator_is_flat(self):
        """
        A & B & C via operator chaining should also produce flat trace.
        """
        a = leaf("A", result=True)
        b = leaf("B", result=True)
        c = leaf("C", result=False)

        p = a & b & c
        t = p(CTX, trace=True, short_circuit=False)

        assert t.operator == "and"
        assert len(t.children) == 3
        assert all(c.operator == "leaf" for c in t.children)

    def test_chained_or_operator_is_flat(self):
        """
        A | B | C via operator chaining should also produce flat trace.
        """
        a = leaf("A", result=False)
        b = leaf("B", result=False)
        c = leaf("C", result=True)

        p = a | b | c
        t = p(CTX, trace=True, short_circuit=False)

        assert t.operator == "or"
        assert len(t.children) == 3
        assert all(c.operator == "leaf" for c in t.children)


# ============================================================================
# 2. Nested Compositions
# ============================================================================


class TestTraceNestedComposition:
    """Verify Trace structure for nested logical compositions."""

    def test_and_containing_or(self):
        """AND(A, OR(B, C)) — two levels, each correct."""
        p = all_of([
            leaf("A", result=True),
            any_of([leaf("B", result=False), leaf("C", result=True)]),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert t.operator == "and"
        assert t.success is True
        assert len(t.children) == 2

        assert t.children[0].operator == "leaf"
        assert t.children[1].operator == "or"
        assert len(t.children[1].children) == 2

    def test_or_containing_and(self):
        """OR(AND(A, B), C) — two levels."""
        p = any_of([
            all_of([leaf("A", result=False), leaf("B", result=True)]),
            leaf("C", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert t.operator == "or"
        assert t.success is True
        assert len(t.children) == 2

        assert t.children[0].operator == "and"
        assert t.children[0].success is False
        assert t.children[1].operator == "leaf"

    def test_not_wrapping_and(self):
        """NOT(AND(A, B)) — not node with and child."""
        p = ~all_of([leaf("A", result=True), leaf("B", result=True)])
        t = p(CTX, trace=True, short_circuit=False)

        assert t.operator == "not"
        assert t.success is False
        assert len(t.children) == 1
        assert t.children[0].operator == "and"
        assert t.children[0].success is True

    def test_three_level_nesting(self):
        """AND(A, OR(B, AND(C, D))) — three levels deep."""
        p = all_of([
            leaf("A", result=True),
            any_of([
                leaf("B", result=False),
                all_of([leaf("C", result=True), leaf("D", result=True)]),
            ]),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert t.operator == "and"
        assert t.success is True
        assert len(t.children) == 2

        or_node = t.children[1]
        assert or_node.operator == "or"
        assert len(or_node.children) == 2

        and_inner = or_node.children[1]
        assert and_inner.operator == "and"
        assert len(and_inner.children) == 2
        assert all(c.operator == "leaf" for c in and_inner.children)

    def test_nary_and_containing_nary_or(self):
        """
        all_of([A, B, any_of([C, D, E])]) — N-ary at both levels.
        Both AND and OR nodes should be flat.
        """
        p = all_of([
            leaf("A", result=True),
            leaf("B", result=True),
            any_of([
                leaf("C", result=False),
                leaf("D", result=False),
                leaf("E", result=True),
            ]),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert t.operator == "and"
        assert t.success is True
        assert len(t.children) == 3

        or_node = t.children[2]
        assert or_node.operator == "or"
        assert len(or_node.children) == 3
        assert all(c.operator == "leaf" for c in or_node.children)


# ============================================================================
# 3. Short-Circuit Behavior
# ============================================================================


class TestTraceShortCircuit:
    """Verify short-circuit trace captures evaluated nodes only."""

    def test_and_short_circuits_on_first_false(self):
        """AND(F, T, T) with short_circuit=True — only first child evaluated."""
        p = all_of([
            leaf("A", result=False),
            leaf("B", result=True),
            leaf("C", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=True)

        assert t.operator == "and"
        assert t.success is False
        evaluated = collect_leaf_names(t)
        assert "A" in evaluated
        assert "B" not in evaluated
        assert "C" not in evaluated

    def test_or_short_circuits_on_first_true(self):
        """OR(T, F, F) with short_circuit=True — only first child evaluated."""
        p = any_of([
            leaf("A", result=True),
            leaf("B", result=False),
            leaf("C", result=False),
        ])
        t = p(CTX, trace=True, short_circuit=True)

        assert t.operator == "or"
        assert t.success is True
        evaluated = collect_leaf_names(t)
        assert "A" in evaluated
        assert "B" not in evaluated
        assert "C" not in evaluated

    def test_and_short_circuits_on_second(self):
        """AND(T, F, T) — evaluates A and B, stops at B."""
        p = all_of([
            leaf("A", result=True),
            leaf("B", result=False),
            leaf("C", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=True)

        assert t.success is False
        evaluated = collect_leaf_names(t)
        assert "A" in evaluated
        assert "B" in evaluated
        assert "C" not in evaluated

    def test_no_short_circuit_evaluates_all(self):
        """AND(F, T, T) with short_circuit=False — all children evaluated."""
        p = all_of([
            leaf("A", result=False),
            leaf("B", result=True),
            leaf("C", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert t.success is False
        evaluated = collect_leaf_names(t)
        assert evaluated == ["A", "B", "C"]


# ============================================================================
# 4. fail_skip Interaction
# ============================================================================


class TestTraceFailSkip:
    """Verify fail_skip produces SKIP trace nodes with correct metadata."""

    def test_skip_node_in_and_context(self):
        """Skipped node in AND context gets fallback=True (AND identity)."""
        p = all_of([
            leaf_raiser("A", ValueError("boom")),
            leaf("B", result=False),
        ])
        t = p(CTX, trace=True, short_circuit=False, fail_skip=(ValueError,))

        assert t.operator == "and"
        assert t.success is False

        skip_child = t.children[0]
        assert skip_child.operator == "SKIP"
        assert skip_child.success is True  # AND identity
        assert skip_child.error is not None
        assert isinstance(skip_child.error, ValueError)
        assert skip_child.node is not None
        assert skip_child.node.name == "A"

    def test_skip_node_in_or_context(self):
        """Skipped node in OR context gets fallback=False (OR identity)."""
        p = any_of([
            leaf_raiser("A", ValueError("boom")),
            leaf("B", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=False, fail_skip=(ValueError,))

        assert t.operator == "or"
        assert t.success is True

        skip_child = t.children[0]
        assert skip_child.operator == "SKIP"
        assert skip_child.success is False  # OR identity
        assert isinstance(skip_child.error, ValueError)

    def test_skip_in_nary_and(self):
        """fail_skip with 3 children AND — all evaluated, skip is flat."""
        p = all_of([
            leaf("A", result=True),
            leaf_raiser("B", ValueError("boom")),
            leaf("C", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=False, fail_skip=(ValueError,))

        assert t.operator == "and"
        assert t.success is True  # A=True, B=True(skip identity), C=True
        assert len(t.children) == 3

        assert t.children[0].operator == "leaf"
        assert t.children[1].operator == "SKIP"
        assert t.children[1].success is True
        assert t.children[2].operator == "leaf"

    def test_unlisted_exception_propagates(self):
        """Exceptions not in fail_skip tuple propagate normally."""
        p = leaf_raiser("A", KeyError("nope"))

        with pytest.raises(KeyError):
            p(CTX, trace=True, fail_skip=(ValueError,))


# ============================================================================
# 5. Trace Leaf Identity
# ============================================================================


class TestTraceLeafIdentity:
    """Verify leaf Trace nodes carry correct metadata."""

    def test_leaf_has_name(self):
        """Leaf trace node carries the predicate name."""
        p = leaf("my_rule", result=True)
        t = p(CTX, trace=True)

        assert t.node is not None
        assert t.node.name == "my_rule"

    def test_leaf_has_desc(self):
        """Leaf trace node carries the predicate description."""
        p = leaf("my_rule", result=True)
        t = p(CTX, trace=True)

        assert t.node is not None
        assert t.node.desc == "my_rule"

    def test_leaf_success_matches_result(self):
        """Leaf trace success matches the predicate return value."""
        p_true = leaf("yes", result=True)
        p_false = leaf("no", result=False)

        assert p_true(CTX, trace=True).success is True
        assert p_false(CTX, trace=True).success is False


# ============================================================================
# 6. DefaultTraceStyle Rendering
# ============================================================================


class TestDefaultTraceStyleRendering:
    """Verify trace rendering produces readable, correct output."""

    def test_leaf_renders_with_name(self):
        """Leaf with name/desc should render the name, not 'LEAF'."""
        p = leaf("is_active", result=True)
        t = p(CTX, trace=True)

        rendered = DefaultTraceStyle().render(t)
        assert "is_active" in rendered
        assert "LEAF" not in rendered

    def test_leaf_without_desc_falls_back_to_name(self):
        """Leaf with name but no desc should render the name."""
        p = predicate(lambda _: True, name="my_rule")
        t = p(CTX, trace=True)

        rendered = DefaultTraceStyle().render(t)
        assert "my_rule" in rendered

    def test_and_node_renders_operator(self):
        """AND node without desc renders 'AND'."""
        p = all_of([leaf("A", result=True), leaf("B", result=True)])
        t = p(CTX, trace=True, short_circuit=False)

        rendered = DefaultTraceStyle().render(t)
        assert "AND" in rendered

    def test_failed_leaf_shows_context(self):
        """Failed leaf with value set shows context in render."""
        t = Trace(
            success=False,
            operator="leaf",
            value={"key": "val"},
        )
        rendered = DefaultTraceStyle().render(t)
        assert "Context" in rendered

    def test_skip_node_shows_error(self):
        """SKIP node renders error information."""
        err = ValueError("test error")
        t = Trace(
            success=True,
            operator="SKIP",
            error=err,
        )
        rendered = DefaultTraceStyle().render(t)
        assert "Error" in rendered
        assert "test error" in rendered


# ============================================================================
# 7. Trace __bool__ and Operator Overloads
# ============================================================================


class TestTraceOperators:
    """Verify Trace logical operator overloads."""

    def test_bool_reflects_success(self):
        """bool(trace) returns trace.success."""
        assert bool(Trace(success=True, operator="leaf")) is True
        assert bool(Trace(success=False, operator="leaf")) is False

    def test_and_operator(self):
        """Trace & Trace produces and-trace."""
        a = Trace(success=True, operator="leaf")
        b = Trace(success=False, operator="leaf")
        result = a & b

        assert result.operator == "and"
        assert result.success is False
        assert len(result.children) == 2

    def test_or_operator(self):
        """Trace | Trace produces or-trace."""
        a = Trace(success=False, operator="leaf")
        b = Trace(success=True, operator="leaf")
        result = a | b

        assert result.operator == "or"
        assert result.success is True
        assert len(result.children) == 2

    def test_invert_operator(self):
        """~Trace produces not-trace."""
        a = Trace(success=True, operator="leaf")
        result = ~a

        assert result.operator == "not"
        assert result.success is False
        assert len(result.children) == 1

    def test_and_with_bool(self):
        """Trace & bool works."""
        a = Trace(success=True, operator="leaf")
        result = a & False

        assert result.operator == "and"
        assert result.success is False

    def test_or_with_bool(self):
        """Trace | bool works."""
        a = Trace(success=False, operator="leaf")
        result = a | True

        assert result.operator == "or"
        assert result.success is True
