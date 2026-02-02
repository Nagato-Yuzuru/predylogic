import json
from dataclasses import dataclass

from pydantic import BaseModel

from predylogic import Registry, SchemaGenerator

test_registry = Registry("test_registry")


@dataclass
class UserCtx:
    age: int
    status: str


@test_registry.rule_def()
def is_status(user: UserCtx, status: str) -> bool:
    return user.status == status


@test_registry.rule_def()
def is_over_age_threshold(user: UserCtx, threshold: int) -> bool:
    """
    Determine whether it is greater than or equal to the threshold.
    """
    return user.age >= threshold


def test_schema():
    schema = SchemaGenerator(test_registry).generate()
    json_schema = schema.model_json_schema()
    raw = json.dumps(json_schema)
    assert isinstance(schema, BaseModel)
