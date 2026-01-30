from abc import ABC, abstractmethod
from textwrap import dedent

from predylogic import Predicate, predicate

from .closure_predicate import Predicate as ClosurePredicate


def true_fn(_):
    return True


def false_fn(_):
    return False


def make_naive_chain(depth: int):
    func_name = f"naive_chain_{depth}"
    calls = ["true_fn(x)"] * depth
    body = " and ".join(calls)
    code = dedent(
        f"""
        def {func_name}(x):
            return {body}
        """,
    )
    local_scope = {"true_fn": true_fn}
    exec(code, local_scope)  # noqa: S102
    return local_scope[func_name]


class LogicFactory(ABC):
    @abstractmethod
    def make_chain(self, depth: int): ...


class ClosureFactory(LogicFactory):
    def make_chain(self, depth: int):
        p = ClosurePredicate(true_fn)
        other = ClosurePredicate(true_fn)
        for _ in range(depth - 1):
            p &= other
        return p


class CurrentFactory(LogicFactory):
    def make_chain(self, depth: int):
        p = predicate(fn=true_fn, name="test fn")
        p = Predicate.all([p] * (depth - 1))
        return p
