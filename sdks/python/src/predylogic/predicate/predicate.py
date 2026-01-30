from __future__ import annotations

import ast
import sys
from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import RLock
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Literal,
    NamedTuple,
    TypeAlias,
    TypeGuard,
    TypeVar,
    cast,
    final,
    overload,
)

from predylogic.trace.trace import Trace
from predylogic.types import LogicBinOp

if sys.version_info >= (3, 11):
    from typing import assert_never
else:
    from typing_extensions import assert_never

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from predylogic.types import PredicateNodeType

T_contra = TypeVar("T_contra", contravariant=True)

FLATTENED_TUPLE: TypeAlias = tuple[Literal["FLATTENED"], LogicBinOp, int]
PredicateFn = Callable[[T_contra], bool]

COMPILED_PREDICATE = "_compiled_predicate"
RT_OR = "_rt_or"
RT_AND = "_rt_and"


@dataclass(frozen=True, kw_only=True)
class Predicate(Generic[T_contra], ABC):
    """
    Represents a base class for predicates with logical operations
    and evaluation on a given context.

    This class defines the foundation for creating and combining predicates
    that can evaluate certain conditions in a provided context. It also
    supports logical operations such as AND, OR, and NOT for building
    complex predicate expressions.

    """

    node_type: PredicateNodeType = field(init=False)
    desc: str | None = field(default=None)
    name: str | None = field(default=None)
    __compiler_cache: dict[tuple, Callable[[T_contra], Trace | bool]] = field(
        default_factory=dict,
        init=False,
        repr=False,
        hash=False,
        compare=False,
    )
    __lock: RLock = field(default_factory=RLock, init=False, repr=False, hash=False, compare=False)

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
        Executes the callable object using the provided context and optional parameters to
        control execution behavior and error handling.

        Args:
            ctx: The context that is passed into the callable object during execution.
            trace: Specifies whether to enable tracing of execution for debugging or
                monitoring purposes. Defaults to False.
            short_circuit: Determines whether the execution should stop immediately upon
                encountering a failure. Defaults to True.
            fail_skip: A tuple of exception types to be skipped or ignored during execution.
                If provided, these exceptions will not disrupt the execution's flow. Defaults
                to None.

        Returns:
            Either a boolean indicating the success or failure of the operation, or a
            Trace object that contains detailed execution history if tracing is enabled.
        """

        cache_key = (trace, short_circuit, fail_skip)
        runner = self.__compiler_cache.get(cache_key)
        if not runner:
            with self.__lock:
                runner = Compiler(trace=trace, short_circuit=short_circuit, fail_skip=fail_skip).compile(self)
                self.__compiler_cache[cache_key] = runner
        return runner(ctx)

    def __and__(
        self,
        other: Predicate[T_contra],
    ) -> Predicate[T_contra]:
        """
        Combine this predicate with another using logical AND.

        To create a large number of consecutive __and__ combinations,
        the `Predicate.all` method should be used to avoid the overhead of creating additional objects.
        """
        if not is_predicate(other):
            return NotImplemented
        return _PredicateAnd(children=(self, other))

    def __or__(self, other: Predicate[T_contra]) -> Predicate[T_contra]:
        """
        Combine this predicate with another using logical or.

        To create a large number of consecutive __or__ combinations,
        the `Predicate.any` method should be used to avoid the overhead of creating additional objects.
        """

        if not is_predicate(other):
            return NotImplemented
        return _PredicateOr(children=(self, other))

    def __invert__(self) -> Predicate[T_contra]:
        """
        Combine this predicate with another using logical not.
        """

        return _PredicateNot(op=self)

    @classmethod
    def all(cls, predicates: Sequence[Predicate[T_contra]]) -> Predicate[T_contra]:
        """
        Use this method to combine multiple predicates,
            thereby avoiding the object creation overhead associated with chained calls.

        Args:
            predicates: Predicates are combined sequentially using `and`.

        """
        if not predicates:
            msg = "Expected at least one predicate"
            raise ValueError(msg)
        if len(predicates) == 1:
            return predicates[0]
        return _PredicateAnd(children=tuple(predicates))

    @classmethod
    def any(cls, predicates: Sequence[Predicate[T_contra]]) -> Predicate[T_contra]:
        """
        Use this method to combine multiple predicates,
            thereby avoiding the object creation overhead associated with chained calls.

        Args:
            predicates: Predicates are combined sequentially using `or`.

        """
        if not predicates:
            msg = "Expected at least one predicate"
            raise ValueError(msg)
        if len(predicates) == 1:
            return predicates[0]
        return _PredicateOr(children=tuple(predicates))


def predicate(fn: PredicateFn[T_contra], *, name: str, desc: str | None = None) -> Predicate[T_contra]:
    """
    Creates and returns a Predicate object from a given predicate function.

    This function allows you to wrap a predicate function in a Predicate object with
    an optional descriptive string. The descriptive string can be used to annotate the
    function's purpose or behavior and defaults to the function's docstring if not provided.

    Args:
        fn:
            The predicate function to be wrapped. A predicate is a callable that takes
            an input of type T_contra and returns a boolean value.
        name: name of predicate
        desc:
            An optional description of the predicate. If not provided, the function's
            docstring will be used as the description.

    Returns:
        Predicate[T_contra]
            A Predicate instance that encapsulates the provided predicate function and
            its associated description.
    """

    return _PredicateLeaf(fn=fn, desc=desc or fn.__doc__, name=name)


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
    And node in the predicate tree.
    """

    node_type: Literal["and"] = field(default="and", init=False)
    children: tuple[Predicate[T_contra], ...]

    def __and__(self, other: Predicate[T_contra]) -> Predicate[T_contra]:
        if not is_predicate(other):
            return NotImplemented
        return _PredicateAnd(children=(self, other))

    # def __post_init__(self):
    #     if len(self.children) <= 2:
    #         msg = "Too few children for AND predicate"
    #         raise ValueError(msg)


@dataclass(frozen=True, kw_only=True, slots=True)
@final
class _PredicateOr(Predicate[T_contra]):
    """
    Or node in the predicate tree.
    """

    node_type: Literal["or"] = field(default="or", init=False)
    children: tuple[Predicate[T_contra], ...]

    # def __post_init__(self):
    #     if len(self.children) <= 2:
    #         msg = "Too few children for OR predicate"
    #         raise ValueError(msg)
    def __or__(self, other: Predicate[T_contra]) -> Predicate[T_contra]:
        if not is_predicate(other):
            return NotImplemented
        return _PredicateOr(children=(self, other))


@dataclass(frozen=True, kw_only=True, slots=True)
@final
class _PredicateNot(Predicate[T_contra]):
    """
    Not node in the predicate tree.
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

            if self.trace:
                # In trace mode, the leaf must return Trace. We always wrap raw booleans.
                if self.fail_skip:
                    self._context[name] = self._wrap_with_fail_skip(leaf, fallback)
                else:
                    trace_cls: type[Trace] = self._context.get("Trace", Trace)

                    def _wrap(
                        ctx: T_contra,
                        _leaf: _PredicateLeaf = leaf,
                        _trace_cls: type[Trace] = trace_cls,
                    ) -> Trace:
                        res = _leaf.fn(ctx)
                        return _trace_cls(success=bool(res), operator="leaf", node=_leaf)

                    self._context[name] = _wrap
            elif self.fail_skip:
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
                res = leaf.fn(ctx)
                if not trace_mode:
                    return res
                return trace_cls(success=bool(res), operator="leaf", node=leaf)
            except fail_skip_excs as e:
                if not trace_mode:
                    return fallback
                return trace_cls(
                    success=fallback,
                    operator="SKIP",
                    node=leaf,
                    value=ctx,
                    error=e,
                )

        return wrapper

    def _collect_chain(self, node: Predicate[T_contra], node_type: LogicBinOp) -> Iterable[Predicate]:
        chain = []
        current = node

        while True:
            if current.node_type != node_type:
                break
            current = cast("_PredicateAnd | _PredicateOr", current)

            children = current.children

            if len(children) == 2:  # noqa: PLR2004
                # collect left first
                current = children[0]
                chain.append(children[1])
            else:
                # N-ary back (Mixed mode)
                if not children:
                    break
                chain.extend(children[1:])
                current = children[0]

        chain.append(current)
        return chain

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

        node: Predicate | FLATTENED_TUPLE
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
            node = cast("PredicateNode | FLATTENED_TUPLE", node)
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
                        # Stack is LIFO: push in reverse so evaluation is left-to-right.
                        stack.extend((child, False, child_fallback) for child in chain)

                    case _PredicateNot(op=op):
                        # Reversing the outer layer's expectations.
                        stack.append((op, False, not fallback))
                    case tuple():
                        pass
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
            decorator_list=[],
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
    def _inject_trace_helpers(self):  # noqa: C901
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
