import pytest


@pytest.mark.parametrize("depth", [100, 1000])
def test_construction_cost(benchmark, factory, depth):
    benchmark.group = f"Build Cost: Depth {depth}"

    benchmark(factory.make_chain, depth)
