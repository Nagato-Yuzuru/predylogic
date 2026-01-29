import sys

import pytest


def test_recursion_limit_probe(factory):
    limit = sys.getrecursionlimit()
    depth = limit + 500

    rule = factory.make_chain(depth)
    factory_name = type(factory).__name__

    # The current mode remains closed.
    if factory_name == "ClosureFactory":
        with pytest.raises(RecursionError):
            rule("obj")
    else:
        try:
            rule("obj")
        except RecursionError:
            pytest.fail(f"RecursionError raised for {factory_name}")
