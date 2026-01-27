from collections.abc import Callable
from typing import Concatenate, ParamSpec, TypeAlias, TypeVar

RunCtx_contra = TypeVar("RunCtx_contra", contravariant=True)
RuleParams = ParamSpec("RuleParams")

RuleDef: TypeAlias = Callable[Concatenate[RunCtx_contra, RuleParams], bool]

__all__ = ["RuleDef"]
