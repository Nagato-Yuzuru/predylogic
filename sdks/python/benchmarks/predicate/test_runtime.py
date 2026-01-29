import pytest

from .utils import make_naive_chain


@pytest.mark.parametrize("depth", [5, 20, 100])
def test_exec_naive_python(benchmark, depth):
    benchmark.group = f"Runtime: Depth {depth}"
    func = make_naive_chain(depth)
    benchmark(func, "obj")


@pytest.mark.parametrize("depth", [5, 20, 100])
def test_exec_engine(benchmark, factory, depth):
    benchmark.group = f"Runtime: Depth {depth}"
    rule = factory.make_chain(depth)

    benchmark(rule, "obj")
