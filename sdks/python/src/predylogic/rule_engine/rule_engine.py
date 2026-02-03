from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, TypeVar, overload

from predylogic.predicate import Predicate

if TYPE_CHECKING:
    from predylogic.register import RegistryManager
    from predylogic.rule_engine.base import RuleSetManifest
    from predylogic.trace import Trace
    from predylogic.typedefs import PredicateNodeType

T_contra = TypeVar("T_contra", contravariant=True)
T_cap = TypeVar("T_cap")


class PredicateHandle(Predicate[T_contra]):
    """
    Handle for predicates. Internally holds a predicate reference, enabling atomic updates during configuration refreshes.
    """

    def __init__(self, predicate: Predicate[T_contra]):
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
        ctx: T_contra,
        /,
        *,
        trace: Literal[True],
        short_circuit: bool = True,
        fail_skip: tuple[type[Exception], ...] | None = None,
    ) -> Trace: ...

    @overload
    def __call__(
        self,
        ctx: T_contra,
        /,
        *,
        trace: Literal[False] = False,
        short_circuit: Literal[True] = True,
        fail_skip: tuple[type[Exception], ...] | None = None,
    ) -> bool: ...

    def __call__(
        self,
        ctx: T_contra,
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

    def _update_predicate(self, predicate: Predicate[T_contra]):
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

    def update_manifests(self, *manifests: RuleSetManifest[T_cap]):
        """
        Updates the provided manifests to the current instance.

        This method is expected to take one or more manifests of type RuleSetManifest
        with a generic parameter T_cap.

        Rules bearing identical names within the same registry will be updated. Handles managed by the engine,
        where updated rules exist on the chain, will likewise be updated.

        Args:
            manifests: One or more instances of RuleSetManifest[T_cap] that are to
                be updated.
        """
        raise NotImplementedError

    @overload
    def get_predicate_handle(self, name: str, *, ctx_type: type[T_cap]) -> PredicateHandle[T_cap]: ...

    @overload
    def get_predicate_handle(self, name: str) -> Predicate[Any]: ...

    def get_predicate_handle(self, name: str, *, ctx_type: Any = Any) -> Predicate[Any]:
        """
        Retrieves the handle for the specified predicate.

        This method is used to obtain a handle for a predicate based on the provided
        name and context type.

        Args:
            name: The name of the predicate to retrieve.
            ctx_type: The type of context associated with the predicate.

        Returns:
            Predicate[ctx_type]: The handle for the specified predicate.
        """
        raise NotImplementedError
