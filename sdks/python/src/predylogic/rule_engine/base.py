from __future__ import annotations

import sys
from abc import ABC
from graphlib import CycleError, TopologicalSorter
from typing import TYPE_CHECKING, Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator

from predylogic.rule_engine.errs import RuleDefRingError

if TYPE_CHECKING:
    from collections.abc import Generator

if sys.version_info >= (3, 11):
    from typing import assert_never
else:
    from typing_extensions import assert_never

X_PARAMS_ORDER = "x-params-order"


class BaseRuleConfig(BaseModel, ABC):
    """
    Base configuration class for rule-specific configurations.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid", frozen=True)

    rule_def_name: str


if TYPE_CHECKING:
    RuleUnionT = TypeVar("RuleUnionT", bound=BaseRuleConfig)
else:
    RuleUnionT = TypeVar("RuleUnionT")


class RuleSetManifest(BaseModel, Generic[RuleUnionT]):
    """
    Represents a manifest for a rule set.

    This class defines the structure for a rule set manifest, its intended purpose, and usage in defining
    rule configurations. It allows for registry information alongside a set of interconnected rules
    represented as a Directed Acyclic Graph (DAG). The rules are defined with their relationships
    and logic nodes.

    Attributes:
        registry (str): The registry name associated with the rule set.
        rules (dict[str, LogicNode[RuleUnionT]]): A dictionary representing the DAG of rule definitions,
            where keys are rule identifiers and values are their corresponding logic nodes.

    Raises:
        RuleDefRingError: If a rule definition creates a cyclic dependency.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    registry: str
    rules: dict[str, LogicNode[RuleUnionT]] = Field(default_factory=dict, description="Dag of rule definitions.")

    @field_validator("rules", mode="after")
    @classmethod
    def _validate_rule_ring(cls, v: dict[str, LogicNode[RuleUnionT]]) -> dict[str, LogicNode[RuleUnionT]]:
        graph: dict[str, set[str]] = {}
        for rid, node in v.items():
            graph[rid] = set(get_dependencies(node))
        ts = TopologicalSorter(graph)
        try:
            ts.prepare()
        except CycleError as e:
            ring: tuple[str] = e.args[1]

            raise RuleDefRingError(ring) from e
        return v


class BaseLogicNode(BaseModel, ABC, Generic[RuleUnionT]):
    """
    Base class for all logic nodes in the predicate tree.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid", frozen=True)


class RefNode(BaseLogicNode[RuleUnionT]):
    """
    Reference a named node. Allow the use of a specific rule to continue the computation.
    """

    model_config = ConfigDict()
    node_type: Literal["ref"] = Field("ref", description="Reference to a rule definition")
    ref_id: str = Field(..., description="Rule definition ID")


class LeafNode(BaseLogicNode[RuleUnionT]):
    """
    Leaf node. Atomic node.
    """

    model_config = ConfigDict(
        title="LeafNode",
    )
    node_type: Literal["leaf"] = Field("leaf", description="Leaf node in the predicate tree")
    rule: RuleUnionT = Field(..., description="The rule to evaluate")


class AndNode(BaseLogicNode[RuleUnionT]):
    """
    Using non-binary AND nodes enables efficient compilation to predicate dis.
    """

    model_config = ConfigDict(
        title="AndNode",
    )
    node_type: Literal["and"] = Field("and", description="And node in the predicate tree")
    rules: list[LogicNode[RuleUnionT]] = Field(..., min_length=2, description="All rules must pass")


class OrNode(BaseLogicNode[RuleUnionT]):
    """
    Using non-binary OR nodes enables efficient compilation to predicate dis.
    """

    model_config = ConfigDict(
        title="OrNode",
    )
    node_type: Literal["or"] = Field("or", description="Or node in the predicate tree")
    rules: list[LogicNode[RuleUnionT]] = Field(..., min_length=2, description="Any rule must pass")


class NotNode(BaseLogicNode[RuleUnionT]):
    """
    Not node in the predicate tree.
    """

    model_config = ConfigDict(
        title="NotNode",
    )
    node_type: Literal["not"] = Field("not", description="Not node in the predicate tree")
    rule: LogicNode[RuleUnionT] = Field(..., description="The rule must fail")


# XXX: Wonder how many days it will take to write PEP 695.


class LogicNode(RootModel[RuleUnionT]):
    """
    To support non-PEP695 syntax, use the Root Model. Further optimize generics.
    """

    model_config = ConfigDict(
        title="LogicNode",
        populate_by_name=True,
    )

    root: Annotated[
        LeafNode[RuleUnionT] | AndNode[RuleUnionT] | OrNode[RuleUnionT] | NotNode[RuleUnionT] | RefNode[RuleUnionT],
        Field(discriminator="node_type"),
    ]


AndNode.model_rebuild()
OrNode.model_rebuild()
NotNode.model_rebuild()
LogicNode.model_rebuild()


def get_dependencies(node: LogicNode[RuleUnionT]) -> Generator[str]:
    """
    Recursively traverse the LogicNode tree and extract the ref_id of all RefNodes.
    """
    inner = node.root

    match inner:
        case RefNode(ref_id=ref_id):
            yield ref_id
        case AndNode() | OrNode() as node:
            for child in node.rules:
                yield from get_dependencies(child)
        case NotNode(rule=rule):
            yield from get_dependencies(rule)
        case LeafNode():
            return
        case _:
            assert_never(inner)
