from __future__ import annotations

import inspect
from collections.abc import Callable, Iterator, Mapping
from functools import wraps
from threading import RLock
from typing import TYPE_CHECKING, Generic, ParamSpec, Protocol, TypeVar, runtime_checkable

from predylogic.predicate import Predicate, predicate
from predylogic.register.errs import RegistryNameConflictError, RuleDefConflictError, RuleDefNotNamedError

if TYPE_CHECKING:
    from predylogic.types import RuleDef

T_contra = TypeVar("T_contra", contravariant=True)
P = ParamSpec("P")


@runtime_checkable
class PredicateProducer(Protocol[T_contra, P]):
    """
    Callable that produces a predicate.
    """

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Predicate[T_contra]:  # noqa: D102
        ...


class RuleDecorator(Protocol[T_contra]):  # noqa: D101
    def __call__(self, fn: RuleDef[T_contra, P], /) -> PredicateProducer[T_contra, P]: ...  # noqa: D102


class RegistryManager:
    """
    Manage registries.

    # TODO: shall be responsible for a portion of the JSON Schema export functionality.
    """

    def __init__(self):
        self.__registers_instance: dict[str, Registry] = {}
        self.__register_lock = RLock()

    def add_register(self, name: str, register: Registry):
        """
        Try to add a register.

        Args:
            name: The name of the register.
            register: The register to add.

        Raises:
            RegisterNameConflictError: If the name is already in use.
        """
        with self.__register_lock:
            if name in self.__registers_instance:
                raise RegistryNameConflictError(name, self.__registers_instance[name])

            self.__registers_instance[name] = register

    def get_register(self, name: str) -> Registry | None:
        """
        Get a register by name.
        """
        return self.__registers_instance.get(name)


class Registry(Generic[T_contra], Mapping[str, PredicateProducer[T_contra, ...]]):
    """
    Registry a predicate producer with a name.
    """

    def __init__(self, name: str):
        self.name = name
        self.__predicates: dict[str, PredicateProducer[T_contra, ...]] = {}
        self.__lock = RLock()

    def __getitem__(self, key: str) -> PredicateProducer[T_contra, ...]:
        return self.__predicates[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.__predicates)

    def __len__(self) -> int:
        return len(self.__predicates)

    def _register_predicate_producer(self, name: str, predicate_producer: PredicateProducer[T_contra, ...]) -> None:
        """
        Raises:
            RuleDefConflictError: If the name is already in use.
        """
        with self.__lock:
            if name in self.__predicates:
                raise RuleDefConflictError(self.name, name, self.__predicates)
            self.__predicates[name] = predicate_producer

    def register(self, rule_def: RuleDef[T_contra, P], alias: str | None) -> PredicateProducer[T_contra, P]:
        """
        Register a RuleDef with an optional alias. Maintain the original function unchanged.

        Args:
            rule_def: The rule definition to register.
            alias: An optional string representing the alias for the rule definition.
                When registering an anonymous function, this parameter must be provided.

        Returns:
            PredicateProducer[P, T_contra]: A new predicate producer instance.

        Raises:
            RegistryNameConflictError: If the name is already in use.
            RuleDefNotNamedError: If a rule def is not named.

        Examples:
            Register a named rule definition:

            ```python
            from typing import TypedDict

            from predylogic.register import Registry


            class UserCtx(TypedDict):
                age: int

            def is_user_over_age(user: User, age: int) -> bool:
                return user.age >= age

            registry = Registry("my_registry")

            # The original function remains unchanged.
            is_user_over_age_rule = registry.register(is_user_over_age)
            ```

        """

        return RuleDefConverter(self, alias)(rule_def)

    def rule_def(self, alias: str | None = None) -> RuleDefConverter[T_contra]:
        """
        Converts the given alias into a RuleDefConverter instance.

        This method is used to create a RuleDefConverter object which can perform
        operations related to defining rules. The optional alias parameter can be
        supplied to distinguish or identify the rule definition.

        Args:
            alias (str | None): An optional string representing the alias for the rule
                definition.

        Returns:
            RuleDefConverter[T_contra]: A new instance of RuleDefConverter, configured
            with the provided alias.

        Raises:
            RegistryNameConflictError: If the name is already in use.
            RuleDefNotNamedError: If a rule def is not named.

        Examples:
            ```python
            from typing import TypedDict

            from predylogic import Registry, Predicate


            class UserCtx(TypedDict):
                age: int


            registry = Registry("my_registry")

            @registry.rule_def()
            def is_user_over_age(user: User, age: int) -> bool:
                return user.age >= age


            is_legal = is_user_over_age(age=18)

            assert isinstance(is_legal, Predicate)
            assert is_user_over_age(18)
            ```

        """

        return RuleDefConverter(self, alias=alias)


class RuleDefConverter(Generic[T_contra], RuleDecorator[T_contra]):
    """
    Convert the [predylogic.types.RuleDef][] function to one that returns a Predicate[T]
    This will modify the signature of RuleDef.

    Must be used on named functions

    Args:
        registry: The registry to which the rule will be added.
        alias: Prioritize using as the name for RuleDef.
    """

    # XXX: Closure decorator functions are not directly defined due to type inference issues
    #  with IDEs and static analysis tools. Using decorator classes makes static inference more straightforward.
    # Even so, PyCharm still fails to perform correct static inference. Reveal_type and ty are relevant here.
    # https://youtrack.jetbrains.com/issue/PY-87133/Incorrect-return-type-inference-for-class-based-decorator-using-ParamSpec-and-Concatenate

    def __init__(self, registry: Registry[T_contra] | None = None, alias: str | None = None):
        self.registry = registry
        self.alias = alias

    def __call__(self, fn: RuleDef[T_contra, P]) -> PredicateProducer[T_contra, P]:
        """
        Convert the RuleDef function to one that returns a Predicate[T_contra], and add the rule to the registry.
        This will modify the signature of RuleDef.

        Args:
            fn: Rule define func. Must be a named function or give an alias.

        Raises:
            RuleDefNotNamedError: If a rule def is not named.
            RegistryNameConflictError: If the name is already in use.

        """

        if self._needs_alias(fn) and self.alias is None:
            raise RuleDefNotNamedError()

        rule_def_name = self.alias or fn.__name__

        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Predicate[T_contra]:
            return predicate(
                lambda x: fn(x, *args, **kwargs),
                name=rule_def_name,
                desc=fn.__doc__ or fn.__name__ or None,
            )

        sig = inspect.signature(fn)

        new_params = list(sig.parameters.values())[1:]

        wrapper.__annotations__ = {p.name: p.annotation for p in new_params}
        wrapper.__annotations__["return"] = Predicate

        wrapper.__signature__ = inspect.Signature(  # ty:ignore[unresolved-attribute]
            parameters=new_params,
            return_annotation=Predicate,
        )

        if self.registry is not None:
            self.registry._register_predicate_producer(rule_def_name, wrapper)

        return wrapper

    @staticmethod
    def _needs_alias(fn: Callable) -> bool:
        name = getattr(fn, "__name__", None)
        return name is None or name in {"", "<lambda>"} or not (inspect.isfunction(fn) or inspect.ismethod(fn))
