from __future__ import annotations

from abc import ABC
from typing import Generic, TypeVar, Literal, Annotated

from pydantic import BaseModel, ConfigDict, Field, RootModel

X_PARAMS_ORDER = "x-params-order"


class BaseRuleConfig(BaseModel, ABC):
    """
    Base configuration class for rule-specific configurations.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid", frozen=True)

    rule_def_name: str


RuleUnionT = TypeVar("RuleUnionT")


class RuleSetManifest(BaseModel, Generic[RuleUnionT]):
    model_config = ConfigDict(populate_by_name=True, extra="forbid", frozen=True)

    registry: str
    rules: dict[str, LogicNode[RuleUnionT]] = Field(default_factory=dict, description="List of rule definitions")


class BaseLogicNode(BaseModel, ABC, Generic[RuleUnionT]):
    """
    Base class for all logic nodes in the predicate tree.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid", frozen=True)


class RefNode(BaseLogicNode[RuleUnionT]):
    model_config = ConfigDict(
        title="RefNode",
    )
    node_type: Literal["ref"] = Field("ref", description="Reference to a rule definition")
    ref_id: str = Field(..., description="Rule definition ID")


class LeafNode(BaseLogicNode[RuleUnionT]):
    model_config = ConfigDict(
        title="LeafNode",
    )
    node_type: Literal["leaf"] = Field("leaf", description="Leaf node in the predicate tree")
    rule: RuleUnionT = Field(..., description="The rule to evaluate")


class AndNode(BaseLogicNode[RuleUnionT]):
    model_config = ConfigDict(
        title="AndNode",
    )
    node_type: Literal["and"] = Field("and", description="And node in the predicate tree")
    rules: list[LogicNode[RuleUnionT]] = Field(..., min_length=2, description="All rules must pass")


class OrNode(BaseLogicNode[RuleUnionT]):
    model_config = ConfigDict(
        title="OrNode",
    )
    node_type: Literal["or"] = Field("or", description="Or node in the predicate tree")
    rules: list[LogicNode[RuleUnionT]] = Field(..., min_length=2, description="Any rule must pass")


class NotNode(BaseLogicNode[RuleUnionT]):
    model_config = ConfigDict(
        title="NotNode",
    )
    node_type: Literal["not"] = Field("not", description="Not node in the predicate tree")
    rule: LogicNode[RuleUnionT] = Field(..., description="The rule must fail")


# XXX: Wonder how many days it will take to write PEP 695.


class LogicNode(RootModel[RuleUnionT]):
    model_config = ConfigDict(title="LogicNode")

    root: Annotated[
        LeafNode[RuleUnionT] | AndNode[RuleUnionT] | OrNode[RuleUnionT] | NotNode[RuleUnionT] | RefNode[RuleUnionT],
        Field(discriminator="node_type"),
    ]


AndNode.model_rebuild()
OrNode.model_rebuild()
NotNode.model_rebuild()
LogicNode.model_rebuild()
