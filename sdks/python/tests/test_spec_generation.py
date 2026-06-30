"""
Tests for the predylogic native spec generation.

Covers SchemaGenerator.generate_spec(), generate_workspace_spec(),
and the _serialize_type() helper for all supported type nodes.
"""

from __future__ import annotations

import json

from predylogic import Registry, RegistryManager, SchemaGenerator, generate_workspace_spec
from predylogic.rule_engine.schema import _serialize_type

from .conftest import OrderCtx, User

# ---------------------------------------------------------------------------
# _serialize_type
# ---------------------------------------------------------------------------


class TestSerializeType:
    def test_scalars(self):
        assert _serialize_type(int) == {"kind": "int"}
        assert _serialize_type(str) == {"kind": "str"}
        assert _serialize_type(float) == {"kind": "float"}
        assert _serialize_type(bool) == {"kind": "bool"}

    def test_none(self):
        assert _serialize_type(type(None)) == {"kind": "none"}

    def test_any_and_empty(self):
        import inspect
        import typing

        assert _serialize_type(typing.Any) == {"kind": "any"}
        assert _serialize_type(inspect.Parameter.empty) == {"kind": "any"}

    def test_list(self):
        assert _serialize_type(list[str]) == {"kind": "list", "element": {"kind": "str"}}
        assert _serialize_type(list[int]) == {"kind": "list", "element": {"kind": "int"}}

    def test_dict(self):
        assert _serialize_type(dict[str, int]) == {
            "kind": "dict",
            "key": {"kind": "str"},
            "value": {"kind": "int"},
        }

    def test_union_pipe_syntax(self):
        result = _serialize_type(int | str)
        assert result["kind"] == "union"
        assert {"kind": "int"} in result["variants"]
        assert {"kind": "str"} in result["variants"]

    def test_optional_is_union_with_none(self):
        result = _serialize_type(int | None)
        assert result["kind"] == "union"
        assert {"kind": "int"} in result["variants"]
        assert {"kind": "none"} in result["variants"]

    def test_nested_list(self):
        assert _serialize_type(list[list[str]]) == {
            "kind": "list",
            "element": {"kind": "list", "element": {"kind": "str"}},
        }

    def test_unknown_type_has_repr(self):
        import datetime

        result = _serialize_type(datetime.date)
        assert result["kind"] == "unknown"
        assert "repr" in result

    def test_unresolved_string_annotation(self):
        result = _serialize_type("SomeForwardRef")
        assert result == {"kind": "unknown", "repr": "SomeForwardRef"}


# ---------------------------------------------------------------------------
# SchemaGenerator.generate_spec()
# ---------------------------------------------------------------------------


class TestGenerateSpec:
    def test_empty_registry(self):
        reg = Registry[User]("empty")
        spec = SchemaGenerator(reg).generate_spec()
        assert spec == {"rules": {}}

    def test_rule_with_no_params(self, user_registry: Registry[User]):
        spec = SchemaGenerator(user_registry).generate_spec()
        assert "is_active" in spec["rules"]
        assert spec["rules"]["is_active"]["params"] == []

    def test_rule_desc_from_docstring(self, user_registry: Registry[User]):
        spec = SchemaGenerator(user_registry).generate_spec()
        assert spec["rules"]["is_active"]["desc"] == "Check if user is active."

    def test_int_param(self, user_registry: Registry[User]):
        params = SchemaGenerator(user_registry).generate_spec()["rules"]["is_adult"]["params"]
        (p,) = params
        assert p["name"] == "min_age"
        assert p["type"] == {"kind": "int"}
        assert p["param_kind"] == "positional_or_keyword"
        assert p["required"] is False  # has default=18

    def test_required_str_param(self, user_registry: Registry[User]):
        params = SchemaGenerator(user_registry).generate_spec()["rules"]["is_named"]["params"]
        (p,) = params
        assert p["name"] == "name"
        assert p["type"] == {"kind": "str"}
        assert p["required"] is True

    def test_float_param(self, order_registry: Registry[OrderCtx]):
        params = SchemaGenerator(order_registry).generate_spec()["rules"]["min_total"]["params"]
        (p,) = params
        assert p["type"] == {"kind": "float"}
        assert p["required"] is True

    def test_var_positional_param(self):
        reg = Registry[User]("vp_reg")

        @reg.rule_def()
        def has_tags(user: User, *tags: str) -> bool:
            """Check tags."""
            return True

        params = SchemaGenerator(reg).generate_spec()["rules"]["has_tags"]["params"]
        (p,) = params
        assert p["name"] == "tags"
        assert p["type"] == {"kind": "str"}
        assert p["param_kind"] == "var_positional"
        assert p["required"] is False

    def test_var_keyword_param(self):
        reg = Registry[User]("vk_reg")

        @reg.rule_def()
        def with_meta(user: User, **meta: int) -> bool:
            """Check meta."""
            return True

        params = SchemaGenerator(reg).generate_spec()["rules"]["with_meta"]["params"]
        (p,) = params
        assert p["name"] == "meta"
        assert p["type"] == {"kind": "int"}
        assert p["param_kind"] == "var_keyword"
        assert p["required"] is False

    def test_keyword_only_param(self):
        reg = Registry[User]("ko_reg")

        @reg.rule_def()
        def named_only(user: User, *, threshold: int) -> bool:
            """Keyword only."""
            return True

        params = SchemaGenerator(reg).generate_spec()["rules"]["named_only"]["params"]
        (p,) = params
        assert p["param_kind"] == "keyword_only"
        assert p["required"] is True

    def test_optional_param(self):
        reg = Registry[User]("opt_reg")

        @reg.rule_def()
        def maybe_named(user: User, name: str | None = None) -> bool:
            """Optional name check."""
            return True

        params = SchemaGenerator(reg).generate_spec()["rules"]["maybe_named"]["params"]
        (p,) = params
        assert p["type"]["kind"] == "union"
        assert p["required"] is False

    def test_list_param(self):
        reg = Registry[User]("list_reg")

        @reg.rule_def()
        def in_groups(user: User, groups: list[str]) -> bool:
            """Group membership."""
            return True

        params = SchemaGenerator(reg).generate_spec()["rules"]["in_groups"]["params"]
        (p,) = params
        assert p["type"] == {"kind": "list", "element": {"kind": "str"}}
        assert p["required"] is True

    def test_no_desc_when_no_docstring(self):
        reg = Registry[User]("nodoc_reg")

        @reg.rule_def()
        def no_doc(user: User) -> bool:
            return True

        spec = SchemaGenerator(reg).generate_spec()
        assert "desc" not in spec["rules"]["no_doc"]


# ---------------------------------------------------------------------------
# generate_workspace_spec()
# ---------------------------------------------------------------------------


class TestGenerateWorkspaceSpec:
    def test_returns_valid_json(self, registry_manager: RegistryManager, user_registry: Registry[User]):
        result = generate_workspace_spec(registry_manager)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_version_field(self, registry_manager: RegistryManager, user_registry: Registry[User]):
        parsed = json.loads(generate_workspace_spec(registry_manager))
        assert parsed["version"] == "1"

    def test_contains_all_registries(
        self,
        registry_manager: RegistryManager,
        user_registry: Registry[User],
        order_registry: Registry[OrderCtx],
    ):
        parsed = json.loads(generate_workspace_spec(registry_manager))
        assert "user_registry" in parsed["registries"]
        assert "order_registry" in parsed["registries"]

    def test_registry_rules_present(
        self,
        registry_manager: RegistryManager,
        user_registry: Registry[User],
    ):
        parsed = json.loads(generate_workspace_spec(registry_manager))
        rules = parsed["registries"]["user_registry"]["rules"]
        assert "is_adult" in rules
        assert "is_active" in rules
        assert "is_named" in rules

    def test_empty_manager(self):
        manager = RegistryManager()
        parsed = json.loads(generate_workspace_spec(manager))
        assert parsed == {"version": "1", "registries": {}}
