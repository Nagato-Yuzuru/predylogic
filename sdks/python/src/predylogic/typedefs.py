from __future__ import annotations

from collections.abc import Callable
from typing import Concatenate, Literal, ParamSpec, TypeAlias, TypeVar

RunCtx_contra = TypeVar("RunCtx_contra", contravariant=True)
RuleParams = ParamSpec("RuleParams")

RuleDef: TypeAlias = Callable[Concatenate[RunCtx_contra, RuleParams], bool]

LogicBinOp: TypeAlias = Literal["and", "or"]
LogicOp: TypeAlias = Literal["not", LogicBinOp]

PredicateNodeType: TypeAlias = Literal["leaf", LogicOp]

# Spec vocabulary: the discriminator tags for payload-less type nodes, and the
# calling convention of a rule parameter (mirrors inspect.Parameter.kind).
AtomKind: TypeAlias = Literal["int", "str", "float", "bool", "none", "any"]
ParamKind: TypeAlias = Literal[
    "positional_only",
    "positional_or_keyword",
    "var_positional",
    "keyword_only",
    "var_keyword",
]

__all__ = [
    "AtomKind",
    "LogicBinOp",
    "LogicOp",
    "ParamKind",
    "PredicateNodeType",
    "RuleDef",
]
