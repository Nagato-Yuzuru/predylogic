from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Literal, TypeAlias

if TYPE_CHECKING:
    from predylogic.typedefs import AtomKind, ParamKind

# ── type nodes ────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AtomType:
    """A type with no inner structure: int / str / float / bool / none / any."""

    kind: AtomKind


@dataclass(frozen=True, slots=True)
class TypeList:
    """Spec node for `list[T]`."""

    element: ParamType
    kind: Literal["list"] = field(default="list", init=False)


@dataclass(frozen=True, slots=True)
class TypeDict:
    """Spec node for `dict[K, V]`."""

    key: ParamType
    value: ParamType
    kind: Literal["dict"] = field(default="dict", init=False)


@dataclass(frozen=True, slots=True)
class TypeUnion:
    """Spec node for `X | Y` / `Union[X, Y]` (including `Optional[X]`)."""

    variants: tuple[ParamType, ...]
    kind: Literal["union"] = field(default="union", init=False)


@dataclass(frozen=True, slots=True)
class TypeUnknown:
    """A Python type with no predylogic-native representation; carries its `repr` for diagnostics."""

    repr: str
    kind: Literal["unknown"] = field(default="unknown", init=False)


ParamType: TypeAlias = AtomType | TypeList | TypeDict | TypeUnion | TypeUnknown

# ── param ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ParamSpec:
    """A single rule parameter: name, type, whether it is required, and calling convention."""

    name: str
    type: ParamType
    required: bool
    param_kind: ParamKind
    desc: str | None = None


# ── spec ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RuleSpec:
    """One named rule: its ordered parameters and an optional description."""

    params: tuple[ParamSpec, ...]
    desc: str | None = None


@dataclass(frozen=True, slots=True)
class RegistrySpec:
    """One registry: a map of rule name to RuleSpec."""

    rules: dict[str, RuleSpec]


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkspaceSpec:
    """Complete predylogic workspace spec covering every registry in a RegistryManager."""

    version: str = field(default="1", init=False)
    registries: dict[str, RegistrySpec]

    def to_json(self) -> str:
        """Serialise to JSON for the PyO3 / CLI boundary, omitting None-valued optional fields."""
        return json.dumps(asdict(self, dict_factory=_omit_none))


def _omit_none(items: list[tuple[str, object]]) -> dict[str, object]:
    """`asdict` dict_factory that drops None-valued keys at construction time."""
    return {k: v for k, v in items if v is not None}
