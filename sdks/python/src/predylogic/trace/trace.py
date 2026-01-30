from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Generic, Literal, Protocol, TypeVar, overload

if TYPE_CHECKING:
    from predylogic.predicate import Predicate
    from predylogic.types import LogicBinOp, LogicOp


if sys.version_info < (3, 11):
    pass
else:
    pass

T_contra = TypeVar("T_contra", contravariant=True)


class TraceStyle(Protocol):
    """
    Protocol for trace style rendering.
    """

    def render(self, trace: Trace, level: int = 0) -> str:
        """
        Render the trace object into a string representation with a specified indentation level.

        Returns:
            A string representation of the trace object with the specified indentation level.
        """
        ...


class DefaultTraceStyle(TraceStyle):
    """
    Default trace style implementation.
    """

    # TODO: based on the style of the terminal.
    ...


@dataclass(kw_only=True, slots=True, frozen=True)
class Trace(Generic[T_contra]):
    """
    Record the execution process of predicates and output the corresponding styles via the pattern.
    """

    success: bool
    operator: Literal[LogicOp, "PRUE_BOOL", "SKIP"]
    children: tuple[Trace, ...] = field(default_factory=list)

    node: Predicate[T_contra] | None = field(default=None, repr=False, compare=False)
    desc: str | None = field(default=None)
    value: T_contra | None = field(default=None, repr=False)
    error: Exception | None = field(default=None, repr=False)
    elapsed: float = field(default=0.0)

    _style: None | TraceStyle = field(hash=False, default=None, repr=False, compare=False, init=False)

    @property
    def style(self) -> TraceStyle:
        """
        Control the print style of Trace, for use with repr.
        """

        return self._style or DefaultTraceStyle()

    @style.setter
    def style(self, style: TraceStyle):
        object.__setattr__(self, "_style", style)

    def __bool__(self) -> bool:
        return self.success

    def __repr__(self) -> str:
        return self.style.render(self)

    @overload
    def __logic_help(
        self,
        op: LogicBinOp,
        other: Trace | bool,  # noqa: FBT001
    ) -> Trace: ...

    @overload
    def __logic_help(
        self,
        op: Literal["not"],
        other: None,
    ) -> Trace: ...

    def __logic_help(self, op: LogicOp, other: Trace | bool | None) -> Trace:  # noqa: FBT001
        if op != "not":
            if isinstance(other, bool):
                other_trace = Trace(success=other, operator="PRUE_BOOL")
            elif isinstance(other, Trace):
                other_trace = other
            else:
                return NotImplemented
            children = (self, other_trace)
            elapsed = self.elapsed + other_trace.elapsed
            if op == "and":
                success = self.success and other_trace.success
            elif op == "or":
                success = self.success or other_trace.success
            else:
                msg = f"Invalid logic operation: {op}"
                raise ValueError(msg)
        else:
            children = (self,)
            elapsed = self.elapsed
            success = not self.success

        return self.__class__(
            children=children,
            elapsed=elapsed,
            success=success,
            operator=op,
        )

    def __and__(self, other: Trace | bool) -> Trace:
        return self.__logic_help("and", other)

    def __or__(self, other: Trace | bool) -> Trace:
        return self.__logic_help("or", other)

    def __invert__(self) -> Trace:
        return self.__logic_help("not", None)
