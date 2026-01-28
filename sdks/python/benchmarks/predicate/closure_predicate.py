""" """

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Generic, TypeVar

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


T_contra = TypeVar("T_contra", contravariant=True)

PredicateFn = Callable[[T_contra], bool]


class Predicate(Generic[T_contra]):
    """
    The Predicate is a lazy-evaluated function.

    It permits logical combinations over contexts of the same type.
    A predicate is a callable object that accepts objects of type T.
    It executes all combined logic and returns a bool when called.

    Use the &, |, and ~ symbols for logical operations.

    Args:
        fn:
            A function that takes an object of type T and returns a boolean.
    """

    def __init__(self, fn: PredicateFn[T_contra]):
        self.fn = fn

    def __call__(self, obj: T_contra) -> bool:
        """
        Execution Logic.
        """

        return self.fn(obj)

    def __and__(self, other: Predicate[T_contra]) -> Self:
        if not isinstance(other, Predicate):
            return NotImplemented
        return self.__class__(lambda x: self(x) and other(x))

    def __or__(self, other: Predicate[T_contra]) -> Self:
        if not isinstance(other, Predicate):
            return NotImplemented
        return self.__class__(lambda x: self(x) or other(x))

    def __invert__(self) -> Self:
        return self.__class__(lambda x: not self(x))
