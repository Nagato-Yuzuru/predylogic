from __future__ import annotations

from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeAlias, TypeGuard, TypeVar, final, overload

if TYPE_CHECKING:
    from predylogic.trace.trace import Trace
    from predylogic.types import PredicateNodeType

T_contra = TypeVar("T_contra", contravariant=True)

PredicateFn = Callable[[T_contra], bool]


@dataclass(frozen=True, kw_only=True)
class Predicate(Generic[T_contra], ABC):
    """
    Base class for predicate nodes in the predicate tree.
    """

    node_type: PredicateNodeType = field(init=False)
    desc: str | None = field(default=None)

    __compiled_fn: Callable[[T_contra], bool | Trace] | None = field(default=None, init=False, repr=False)

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
        raise NotImplementedError

    def __and__(
        self,
        other: Predicate[T_contra],
    ) -> Predicate[T_contra]:
        """
        Combine this predicate with another using logical AND.
        """
        if not is_predicate(other):
            return NotImplemented
        return _PredicateAnd(left=self, right=other)

    def __or__(self, other: Predicate[T_contra]) -> Predicate[T_contra]:
        if not is_predicate(other):
            return NotImplemented
        return _PredicateOr(left=self, right=other)

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
    left: Predicate[T_contra]
    right: Predicate[T_contra]


@dataclass(frozen=True, kw_only=True, slots=True)
@final
class _PredicateOr(Predicate[T_contra]):
    """
    Leaf node in the predicate tree.
    """

    node_type: Literal["or"] = field(default="or", init=False)
    left: Predicate[T_contra]
    right: Predicate[T_contra]


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

    Args:
        p: The object to check.

    """

    return isinstance(p, Predicate)
