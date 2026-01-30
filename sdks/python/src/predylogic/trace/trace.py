from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Generic, Literal, Protocol, TypeVar, overload

if TYPE_CHECKING:
    from predylogic.predicate import Predicate
    from predylogic.types import LogicBinOp, LogicOp, PredicateNodeType

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

    def render(self, trace: Trace, level: int = 0) -> str:
        """
        Render the trace object into a string representation with a specified indentation level.
        """
        indent = "  " * level

        if trace.node and trace.node.desc:
            label = trace.node.desc
            if trace.operator in ("and", "or", "not"):
                label = f"{label} <{trace.operator.upper()}>"
        else:
            label = trace.operator.upper()

        if trace.operator == "SKIP":
            icon = "⏭️ "
        elif trace.success:
            icon = "✅"
        else:
            icon = "❌"

        line = f"{indent}{icon} {label}"

        should_show_value = trace.value is not None and (not trace.success or trace.operator == "SKIP")

        if should_show_value:
            val_indent = "  " * (level + 1)
            line += f"\n{val_indent}└─ Context: {trace.value!r}"

        if trace.error:
            err_indent = "  " * (level + 1)
            line += f"\n{err_indent}💥 Error: {trace.error!r}"

        lines = [line]
        for child in trace.children:
            lines.append(self.render(child, level + 1))

        return "\n".join(lines)


@dataclass(kw_only=True, slots=True, frozen=True)
class Trace(Generic[T_contra]):
    """
    Record the execution process of predicates and output the corresponding styles via the pattern.
    """

    success: bool
    operator: Literal[PredicateNodeType, "PURE_BOOL", "SKIP"]
    children: tuple[Trace, ...] = field(default_factory=tuple)

    node: Predicate[T_contra] | None = field(default=None, repr=False, compare=False)
    value: T_contra | None = field(default=None, repr=False)
    error: Exception | None = field(default=None, repr=False)

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
                other_trace = Trace(success=other, operator="PURE_BOOL")
            elif isinstance(other, Trace):
                other_trace = other
            else:
                return NotImplemented
            children = (self, other_trace)
            if op == "and":
                success = self.success and other_trace.success
            elif op == "or":
                success = self.success or other_trace.success
            else:
                msg = f"Invalid logic operation: {op}"
                raise ValueError(msg)
        else:
            children = (self,)
            success = not self.success

        return self.__class__(
            children=children,
            success=success,
            operator=op,
        )

    def __and__(self, other: Trace | bool) -> Trace:
        return self.__logic_help("and", other)

    def __or__(self, other: Trace | bool) -> Trace:
        return self.__logic_help("or", other)

    def __invert__(self) -> Trace:
        return self.__logic_help("not", None)
