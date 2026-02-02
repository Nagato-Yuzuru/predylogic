import inspect
from collections import OrderedDict
from functools import reduce
from typing import Annotated, Any, Literal, TypeVar

from caseconverter import pascalcase
from pydantic import ConfigDict, Field, create_model
from pydantic.fields import FieldInfo

from predylogic.register.registry import PredicateProducer, Registry
from predylogic.schema.base import X_PARAMS_ORDER, RuleSetManifest, BaseRuleConfig

T_contra = TypeVar("T_contra", contravariant=True)


class SchemaGenerator:
    """
    Generate JSON Schema for PredyLogic rules.
    """

    def __init__(self, registry: Registry[T_contra]):
        self.registry = registry

    def generate(self) -> type[RuleSetManifest]:
        UnionDefs = self.get_rule_def_types()
        Model = RuleSetManifest[UnionDefs]
        Model.__name__ = f"{to_pascal(self.registry.name)}Manifest"

        Model.model_rebuild()
        return Model

    def get_rule_def_types(self) -> Any:
        defs = tuple(self._create_rule_model(rule_name, producer) for rule_name, producer in self.registry.items())
        if not defs:
            return type(None)
        UnionDefs = Annotated[reduce(lambda a, b: a | b, defs), Field(discriminator="rule_def_name")]  # ty:ignore[invalid-type-form]
        return UnionDefs

    def _create_rule_model(self, rule_name: str, producer: PredicateProducer) -> type[BaseRuleConfig]:
        sig = inspect.signature(producer)
        doc = inspect.getdoc(producer) or f"Configuration for {rule_name}"
        field_order = list(sig.parameters.keys())

        signatures = SignatureConv(sig).conv_to_pydantic_field()

        model = create_model(
            to_pascal(f"{rule_name}Config"),
            __base__=BaseRuleConfig,
            __doc__=doc,
            __config__=ConfigDict(
                json_schema_extra={X_PARAMS_ORDER: field_order},
            ),
            rule_def_name=(
                Literal[rule_name],  # ty:ignore[invalid-type-form]
                Field(description="Name of the rule definition in the registry"),
            ),
            **signatures,
        )  # ty:ignore[no-matching-overload]

        return model


class SignatureConv:
    def __init__(self, sig: inspect.Signature):
        self.sig = sig

    def conv_to_pydantic_field(self) -> OrderedDict[str, tuple[type, FieldInfo]]:
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
    return pascalcase(s)
