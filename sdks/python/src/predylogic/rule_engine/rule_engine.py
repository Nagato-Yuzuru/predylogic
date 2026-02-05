from __future__ import annotations

import sys
from threading import RLock
from typing import TYPE_CHECKING, Any, Literal, TypeVar, overload

from predylogic.predicate import ComposablePredicate, Predicate, all_of, any_of, predicate
from predylogic.register.errs import RegistryNotFoundError, RuleDefNotFoundError
from predylogic.rule_engine.base import AndNode, BaseRuleConfig, LeafNode, LogicNode, NotNode, OrNode, RefNode
from predylogic.rule_engine.errs import RuleRevokedError

if TYPE_CHECKING:
    from predylogic.register import RegistryManager
    from predylogic.rule_engine.base import RuleSetManifest
    from predylogic.trace import Trace
    from predylogic.typedefs import PredicateNodeType

if sys.version_info >= (3, 11):
    from typing import assert_never
else:
    from typing_extensions import assert_never

T = TypeVar("T")


class PredicateHandle(Predicate[T]):
    """
    Handle for predicates. Internally holds a predicate reference, enabling atomic updates during configuration refreshes.
    """

    def __init__(self, predicate: Predicate[T]):
        self.__predicate = predicate

    @property
    def node_type(self) -> PredicateNodeType:  # noqa: D102
        return self.__predicate.node_type

    @property
    def desc(self) -> str | None:  # noqa: D102
        return self.__predicate.desc

    @property
    def name(self) -> str | None:  # noqa: D102
        return self.__predicate.name

    @overload
    def __call__(
        self,
        ctx: T,
        /,
        *,
        trace: Literal[True],
        short_circuit: bool = True,
        fail_skip: tuple[type[Exception], ...] | None = None,
    ) -> Trace: ...

    @overload
    def __call__(
        self,
        ctx: T,
        /,
        *,
        trace: Literal[False] = False,
        short_circuit: Literal[True] = True,
        fail_skip: tuple[type[Exception], ...] | None = None,
    ) -> bool: ...

    def __call__(
        self,
        ctx: T,
        /,
        *,
        trace: bool = False,
        short_circuit: bool = True,
        fail_skip: tuple[type[Exception], ...] | None = None,
    ) -> bool | Trace:
        """
        Executes the callable object using the provided context and optional parameters to
        control execution behavior and error handling.

        Args:
            ctx: The context that is passed into the callable object during execution.
            trace: Specifies whether to enable tracing of execution for debugging or
                monitoring purposes. Defaults to False.
            short_circuit: Determines whether the execution should stop immediately upon
                encountering a failure. Defaults to True.
            fail_skip: A tuple of exception types to be skipped or ignored during execution.
                If provided, these exceptions will not disrupt the execution's flow. Defaults
                to None.

        Returns:
            Either a boolean indicating the success or failure of the operation, or a
            Trace object that contains detailed execution history if tracing is enabled.
        """
        return self.__predicate(
            ctx,
            trace=trace,
            short_circuit=short_circuit,
            fail_skip=fail_skip,
        )  # ty:ignore[no-matching-overload]

    def _update_predicate(self, predicate: Predicate[T]):
        self.__predicate = predicate


class RuleEngine:
    """
    Handles the management, updating, and retrieval of rule set manifests and predicate handles.

    The RuleEngine class is designed for managing rules and associated handlers. It provides
    functionalities to update rules and retrieve predicate handles for specified contexts. This
    is useful in systems where dynamic rule updates and context-specific predicate handling
    are required.

    Attributes:
        registry_manager (RegistryManager): Manages the registry of rule sets and their associated handlers.
    """

    def __init__(self, registry_manager: RegistryManager):
        self.registry_manager = registry_manager

        # NOTE: Using defaultdict carries the risk of implicit writes outside the lock.
        self._manifests: dict[str, RuleSetManifest[Any]] = {}
        self._compiled_rules: dict[str, dict[str, Predicate[Any]]] = {}
        self._handles: dict[str, dict[str, PredicateHandle[Any]]] = {}
        self._lock = RLock()

    @overload
    def get_predicate_handle(
        self,
        registry_name: str,
        rule_name: str,
        *,
        ctx_type: type[T],
    ) -> PredicateHandle[T]: ...

    @overload
    def get_predicate_handle(
        self,
        registry_name: str,
        rule_name: str,
    ) -> Predicate[Any]: ...

    def get_predicate_handle(self, registry_name: str, rule_name: str, *, ctx_type: Any = Any) -> Predicate[Any]:
        """
        Retrieves the handle for the specified predicate.

        This method is used to get a handle for a predicate based on the provided
        name and context type.

        The returned Predicate is a handle encapsulating the original Predicate.
        During `update_manifests`, atomic updates are performed on handles managed by the RuleEngine.

        Args:
            registry_name: name of the registry containing the predicate.
            rule_name: name of the predicate to retrieve.
            ctx_type: The type of context associated with the predicate.

        Returns:
            The handle for the specified predicate.
                If the predicate being looked up does not exist or has been deleted during a manifest update,
                a predicate will be returned that raises a RuleRevokedError exception.
        """

        if (registry_handles := self._handles.get(registry_name)) and (handle := registry_handles.get(rule_name)):
            return handle

        with self._lock:
            registry_handles = self._handles.setdefault(registry_name, {})
            if handle := registry_handles.get(rule_name):
                return handle
            registry_cache = self._compiled_rules.get(registry_name, {})

            pred = registry_cache.get(rule_name) or self._missing_predicate(registry_name, rule_name)
            handle = PredicateHandle(pred)
            registry_handles[rule_name] = handle
            return handle

    def update_manifests(self, *manifests: RuleSetManifest):
        """
        Updates the provided manifests to the current instance.

        This method is expected to take one or more manifests of type RuleSetManifest.

        Rules bearing identical names within the same registry will be updated. Handles managed by the engine,
        where updated rules exist on the chain, will likewise be updated.

        Args:
            manifests: One or more instances of RuleSetManifest that are to
                be updated.
        """

        updates_map = {
            m.registry: {rule_id: self._compile_node(node, m) for rule_id, node in m.rules.items()} for m in manifests
        }

        manifests_dict = {m.registry: m for m in manifests}

        with self._lock:
            for registry_name, new_rules in updates_map.items():
                self._manifests[registry_name] = manifests_dict[registry_name]

                registry_cache = self._compiled_rules.setdefault(registry_name, {})
                registry_cache.update(new_rules)
                handle_registry = self._handles.get(registry_name, {})
                for rule_name, new_pred in new_rules.items():
                    if handle := handle_registry.get(rule_name):
                        handle._update_predicate(new_pred)

    def _compile_node(
        self,
        node: LogicNode,
        manifest: RuleSetManifest,
    ) -> ComposablePredicate:
        """
        Recursively compiles a LogicNode into a Predicate tree.
        """
        inner = node.root

        match inner:
            case LeafNode(rule=rule_config):
                return self._predicate_from_rule_config(manifest.registry, rule_config)
            case RefNode(ref_id=ref_id):
                handle = self.get_predicate_handle(manifest.registry, ref_id)
                return predicate(handle, name=ref_id, desc=f"Ref -> {manifest.registry}::{ref_id}")
            case AndNode(rules=rules):
                children = [self._compile_node(child, manifest) for child in rules]
                return all_of(children)
            case OrNode(rules=rules):
                children = [self._compile_node(child, manifest) for child in rules]
                return any_of(children)
            case NotNode(rule=rule):
                return ~self._compile_node(rule, manifest)
            case _:
                assert_never(inner)

    def _predicate_from_rule_config(self, registry_name: str, rule_config: BaseRuleConfig) -> ComposablePredicate:
        registry = self.registry_manager.get_register(registry_name)
        if registry is None:
            raise RegistryNotFoundError(registry_name)

        rule_def_name = rule_config.rule_def_name

        producer = registry.get(rule_def_name)
        if producer is None:
            raise RuleDefNotFoundError(rule_def_name)

        params = rule_config.model_dump(by_alias=True, exclude={"rule_def_name"})
        return producer(**params)

    def _missing_predicate(self, registry_name: str, rule_name: str) -> Predicate:
        def _raise(_) -> bool:  # noqa: ANN001
            raise RuleRevokedError(registry_name, rule_name)

        return predicate(
            _raise,
            name=rule_name,
            desc=f"Revoked/Missing rule '{rule_name}' in registry '{registry_name}'",
        )
