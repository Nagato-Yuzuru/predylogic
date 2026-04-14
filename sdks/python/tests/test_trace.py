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

# Shape: (operator, success, name, children_shapes)
Shape = tuple[str, bool, str | None, tuple["Shape", ...]]


def trace_shape(t: Trace) -> Shape:
    """Extract the full structural snapshot of a Trace tree.

    Returns (operator, success, name, (child_shapes...)).
    A single assert on this tuple locks down structure, order, identity, and success.
    """
    name = t.node.name if t.node else None
    children = tuple(trace_shape(c) for c in t.children)
    return t.operator, t.success, name, children


# ============================================================================
# 1. Trace Tree Structure
# ============================================================================


class TestTraceTreeStructure:
    """Verify Trace tree mirrors the logical structure — flat N-ary, not nested binary."""

    def test_single_leaf(self):
        """Single leaf produces a leaf Trace."""
        p = leaf("A", result=True)
        t = p(CTX, trace=True)

        assert trace_shape(t) == ("leaf", True, "A", ())

    def test_two_children_and(self):
        """AND with 2 children — baseline, should be flat."""
        p = all_of([leaf("A", result=True), leaf("B", result=False)])
        t = p(CTX, trace=True, short_circuit=False)

        assert trace_shape(t) == (
            "and",
            False,
            None,
            (
                ("leaf", True, "A", ()),
                ("leaf", False, "B", ()),
            ),
        )

    def test_two_children_or(self):
        """OR with 2 children — baseline, should be flat."""
        p = any_of([leaf("A", result=False), leaf("B", result=True)])
        t = p(CTX, trace=True, short_circuit=False)

        assert trace_shape(t) == (
            "or",
            True,
            None,
            (
                ("leaf", False, "A", ()),
                ("leaf", True, "B", ()),
            ),
        )

    def test_three_children_and_is_flat(self):
        """
        CRITICAL: all_of([A, B, C]) must produce a flat AND node with 3 children,
        not a left-leaning nested tree.

        Expected:  and -> [A, B, C]
        NOT:       and -> [and -> [A, B], C]
        """
        p = all_of([
            leaf("A", result=True),
            leaf("B", result=False),
            leaf("C", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert trace_shape(t) == (
            "and",
            False,
            None,
            (
                ("leaf", True, "A", ()),
                ("leaf", False, "B", ()),
                ("leaf", True, "C", ()),
            ),
        )

    def test_three_children_or_is_flat(self):
        """CRITICAL: any_of([A, B, C]) must produce a flat OR node with 3 children."""
        p = any_of([
            leaf("A", result=False),
            leaf("B", result=True),
            leaf("C", result=False),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert trace_shape(t) == (
            "or",
            True,
            None,
            (
                ("leaf", False, "A", ()),
                ("leaf", True, "B", ()),
                ("leaf", False, "C", ()),
            ),
        )

    def test_four_children_and_is_flat(self):
        """4 children AND — no nesting at any level."""
        p = all_of([
            leaf("A", result=True),
            leaf("B", result=True),
            leaf("C", result=True),
            leaf("D", result=False),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert trace_shape(t) == (
            "and",
            False,
            None,
            (
                ("leaf", True, "A", ()),
                ("leaf", True, "B", ()),
                ("leaf", True, "C", ()),
                ("leaf", False, "D", ()),
            ),
        )

    def test_four_children_or_is_flat(self):
        """4 children OR — no nesting at any level."""
        p = any_of([
            leaf("A", result=False),
            leaf("B", result=False),
            leaf("C", result=True),
            leaf("D", result=False),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert trace_shape(t) == (
            "or",
            True,
            None,
            (
                ("leaf", False, "A", ()),
                ("leaf", False, "B", ()),
                ("leaf", True, "C", ()),
                ("leaf", False, "D", ()),
            ),
        )

    def test_chained_and_operator_is_flat(self):
        """A & B & C via operator chaining should also produce flat trace."""
        p = leaf("A", result=True) & leaf("B", result=True) & leaf("C", result=False)
        t = p(CTX, trace=True, short_circuit=False)

        assert trace_shape(t) == (
            "and",
            False,
            None,
            (
                ("leaf", True, "A", ()),
                ("leaf", True, "B", ()),
                ("leaf", False, "C", ()),
            ),
        )

    def test_chained_or_operator_is_flat(self):
        """A | B | C via operator chaining should also produce flat trace."""
        p = leaf("A", result=False) | leaf("B", result=False) | leaf("C", result=True)
        t = p(CTX, trace=True, short_circuit=False)

        assert trace_shape(t) == (
            "or",
            True,
            None,
            (
                ("leaf", False, "A", ()),
                ("leaf", False, "B", ()),
                ("leaf", True, "C", ()),
            ),
        )

    def test_five_children_all_same_result(self):
        """5 children AND, all True — verify no degenerate nesting."""
        p = all_of([leaf(c, result=True) for c in "ABCDE"])
        t = p(CTX, trace=True, short_circuit=False)

        assert trace_shape(t) == ("and", True, None, tuple(("leaf", True, c, ()) for c in "ABCDE"))


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

        assert trace_shape(t) == (
            "and",
            True,
            None,
            (
                ("leaf", True, "A", ()),
                (
                    "or",
                    True,
                    None,
                    (
                        ("leaf", False, "B", ()),
                        ("leaf", True, "C", ()),
                    ),
                ),
            ),
        )

    def test_or_containing_and(self):
        """OR(AND(A, B), C) — two levels."""
        p = any_of([
            all_of([leaf("A", result=False), leaf("B", result=True)]),
            leaf("C", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert trace_shape(t) == (
            "or",
            True,
            None,
            (
                (
                    "and",
                    False,
                    None,
                    (
                        ("leaf", False, "A", ()),
                        ("leaf", True, "B", ()),
                    ),
                ),
                ("leaf", True, "C", ()),
            ),
        )

    def test_not_wrapping_and(self):
        """NOT(AND(A, B)) — not node with and child."""
        p = ~all_of([leaf("A", result=True), leaf("B", result=True)])
        t = p(CTX, trace=True, short_circuit=False)

        assert trace_shape(t) == (
            "not",
            False,
            None,
            (
                (
                    "and",
                    True,
                    None,
                    (
                        ("leaf", True, "A", ()),
                        ("leaf", True, "B", ()),
                    ),
                ),
            ),
        )

    def test_not_wrapping_leaf(self):
        """NOT(A) — simple negation."""
        p = ~leaf("A", result=True)
        t = p(CTX, trace=True)

        assert trace_shape(t) == ("not", False, None, (("leaf", True, "A", ()),))

    def test_double_not(self):
        """NOT(NOT(A)) — double negation."""
        p = ~~leaf("A", result=True)
        t = p(CTX, trace=True)

        assert trace_shape(t) == ("not", True, None, (("not", False, None, (("leaf", True, "A", ()),)),))

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

        assert trace_shape(t) == (
            "and",
            True,
            None,
            (
                ("leaf", True, "A", ()),
                (
                    "or",
                    True,
                    None,
                    (
                        ("leaf", False, "B", ()),
                        (
                            "and",
                            True,
                            None,
                            (
                                ("leaf", True, "C", ()),
                                ("leaf", True, "D", ()),
                            ),
                        ),
                    ),
                ),
            ),
        )

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

        assert trace_shape(t) == (
            "and",
            True,
            None,
            (
                ("leaf", True, "A", ()),
                ("leaf", True, "B", ()),
                (
                    "or",
                    True,
                    None,
                    (
                        ("leaf", False, "C", ()),
                        ("leaf", False, "D", ()),
                        ("leaf", True, "E", ()),
                    ),
                ),
            ),
        )

    def test_mixed_operators_complex(self):
        """OR(AND(A, B, C), NOT(D), E) — mixed N-ary with not."""
        p = any_of([
            all_of([
                leaf("A", result=True),
                leaf("B", result=True),
                leaf("C", result=False),
            ]),
            ~leaf("D", result=True),
            leaf("E", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert trace_shape(t) == (
            "or",
            True,
            None,
            (
                (
                    "and",
                    False,
                    None,
                    (
                        ("leaf", True, "A", ()),
                        ("leaf", True, "B", ()),
                        ("leaf", False, "C", ()),
                    ),
                ),
                ("not", False, None, (("leaf", True, "D", ()),)),
                ("leaf", True, "E", ()),
            ),
        )


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
        # Only A should be evaluated — B and C skipped
        leaf_names = set(self._collect_leaf_names(t))
        assert "A" in leaf_names
        assert "B" not in leaf_names
        assert "C" not in leaf_names

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
        leaf_names = set(self._collect_leaf_names(t))
        assert "A" in leaf_names
        assert "B" not in leaf_names
        assert "C" not in leaf_names

    def test_and_short_circuits_on_second(self):
        """AND(T, F, T) — evaluates A and B, stops at B."""
        p = all_of([
            leaf("A", result=True),
            leaf("B", result=False),
            leaf("C", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=True)

        assert t.success is False
        leaf_names = set(self._collect_leaf_names(t))
        assert "A" in leaf_names
        assert "B" in leaf_names
        assert "C" not in leaf_names

    def test_or_short_circuits_on_second(self):
        """OR(F, T, F) — evaluates A and B, stops at B."""
        p = any_of([
            leaf("A", result=False),
            leaf("B", result=True),
            leaf("C", result=False),
        ])
        t = p(CTX, trace=True, short_circuit=True)

        assert t.success is True
        leaf_names = set(self._collect_leaf_names(t))
        assert "A" in leaf_names
        assert "B" in leaf_names
        assert "C" not in leaf_names

    def test_no_short_circuit_evaluates_all_and(self):
        """AND(F, T, T) with short_circuit=False — all children evaluated in order."""
        p = all_of([
            leaf("A", result=False),
            leaf("B", result=True),
            leaf("C", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert t.success is False
        assert self._collect_leaf_names(t) == ["A", "B", "C"]

    def test_no_short_circuit_evaluates_all_or(self):
        """OR(T, F, F) with short_circuit=False — all children evaluated in order."""
        p = any_of([
            leaf("A", result=True),
            leaf("B", result=False),
            leaf("C", result=False),
        ])
        t = p(CTX, trace=True, short_circuit=False)

        assert t.success is True
        assert self._collect_leaf_names(t) == ["A", "B", "C"]

    def test_short_circuit_nested_and_in_or(self):
        """OR(AND(T, F), T) with short_circuit — inner AND fails, outer OR tries next."""
        p = any_of([
            all_of([leaf("A", result=True), leaf("B", result=False)]),
            leaf("C", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=True)

        assert t.success is True
        # AND(A, B) should evaluate both (A=T then B=F), then OR tries C
        leaf_names = set(self._collect_leaf_names(t))
        assert "A" in leaf_names
        assert "B" in leaf_names
        assert "C" in leaf_names

    @staticmethod
    def _collect_leaf_names(t: Trace) -> list[str]:
        """Recursively collect names of all leaf trace nodes (pre-order)."""
        names: list[str] = []
        if t.operator == "leaf" and t.node and t.node.name:
            names.append(t.node.name)
        for c in t.children:
            names.extend(TestTraceShortCircuit._collect_leaf_names(c))
        return names


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
        """fail_skip with 3 children AND — all evaluated, structure is flat."""
        p = all_of([
            leaf("A", result=True),
            leaf_raiser("B", ValueError("boom")),
            leaf("C", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=False, fail_skip=(ValueError,))

        assert trace_shape(t) == (
            "and",
            True,
            None,
            (
                ("leaf", True, "A", ()),
                ("SKIP", True, "B", ()),  # AND identity fallback
                ("leaf", True, "C", ()),
            ),
        )

    def test_skip_in_nary_or(self):
        """fail_skip with 3 children OR — all evaluated, structure is flat."""
        p = any_of([
            leaf("A", result=False),
            leaf_raiser("B", ValueError("boom")),
            leaf("C", result=True),
        ])
        t = p(CTX, trace=True, short_circuit=False, fail_skip=(ValueError,))

        assert trace_shape(t) == (
            "or",
            True,
            None,
            (
                ("leaf", False, "A", ()),
                ("SKIP", False, "B", ()),  # OR identity fallback
                ("leaf", True, "C", ()),
            ),
        )

    def test_skip_preserves_error_and_context(self):
        """SKIP node carries the original exception and context value."""
        err = ValueError("test_error")
        p = leaf_raiser("A", err)
        t = p(CTX, trace=True, fail_skip=(ValueError,))

        assert t.operator == "SKIP"
        assert t.error is not None
        assert str(t.error) == "test_error"
        assert t.value == CTX

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

    def test_leaf_has_name_and_desc(self):
        """Leaf trace node carries name and description."""
        p = leaf("my_rule", result=True)
        t = p(CTX, trace=True)

        assert t.node is not None
        assert t.node.name == "my_rule"
        assert t.node.desc == "my_rule"

    def test_leaf_with_separate_name_and_desc(self):
        """Leaf with different name and desc carries both."""
        p = predicate(lambda _: True, name="rule_id", desc="Human-readable description")
        t = p(CTX, trace=True)

        assert t.node is not None
        assert t.node.name == "rule_id"
        assert t.node.desc == "Human-readable description"

    def test_leaf_success_true(self):
        p = leaf("yes", result=True)
        assert p(CTX, trace=True).success is True

    def test_leaf_success_false(self):
        p = leaf("no", result=False)
        assert p(CTX, trace=True).success is False


# ============================================================================
# 6. DefaultTraceStyle Rendering
# ============================================================================


class TestDefaultTraceStyleRendering:
    """Verify trace rendering produces readable, correct output."""

    def test_leaf_renders_with_desc(self):
        """Leaf with desc should render the desc, not 'LEAF'."""
        p = leaf("is_active", result=True)
        t = p(CTX, trace=True)

        rendered = DefaultTraceStyle().render(t)
        assert "is_active" in rendered
        assert "LEAF" not in rendered

    def test_leaf_without_desc_falls_back_to_name(self):
        """Leaf with name but no desc should render the name, not 'LEAF'."""
        p = predicate(lambda _: True, name="my_rule")
        t = p(CTX, trace=True)

        rendered = DefaultTraceStyle().render(t)
        assert "my_rule" in rendered

    def test_success_icon(self):
        """Successful trace uses check icon."""
        t = Trace(success=True, operator="leaf")
        rendered = DefaultTraceStyle().render(t)
        assert "\u2705" in rendered  # ✅

    def test_failure_icon(self):
        """Failed trace uses cross icon."""
        t = Trace(success=False, operator="leaf")
        rendered = DefaultTraceStyle().render(t)
        assert "\u274c" in rendered  # ❌

    def test_skip_icon(self):
        """SKIP trace uses skip icon."""
        t = Trace(success=True, operator="SKIP")
        rendered = DefaultTraceStyle().render(t)
        assert "\u23ed" in rendered  # ⏭

    def test_and_node_renders_operator_label(self):
        """AND node without desc renders 'AND'."""
        p = all_of([leaf("A", result=True), leaf("B", result=True)])
        t = p(CTX, trace=True, short_circuit=False)

        rendered = DefaultTraceStyle().render(t)
        assert "AND" in rendered

    def test_failed_leaf_shows_context(self):
        """Failed leaf with value set shows context in render."""
        t = Trace(success=False, operator="leaf", value={"key": "val"})
        rendered = DefaultTraceStyle().render(t)
        assert "Context" in rendered
        assert "key" in rendered

    def test_skip_node_shows_error(self):
        """SKIP node renders error information."""
        t = Trace(success=True, operator="SKIP", error=ValueError("test error"))
        rendered = DefaultTraceStyle().render(t)
        assert "Error" in rendered
        assert "test error" in rendered

    def test_nested_rendering_indentation(self):
        """Nested trace produces indented output."""
        inner = Trace(success=True, operator="leaf")
        outer = Trace(success=True, operator="and", children=(inner,))
        rendered = DefaultTraceStyle().render(outer)
        lines = rendered.split("\n")
        # Outer at level 0, inner at level 1 (indented)
        assert len(lines) >= 2
        assert lines[1].startswith("  ")  # 2-space indent


# ============================================================================
# 7. Trace __bool__ and Operator Overloads
# ============================================================================


class TestTraceOperators:
    """Verify Trace logical operator overloads (public API)."""

    def test_bool_true(self):
        assert bool(Trace(success=True, operator="leaf")) is True

    def test_bool_false(self):
        assert bool(Trace(success=False, operator="leaf")) is False

    def test_and_both_true(self):
        a = Trace(success=True, operator="leaf")
        b = Trace(success=True, operator="leaf")
        result = a & b
        assert result.operator == "and"
        assert result.success is True
        assert len(result.children) == 2

    def test_and_one_false(self):
        a = Trace(success=True, operator="leaf")
        b = Trace(success=False, operator="leaf")
        result = a & b
        assert result.operator == "and"
        assert result.success is False
        assert len(result.children) == 2

    def test_or_both_false(self):
        a = Trace(success=False, operator="leaf")
        b = Trace(success=False, operator="leaf")
        result = a | b
        assert result.operator == "or"
        assert result.success is False
        assert len(result.children) == 2

    def test_or_one_true(self):
        a = Trace(success=False, operator="leaf")
        b = Trace(success=True, operator="leaf")
        result = a | b
        assert result.operator == "or"
        assert result.success is True
        assert len(result.children) == 2

    def test_invert(self):
        a = Trace(success=True, operator="leaf")
        result = ~a
        assert result.operator == "not"
        assert result.success is False
        assert len(result.children) == 1
        assert result.children[0] is a

    def test_invert_false(self):
        a = Trace(success=False, operator="leaf")
        result = ~a
        assert result.success is True

    def test_and_with_bool(self):
        a = Trace(success=True, operator="leaf")
        result = a & False
        assert result.success is False
        # The bool should be wrapped as PURE_BOOL
        assert result.children[1].operator == "PURE_BOOL"

    def test_or_with_bool(self):
        a = Trace(success=False, operator="leaf")
        result = a | True
        assert result.success is True
        assert result.children[1].operator == "PURE_BOOL"
