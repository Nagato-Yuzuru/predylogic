from __future__ import annotations

import inspect
from collections import OrderedDict
from functools import reduce
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypeVar

from caseconverter import pascalcase
from pydantic import ConfigDict, Field, create_model

from predylogic.schema.base import X_PARAMS_ORDER, BaseRuleConfig, RuleSetManifest

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from predylogic.register.registry import PredicateProducer, Registry

T_contra = TypeVar("T_contra", contravariant=True)


class SchemaGenerator:
    """
    Generate JSON Schema for PredyLogic rules.
    """

    def __init__(self, registry: Registry[T_contra]):
        self.registry = registry

    def generate(self) -> type[RuleSetManifest]:
        """
        Generates a dynamic RuleSetManifest model with rebuilt validation.

        The method dynamically constructs a RuleSetManifest model based on rule
        definitions fetched from the current object's context. The resulting model
        is renamed for clarity according to the current registry's name and its
        validation is rebuilt before returning the model.

        Returns:
            type[RuleSetManifest]: A dynamically created and rebuilt RuleSetManifest
            model specific to the registered rule definitions.
        """
        union_defs = self.get_rule_def_types()
        model = RuleSetManifest[union_defs]
        model.__name__ = f"{to_pascal(self.registry.name)}Manifest"

        model.model_rebuild()
        return model

    def get_rule_def_types(self) -> Any:  # noqa: ANN401
        """
        Generates the union of rule definitions from the current registry.

        This method creates a tuple of rule model definitions based on the current rule
        registry and combines them into a union type. If the registry is empty, it
        returns `NoneType`. The union definition includes a discriminator field for
        identifying specific rule definitions.

        Returns:
            Any: A union of all the rule definitions created from the registry or
            `NoneType` if no definitions exist.
        """
        defs = tuple(self._create_rule_model(rule_name, producer) for rule_name, producer in self.registry.items())
        if not defs:
            return type(None)
        union_defs = Annotated[reduce(lambda a, b: a | b, defs), Field(discriminator="rule_def_name")]  # ty:ignore[invalid-type-form]
        return union_defs

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

        model.__name__ = f"{to_pascal(rule_name)}Config"
        return model


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
