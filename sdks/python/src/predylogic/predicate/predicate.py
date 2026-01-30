# ruff: noqa: C901
from __future__ import annotations

import ast
from abc import ABC
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Literal,
    NamedTuple,
    TypeAlias,
    TypeGuard,
    TypeVar,
    assert_never,
    cast,
    final,
    overload,
)

from predylogic.trace.trace import Trace

if TYPE_CHECKING:
    from predylogic.types import LogicBinOp, PredicateNodeType

T_contra = TypeVar("T_contra", contravariant=True)

PredicateFn = Callable[[T_contra], bool]

COMPILED_PREDICATE = "_compiled_predicate"
RT_OR = "_rt_or"
RT_AND = "_rt_and"


@dataclass(frozen=True, kw_only=True)
class Predicate(Generic[T_contra], ABC):
    """
    Base class for predicate nodes in the predicate tree.
    """

    node_type: PredicateNodeType = field(init=False)
    desc: str | None = field(default=None)
    __compiler_cache: dict[tuple, Callable[[T_contra], Trace | bool]] = field(
        default_factory=dict,
        init=False,
        repr=False,
        hash=False,
        compare=False,
    )

    @overload
    def __call__(
        self,
        ctx: T_contra,
        /,
        *,
        trace: Literal[True] = True,
        short_circuit: bool = True,
        fail_skip: tuple[type[Exception], ...] | None = None,
    ) -> Trace: ...

    @overload
    def __call__(
        self,
        ctx: T_contra,
        /,
        *,
        trace: Literal[False] = False,
        short_circuit: bool = True,
        fail_skip: tuple[type[Exception], ...] | None = None,
    ) -> bool: ...

    def __call__(
        self,
        ctx: T_contra,
        /,
        *,
        trace: bool = False,
        short_circuit: bool = True,
        fail_skip: tuple[type[Exception], ...] | None = None,
    ) -> bool | Trace:
        """
        Execute the final predicate.
        """
        cache_key = (trace, short_circuit, fail_skip)
        runner = self.__compiler_cache.get(cache_key)
        if not runner:
            runner = Compiler(trace=trace, short_circuit=short_circuit, fail_skip=fail_skip).compile(self)
            self.__compiler_cache[cache_key] = runner
        return runner(ctx)

    def __and__(
        self,
        other: Predicate[T_contra],
    ) -> Predicate[T_contra]:
        """
        Combine this predicate with another using logical AND.
        """
        if not is_predicate(other):
            return NotImplemented
        return _PredicateAnd(children=(self, other))

    def __or__(self, other: Predicate[T_contra]) -> Predicate[T_contra]:
        if not is_predicate(other):
            return NotImplemented
        return _PredicateOr(children=(self, other))

    def __invert__(self) -> Predicate[T_contra]:
        return _PredicateNot(op=self)


def predicate(fn: PredicateFn[T_contra], *, desc: str | None = None) -> Predicate[T_contra]:
    """
    Create a Predicate from the function.
    """

    return _PredicateLeaf(fn=fn, desc=desc or fn.__doc__)


@dataclass(frozen=True, kw_only=True, slots=True)
@final
class _PredicateLeaf(Predicate[T_contra]):
    """
    Leaf node in the predicate tree.
    """

    node_type: Literal["leaf"] = field(default="leaf", init=False)
    fn: PredicateFn[T_contra]


@dataclass(frozen=True, kw_only=True, slots=True)
@final
class _PredicateAnd(Predicate[T_contra]):
    """
    Leaf node in the predicate tree.
    """

    node_type: Literal["and"] = field(default="and", init=False)
    children: tuple[Predicate[T_contra], ...]

    def __and__(self, other: Predicate[T_contra]) -> Predicate[T_contra]:
        if not is_predicate(other):
            return NotImplemented
        return _PredicateAnd(children=(self, other))


@dataclass(frozen=True, kw_only=True, slots=True)
@final
class _PredicateOr(Predicate[T_contra]):
    """
    Leaf node in the predicate tree.
    """

    node_type: Literal["or"] = field(default="or", init=False)
    children: tuple[Predicate[T_contra], ...]

    def __or__(self, other: Predicate[T_contra]) -> Predicate[T_contra]:
        if not is_predicate(other):
            return NotImplemented
        return _PredicateOr(children=(self, other))


@dataclass(frozen=True, kw_only=True, slots=True)
@final
class _PredicateNot(Predicate[T_contra]):
    """
    Leaf node in the predicate tree.
    """

    node_type: Literal["not"] = field(default="not", init=False)
    op: Predicate[T_contra]


PredicateNode: TypeAlias = (
    _PredicateLeaf[T_contra] | _PredicateAnd[T_contra] | _PredicateOr[T_contra] | _PredicateNot[T_contra]
)


def is_predicate(p: Any) -> TypeGuard[Predicate]:  # noqa: ANN401
    """
    Check if the given object is a valid predicate.
    """

    return isinstance(p, Predicate)


class Compiler:
    """
    Compiler for predicate functions.
    """

    def __init__(
        self,
        *,
        trace: bool,
        short_circuit: bool,
        fail_skip: tuple[type[Exception], ...] | None,
        root_fallback: bool = False,
    ):
        self.trace = trace
        self.short_circuit = short_circuit
        self.fail_skip = fail_skip or ()
        self.root_fallback = root_fallback

        self._leaf_counter = 0
        self._leaf_map: dict[tuple[int, bool], str] = {}
        self._context: dict[str, Any] = {}

    def _register_leaf(self, leaf: _PredicateLeaf, fallback: bool) -> str:  # noqa: FBT001
        # The same node may have different fallbacks.
        cache_key = (id(leaf), fallback)

        if cache_key not in self._leaf_map:
            name = f"_leaf_{self._leaf_counter}"
            self._leaf_counter += 1
            self._leaf_map[cache_key] = name

            if self.fail_skip:
                self._context[name] = self._wrap_with_fail_skip(leaf, fallback)
            else:
                self._context[name] = leaf.fn

        return self._leaf_map[cache_key]

    def _wrap_with_fail_skip(self, leaf: _PredicateLeaf, fallback: bool) -> Callable:  # noqa: FBT001
        trace_cls: type[Trace] = self._context.get("Trace", Trace)
        # Optimize: using closures to avoid property lookups each time
        trace_mode = self.trace
        fail_skip_excs = self.fail_skip

        def wrapper(ctx: T_contra) -> bool | Trace:
            try:
                return leaf.fn(ctx)
            except fail_skip_excs as e:
                if not trace_mode:
                    return fallback
                return trace_cls(
                    success=fallback,
                    operator="SKIP",
                    node=leaf,
                    desc=f"Skipped: (Default: {fallback})",
                    error=e,
                )

        return wrapper

    def _collect_chain(self, node: Predicate[T_contra], node_type: LogicBinOp) -> Iterable[Predicate]:
        chain = []
        current = node

        while isinstance(current, (_PredicateOr, _PredicateAnd)) and current.node_type == node_type:
            # handle right children
            if len(current.children) == 2:  # noqa: PLR2004
                chain.append(current.children[1])
                current = current.children[0]
            else:
                chain.extend(reversed(current.children))
                break
        if not (isinstance(current, (_PredicateAnd, _PredicateOr)) and current.node_type == node_type):
            chain.append(current)

        return reversed(chain)

    def _fix_locations_iterative(self, root: ast.AST) -> None:
        """
        Iterative implementation of ast.fix_missing_locations.
        Uses ast.iter_child_nodes to flatten the traversal logic.
        """
        stack = [root]

        while stack:
            node = stack.pop()
            if not getattr(node, "lineno", None):
                node.lineno = 1  # ty:ignore[invalid-assignment]
                node.col_offset = 0  # ty:ignore[invalid-assignment]
                node.end_lineno = 1  # ty:ignore[invalid-assignment]
                node.end_col_offset = 0  # ty:ignore[invalid-assignment]

            stack.extend(ast.iter_child_nodes(node))

    def _create_ast_leaf(self, leaf: _PredicateLeaf, fallback: bool) -> ast.Call:  # noqa: FBT001
        func_name = self._register_leaf(leaf, fallback)
        return ast.Call(
            func=ast.Name(id=func_name, ctx=ast.Load()),
            args=[ast.Name(id="ctx", ctx=ast.Load())],
            keywords=[],
        )

    class CompileStack(NamedTuple):
        """
        Represents a stack entry for predicate compilation.
        """

        node: Predicate | tuple[Literal["FLATTENED"], LogicBinOp, int]
        visited: bool
        fallback: bool

    # noinspection D
    def compile(  # noqa: D102
        self,
        p: Predicate[T_contra],
    ) -> Callable[[T_contra], bool | Trace]:
        # XXX: Hard to say whether evaluating an if statement or function lookup is faster during runtime;
        #  this may require specific profiling.

        # Markers are static, employing the pattern to pre-determine specific behaviours.
        process_not = self._process_not_trace if self.trace else self._process_not_bool
        process_binary = self._process_binary_trace if self.trace else self._process_binary_bool

        stack = [self.CompileStack(p, visited=False, fallback=self.root_fallback)]
        results: list[ast.expr] = []

        while stack:
            node, visited, fallback = stack.pop()
            node = cast("PredicateNode", node)
            if isinstance(node, tuple) and node[0] == "FLATTENED":
                _, op_type, count = node
                child_exprs = results[-count:]
                results[-count:] = []

                results.append(process_binary(op_type, child_exprs))
                continue

            if not visited:
                stack.append((node, True, fallback))
                match node:
                    case _PredicateLeaf() as p:
                        results.append(self._create_ast_leaf(p, fallback))
                    case (
                        _PredicateAnd(node_type=node_type, children=children)
                        | _PredicateOr(node_type=node_type, children=children)
                    ):
                        flat_tuple = ("FLATTENED", node_type, len(children))
                        chain = self._collect_chain(node, node_type)
                        stack.append(self.CompileStack(flat_tuple, visited=False, fallback=fallback))

                        child_fallback = node_type != "or"
                        for child in chain:
                            stack.append((child, False, child_fallback))

                    case _PredicateNot(op=op):
                        # Reversing the outer layer's expectations.
                        stack.append((op, False, not fallback))
                    case _:
                        assert_never(node)
            else:
                match node:
                    case _PredicateNot():
                        child_expr = results.pop()
                        results.append(process_not(child_expr))

        body_expr = results.pop()
        func_def = ast.FunctionDef(
            name=COMPILED_PREDICATE,
            args=ast.arguments(posonlyargs=[], args=[ast.arg(arg="ctx")], kwonlyargs=[], defaults=[], kw_defaults=[]),
            body=[ast.Return(value=body_expr)],
        )
        module = ast.Module(body=[func_def], type_ignores=[])

        self._fix_locations_iterative(module)
        if self.trace:
            self._inject_trace_helpers()

        code_obj = compile(module, filename="<ast>", mode="exec")
        exec(code_obj, self._context)  # noqa: S102

        return self._context[COMPILED_PREDICATE]

    @staticmethod
    def _build_lazy_trace_call(func_name: str, exprs: Sequence[ast.expr]) -> ast.Call:

        # First evaluated
        args = [exprs[0]]

        for expr in exprs[1:]:
            lambda_wrapper = ast.Lambda(
                args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=expr,
            )
            args.append(lambda_wrapper)

        return ast.Call(func=ast.Name(id=func_name, ctx=ast.Load()), args=args, keywords=[])

    # noinspection D
    def _inject_trace_helpers(self):
        self._context["Trace"] = Trace

        if self.short_circuit:

            def _rt_and(first: Trace[T_contra], *thunks: Callable[[], Trace[T_contra]]) -> Trace[T_contra]:
                res = first
                for thunk in thunks:
                    if not res.success:
                        return Trace(success=False, operator="and", children=(res,))
                    other = thunk()
                    res = res & other
                return res

            def _rt_or(first: Trace[T_contra], *thunks: Callable[[], Trace[T_contra]]) -> Trace[T_contra]:
                res = first
                for thunk in thunks:
                    if res.success:
                        return Trace(success=True, operator="or", children=(res,))

                    other = thunk()
                    res = res | other
                return res

        else:

            def _rt_and(first: Trace[T_contra], *thunks: Callable[[], Trace[T_contra]]) -> Trace[T_contra]:
                res = first
                for thunk in thunks:
                    res = res & thunk()
                return res

            def _rt_or(first: Trace[T_contra], *thunks: Callable[[], Trace[T_contra]]) -> Trace[T_contra]:
                res = first
                for thunk in thunks:
                    res = res | thunk()
                return res

        self._context[RT_AND] = _rt_and
        self._context[RT_OR] = _rt_or

    @staticmethod
    def _process_not_trace(child_expr: ast.expr) -> ast.UnaryOp:
        """Process NOT operation in trace mode (uses bitwise invert)."""
        return ast.UnaryOp(op=ast.Invert(), operand=child_expr)

    def _process_binary_trace(
        self,
        node_type: LogicBinOp,
        child_exprs: list[ast.expr],
    ) -> ast.Call:
        """Process AND/OR in trace mode (lazy evaluation with helpers)."""
        helper_name = RT_AND if node_type == "and" else RT_OR
        return self._build_lazy_trace_call(helper_name, child_exprs)

    @staticmethod
    def _process_not_bool(child_expr: ast.expr) -> ast.UnaryOp:
        """Process NOT operation in bool mode (logical not)."""
        return ast.UnaryOp(op=ast.Not(), operand=child_expr)

    def _process_binary_bool(
        self,
        node: LogicBinOp,
        child_exprs: list[ast.expr],
    ) -> ast.BoolOp:
        """Process AND/OR in bool mode (native short-circuit)."""
        op = ast.And() if node == "and" else ast.Or()
        return ast.BoolOp(op=op, values=child_exprs)
