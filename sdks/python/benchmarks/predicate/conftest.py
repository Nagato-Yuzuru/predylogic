import gc
import sys

if sys.version_info < (3, 11):
    from typing_extensions import assert_never
else:
    from typing import assert_never

import pytest

from .utils import ClosureFactory, CurrentFactory


@pytest.fixture(params=["closure", "current"], ids=["Closure", "Current"])
def factory(request):
    match request.param:
        case "closure":
            return ClosureFactory()
        case "current":
            return CurrentFactory()
        case _:
            assert_never(request.param)  # ty:ignore[type-assertion-failure]


@pytest.fixture(scope="function", autouse=True)
def clean_heap_isolation():
    gc.collect()
    yield
