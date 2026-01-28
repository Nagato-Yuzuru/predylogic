import pytest

from .utils import make_naive_chain


@pytest.mark.parametrize("depth", [100, 1000])
def test_construction_cost(benchmark, factory, depth):
    benchmark.group = f"Build Cost: Depth {depth}"

    benchmark(factory.make_chain, depth)


@pytest.mark.parametrize("depth", [100, 1000])
def test_naive_construction_cost(benchmark, depth):
    benchmark.group = f"Build Cost: Depth {depth}"

    func = make_naive_chain(depth)
    benchmark(func, depth)
