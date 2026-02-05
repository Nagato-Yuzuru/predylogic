from __future__ import annotations

from collections.abc import Callable
from typing import Concatenate, Literal, ParamSpec, TypeAlias, TypeVar

RunCtx_contra = TypeVar("RunCtx_contra", contravariant=True)
RuleParams = ParamSpec("RuleParams")

RuleDef: TypeAlias = Callable[Concatenate[RunCtx_contra, RuleParams], bool]

LogicBinOp: TypeAlias = Literal["and", "or"]
LogicOp: TypeAlias = Literal["not", LogicBinOp]

PredicateNodeType: TypeAlias = Literal["leaf", LogicOp]

__all__ = ["LogicBinOp", "LogicOp", "PredicateNodeType", "RuleDef"]
