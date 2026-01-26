from __future__ import annotations

import inspect
from collections.abc import Callable, Iterator, Mapping
from functools import wraps
from threading import RLock
from typing import Any, Concatenate, cast

from predylogic.predicate import Predicate
from predylogic.register.errs import RegistryNameConflictError, RuleDefConflictError
from predylogic.types import RuleDef

type PredicateProducer[T, **P] = Callable[P, Predicate[T]]
type RuleDecorator[T, **P] = Callable[[RuleDef[T, P]], PredicateProducer[T, P]]


class RegistryManager:
    """
    Manage registries.
    """

    def __init__(self):
        self.__registers_instance: dict[str, Registry] = {}
        self.__register_lock = RLock()

    def try_add_register(self, name: str, register: Registry):
        """
        Try to add a register.

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


GlobalRegistryManager = RegistryManager()


class Registry[T](Mapping[str, PredicateProducer[T, Any]]):
    """
    Registry a predicate producer with a name.
    """

    def __init__(self, name: str, *, _manager: RegistryManager | None = None):
        self.name = name
        self.__predicates: dict[str, PredicateProducer[T, Any]] = {}
        self.__lock = RLock()

        manager = _manager or GlobalRegistryManager
        manager.try_add_register(self.name, self)

    def __getitem__(self, key: str) -> PredicateProducer[T, Any]:
        return self.__predicates[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.__predicates)

    def __len__(self) -> int:
        return len(self.__predicates)

    def register[**P](self, name: str, predicate_producer: PredicateProducer[T, P]):
        """
        Register a predicate producer with a name.

        Raises:
            RuleDefConflictError: If the name is already in use.
        """
        with self.__lock:
            if name in self.__predicates:
                raise RuleDefConflictError(self.name, name, self.__predicates)
            self.__predicates[name] = predicate_producer


class rule_def[T]:  # noqa: N801
    """
    Convert the [predylogic.types.RuleDef][] function to one that returns a Predicate[T], and add the rule to the registry.
    This will modify the signature of RuleDef.

    Must be used on named functions

    Args:
        *registries: Registers to add the rule to.

    Examples:
        ```python
        from typing import TypedDict


        class UserCtx(TypedDict):
            age: int


        register = Register[UserCtx]("register")

        @rule_def(register)
        def is_over_age_threshold(user_ctx: UserCtx, threshold) -> bool:
            return user_ctx.age >= threshold

        legal = is_over_age_threshold(18)
        illegal = ~legal

        assert legal({"age": 18})
        assert illegal({"age": 17})
        ```

    """

    # XXX: Closure decorator functions are not directly defined due to type inference issues
    #  with IDEs and static analysis tools. Using decorator classes makes static inference more straightforward.
    # Even so, PyCharm still fails to perform correct static inference. Reveal_type and ty are relevant here.
    # https://youtrack.jetbrains.com/issue/PY-87133/Incorrect-return-type-inference-for-class-based-decorator-using-ParamSpec-and-Concatenate

    def __init__(self, *registries: Registry[T]):
        self.__registries = registries

    def __call__[**P](self, fn: Callable[Concatenate[T, P], bool]) -> PredicateProducer[T, P]:
        """
        Convert the RuleDef function to one that returns a Predicate[T], and add the rule to the registry.
        This will modify the signature of RuleDef.

        Args:
            fn (RuleDef[T,P]): Rule define func. Must be a named function.

        Raises:
            RuleDefConflictError: If a rule with the same fn name has already been registered.
        """
        fn = cast("RuleDef[T, P]", fn)

        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Predicate[T]:
            return Predicate(lambda x: fn(x, *args, **kwargs))

        sig = inspect.signature(fn)

        new_params = list(sig.parameters.values())[1:]

        wrapper.__annotations__ = {p.name: p.annotation for p in new_params}
        wrapper.__annotations__["return"] = Predicate

        wrapper.__signature__ = inspect.Signature(parameters=new_params, return_annotation=Predicate)  # ty:ignore[unresolved-attribute]

        for register in self.__registries:
            register.register(fn.__name__, wrapper)

        return wrapper
