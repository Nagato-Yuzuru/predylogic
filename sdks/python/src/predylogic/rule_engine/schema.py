from __future__ import annotations

import inspect
import types
import typing
from collections import OrderedDict
from functools import cached_property, reduce
from typing import TYPE_CHECKING, Annotated, Any, Generic, Literal, TypeVar

from caseconverter import pascalcase
from pydantic import ConfigDict, Field, RootModel, create_model

from predylogic.rule_engine.base import BaseRuleConfig, BaseRuleParams, RuleSetManifest
from predylogic.rule_engine.spec import (
    AtomType,
    ParamSpec,
    ParamType,
    RegistrySpec,
    RuleSpec,
    TypeDict,
    TypeList,
    TypeUnion,
    TypeUnknown,
    WorkspaceSpec,
)

if TYPE_CHECKING:
    from types import UnionType

    from pydantic.fields import FieldInfo

    from predylogic.register.registry import PredicateProducer, Registry, RegistryManager
    from predylogic.typedefs import ParamKind

T_cap = TypeVar("T_cap")
T_union = TypeVar("T_union")

_PARAM_KIND_NAMES: dict[inspect._ParameterKind, ParamKind] = {
    inspect.Parameter.POSITIONAL_ONLY: "positional_only",
    inspect.Parameter.POSITIONAL_OR_KEYWORD: "positional_or_keyword",
    inspect.Parameter.VAR_POSITIONAL: "var_positional",
    inspect.Parameter.KEYWORD_ONLY: "keyword_only",
    inspect.Parameter.VAR_KEYWORD: "var_keyword",
}

_VAR_PARAM_KINDS = frozenset({inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD})


def _serialize_type(anno: Any) -> ParamType:  # noqa: C901, PLR0911, ANN401
    if anno is inspect.Parameter.empty or anno is typing.Any:
        return AtomType(kind="any")
    if isinstance(anno, str):
        return TypeUnknown(repr=anno)
    if anno is type(None):
        return AtomType(kind="none")
    if anno is int:
        return AtomType(kind="int")
    if anno is str:
        return AtomType(kind="str")
    if anno is float:
        return AtomType(kind="float")
    if anno is bool:
        return AtomType(kind="bool")
    if isinstance(anno, types.UnionType):
        return TypeUnion(variants=tuple(_serialize_type(a) for a in typing.get_args(anno)))
    origin = typing.get_origin(anno)
    args = typing.get_args(anno)
    if origin is typing.Union:
        return TypeUnion(variants=tuple(_serialize_type(a) for a in args))
    if origin is list:
        return TypeList(element=_serialize_type(args[0] if args else typing.Any))
    if origin is dict:
        return TypeDict(
            key=_serialize_type(args[0] if args else typing.Any),
            value=_serialize_type(args[1] if len(args) > 1 else typing.Any),
        )
    return TypeUnknown(repr=str(anno))


def _rule_spec(producer: PredicateProducer) -> RuleSpec:
    # RuleDefConverter sets __signature__ on the wrapper, which blocks eval_str.
    # @wraps preserves __wrapped__ pointing at the original fn, whose annotations
    # are string-deferred when the defining module uses `from __future__ import annotations`.
    # Resolving via __wrapped__ + eval_str=True gives us actual type objects.
    wrapped = getattr(producer, "__wrapped__", None)
    if wrapped is not None:
        try:
            full_sig = inspect.signature(wrapped, eval_str=True)
            # Drop the first parameter (the context arg, e.g. `user: User`).
            params_seq = list(full_sig.parameters.values())[1:]
        except Exception:
            params_seq = list(inspect.signature(producer).parameters.values())
    else:
        params_seq = list(inspect.signature(producer).parameters.values())

    doc = inspect.getdoc(producer)
    params = tuple(
        ParamSpec(
            name=p.name,
            type=_serialize_type(p.annotation),
            required=p.default is inspect.Parameter.empty and p.kind not in _VAR_PARAM_KINDS,
            param_kind=_PARAM_KIND_NAMES[p.kind],
        )
        for p in params_seq
    )
    return RuleSpec(params=params, desc=doc)


def generate_workspace_spec(manager: RegistryManager) -> WorkspaceSpec:
    """
    Generate the predylogic native workspace spec.

    The spec encodes every registry's rule names, parameter types, and calling
    conventions. It is consumed by the Rust CLI (CI gate and LSP server) and
    passed to the PyO3 parser at runtime as the trust boundary for DSL validation.
    Call `.to_json()` on the result to serialise for the PyO3 / CLI boundary.
    """
    return WorkspaceSpec(
        registries={name: SchemaGenerator(registry).generate_spec() for name, registry in manager.items()},
    )


class SchemaGenerator(Generic[T_cap]):
    """
    Generate JSON Schema and predylogic native specs from a Registry.
    """

    def __init__(self, registry: Registry[T_cap]):
        self.registry = registry

    def generate(self) -> type[RuleSetManifest]:
        """
        Generates a dynamic RuleSetManifest model with rebuilt validation.

        The method dynamically constructs a RuleSetManifest model based on rule
        definitions fetched from the current object's context. The resulting model
        is renamed for clarity according to the current registry's name and its
        validation is rebuilt before returning the model.

        Returns:
            A dynamically created and rebuilt RuleSetManifest
            model specific to the registered rule definitions.
        """
        union_defs = self.rule_def_types
        model = create_model(
            f"{to_pascal(self.registry.name)}Manifest",
            __base__=RuleSetManifest[union_defs],  # ty:ignore[invalid-type-form]
            registry=(
                Literal[self.registry.name],  # ty:ignore[invalid-type-form]
                Field(
                    self.registry.name,
                    description="Name of the registry containing the rule definitions",
                    init=False,
                ),
            ),
        )

        model.model_rebuild()
        return model

    def generate_spec(self) -> RegistrySpec:
        """
        Generate the predylogic native spec for this registry.

        Returns a RegistrySpec encoding each rule's description, parameter names,
        types, required flag, and calling convention. Intended for use by
        the Rust CLI and PyO3 parser; see `generate_workspace_spec` for the
        multi-registry form.
        """
        return RegistrySpec(
            rules={name: _rule_spec(producer) for name, producer in self.registry.items()},
        )

    @cached_property
    def rule_def_types(self) -> UnionType | type:
        """
        Generates the union of rule definitions from the current registry.

        This method creates a tuple of rule model definitions based on the current rule
        registry and combines them into a union type. If the registry is empty, it
        returns `NoneType`. The union definition includes a discriminator field for
        identifying specific rule definitions.

        Returns:
            A union of all the rule definitions created from the registry or
            `NoneType` if no definitions exist.
        """
        defs = tuple(self._create_rule_model(rule_name, producer) for rule_name, producer in self.registry.items())
        if not defs:
            return type(None)
        return reduce(lambda a, b: a | b, defs)

    def _wrap_named_union(self, union_type: T_union) -> type[RootModel[T_union]]:
        name = f"{to_pascal(self.registry.name)}RuleDef"
        wrapped = create_model(
            name,
            __base__=RootModel,
            __config__=ConfigDict(title=name),
            root=(
                Annotated[union_type, Field(discriminator="rule_def_name")],
                Field(..., description="The rule definition to evaluate"),
            ),
        )
        wrapped.__name__ = name
        return wrapped

    def _create_rule_model(self, rule_name: str, producer: PredicateProducer[T_cap, ...]) -> type[BaseRuleConfig]:
        sig = inspect.signature(producer)
        doc = inspect.getdoc(producer) or f"Configuration for {rule_name}"

        signatures = SignatureConv(sig).conv_to_pydantic_field()
        param_kinds = {name: param.kind for name, param in sig.parameters.items()}

        params_name = to_pascal(f"{rule_name}Params")
        params_model = create_model(
            params_name,
            __base__=BaseRuleParams,
            **signatures,
        )  # ty:ignore[no-matching-overload]
        params_model.__name__ = params_name
        # Attached so `RuleEngine._predicate_from_rule_config` can re-expand
        # VAR_POSITIONAL / VAR_KEYWORD fields into `*args` / `**kwargs` at
        # call time — Pydantic flattens both into named fields.
        params_model.__param_kinds__ = param_kinds

        # Only default `params` to an empty model when there is nothing required
        # to supply. Otherwise `default_factory=params_model` would run on missing
        # input and surface the inner "field required" error, masking the real
        # "params is missing" signal at the config level.
        if any(f.is_required() for f in params_model.model_fields.values()):
            params_field = Field(description="Parameters for the rule")
        else:
            params_field = Field(default_factory=params_model, description="Parameters for the rule")

        config_name = to_pascal(f"{rule_name}Config")
        config_model = create_model(
            config_name,
            __base__=BaseRuleConfig,
            __doc__=doc,
            rule_def_name=(
                Literal[rule_name],  # ty:ignore[invalid-type-form]
                Field(rule_name, description="Name of the rule definition in the registry", init=False),
            ),
            params=(params_model, params_field),
        )
        config_model.__name__ = config_name
        return config_model


class SignatureConv:
    """
    Helper class for converting inspect.Signature to Pydantic field definitions.
    """

    def __init__(self, sig: inspect.Signature):
        self.sig = sig

    def conv_to_pydantic_field(self) -> OrderedDict[str, tuple[type, FieldInfo]]:
        """
        Convert inspect.Signature to Pydantic field definitions.
        """
        # XXX: After implementing the loader, perform special handling here.
        fields: OrderedDict[str, tuple[type, FieldInfo]] = OrderedDict()
        for name, param in self.sig.parameters.items():
            pyd_type, pyd_default = self._convert_param(param)
            fields[name] = (pyd_type, pyd_default)
        return fields

    def _convert_param(self, param: inspect.Parameter) -> tuple[type, FieldInfo]:
        anno = param.annotation
        kind = param.kind
        default = param.default

        base_type = Any if anno is param.empty else anno

        if kind == inspect.Parameter.VAR_POSITIONAL:
            final_type = list[base_type]
            final_default = Field(default_factory=list)
        elif kind == inspect.Parameter.VAR_KEYWORD:
            final_type = dict[str, base_type]
            final_default = Field(default_factory=dict)
        else:
            final_type = base_type
            final_default = Field(... if default is inspect.Parameter.empty else default)
        # TODO: support CEL and re cache.

        return final_type, final_default


def to_pascal(s: str) -> str:
    """
    Convert a string to PascalCase.
    """
    return pascalcase(s)
