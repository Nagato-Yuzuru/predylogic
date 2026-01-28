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
