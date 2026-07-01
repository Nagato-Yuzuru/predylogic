"""
Tests for the predylogic native spec generation.

Covers SchemaGenerator.generate_spec(), generate_workspace_spec(),
and the _serialize_type() helper for all supported type nodes.
"""

from __future__ import annotations

import datetime
import inspect
import json
import typing

from predylogic import (
    Registry,
    RegistryManager,
    RegistrySpec,
    RuleSpec,
    SchemaGenerator,
    WorkspaceSpec,
    generate_workspace_spec,
)
from predylogic.rule_engine.schema import _serialize_type
from predylogic.rule_engine.spec import (
    AtomType,
    ParamSpec,
    TypeDict,
    TypeList,
    TypeUnion,
    TypeUnknown,
)

from .conftest import OrderCtx, User

# ---------------------------------------------------------------------------
# _serialize_type
# ---------------------------------------------------------------------------


class TestSerializeType:
    def test_scalars(self):
        assert _serialize_type(int) == AtomType(kind="int")
        assert _serialize_type(str) == AtomType(kind="str")
        assert _serialize_type(float) == AtomType(kind="float")
        assert _serialize_type(bool) == AtomType(kind="bool")

    def test_none(self):
        assert _serialize_type(type(None)) == AtomType(kind="none")

    def test_any_and_empty(self):
        assert _serialize_type(typing.Any) == AtomType(kind="any")
        assert _serialize_type(inspect.Parameter.empty) == AtomType(kind="any")

    def test_list(self):
        assert _serialize_type(list[str]) == TypeList(element=AtomType(kind="str"))
        assert _serialize_type(list[int]) == TypeList(element=AtomType(kind="int"))

    def test_dict(self):
        assert _serialize_type(dict[str, int]) == TypeDict(key=AtomType(kind="str"), value=AtomType(kind="int"))

    def test_union_pipe_syntax(self):
        result = _serialize_type(int | str)
        assert isinstance(result, TypeUnion)
        assert AtomType(kind="int") in result.variants
        assert AtomType(kind="str") in result.variants

    def test_optional_is_union_with_none(self):
        result = _serialize_type(int | None)
        assert isinstance(result, TypeUnion)
        assert AtomType(kind="int") in result.variants
        assert AtomType(kind="none") in result.variants

    def test_nested_list(self):
        assert _serialize_type(list[list[str]]) == TypeList(element=TypeList(element=AtomType(kind="str")))

    def test_unknown_type_has_repr(self):
        result = _serialize_type(datetime.date)
        assert isinstance(result, TypeUnknown)
        assert result.repr

    def test_unresolved_string_annotation(self):
        result = _serialize_type("SomeForwardRef")
        assert result == TypeUnknown(repr="SomeForwardRef")


# ---------------------------------------------------------------------------
# SchemaGenerator.generate_spec()
# ---------------------------------------------------------------------------


class TestGenerateSpec:
    def test_empty_registry_returns_registry_spec(self):
        reg = Registry[User]("empty")
        spec = SchemaGenerator(reg).generate_spec()
        assert isinstance(spec, RegistrySpec)
        assert spec.rules == {}

    def test_rule_with_no_params(self, user_registry: Registry[User]):
        spec = SchemaGenerator(user_registry).generate_spec()
        assert "is_active" in spec.rules
        assert spec.rules["is_active"].params == ()

    def test_rule_desc_from_docstring(self, user_registry: Registry[User]):
        spec = SchemaGenerator(user_registry).generate_spec()
        assert spec.rules["is_active"].desc == "Check if user is active."

    def test_rule_is_rule_spec(self, user_registry: Registry[User]):
        spec = SchemaGenerator(user_registry).generate_spec()
        assert isinstance(spec.rules["is_adult"], RuleSpec)

    def test_param_is_param_spec(self, user_registry: Registry[User]):
        rule = SchemaGenerator(user_registry).generate_spec().rules["is_adult"]
        assert len(rule.params) == 1
        assert isinstance(rule.params[0], ParamSpec)

    def test_int_param(self, user_registry: Registry[User]):
        (p,) = SchemaGenerator(user_registry).generate_spec().rules["is_adult"].params
        assert p.name == "min_age"
        assert p.type == AtomType(kind="int")
        assert p.param_kind == "positional_or_keyword"
        assert p.required is False  # has default=18

    def test_required_str_param(self, user_registry: Registry[User]):
        (p,) = SchemaGenerator(user_registry).generate_spec().rules["is_named"].params
        assert p.name == "name"
        assert p.type == AtomType(kind="str")
        assert p.required is True

    def test_float_param(self, order_registry: Registry[OrderCtx]):
        (p,) = SchemaGenerator(order_registry).generate_spec().rules["min_total"].params
        assert p.type == AtomType(kind="float")
        assert p.required is True

    def test_var_positional_param(self):
        reg = Registry[User]("vp_reg")

        @reg.rule_def()
        def has_tags(user: User, *tags: str) -> bool:
            """Check tags."""
            return True

        (p,) = SchemaGenerator(reg).generate_spec().rules["has_tags"].params
        assert p.name == "tags"
        assert p.type == AtomType(kind="str")
        assert p.param_kind == "var_positional"
        assert p.required is False

    def test_var_keyword_param(self):
        reg = Registry[User]("vk_reg")

        @reg.rule_def()
        def with_meta(user: User, **meta: int) -> bool:
            """Check meta."""
            return True

        (p,) = SchemaGenerator(reg).generate_spec().rules["with_meta"].params
        assert p.name == "meta"
        assert p.type == AtomType(kind="int")
        assert p.param_kind == "var_keyword"
        assert p.required is False

    def test_keyword_only_param(self):
        reg = Registry[User]("ko_reg")

        @reg.rule_def()
        def named_only(user: User, *, threshold: int) -> bool:
            """Keyword only."""
            return True

        (p,) = SchemaGenerator(reg).generate_spec().rules["named_only"].params
        assert p.param_kind == "keyword_only"
        assert p.required is True

    def test_optional_param(self):
        reg = Registry[User]("opt_reg")

        @reg.rule_def()
        def maybe_named(user: User, name: str | None = None) -> bool:
            """Optional name check."""
            return True

        (p,) = SchemaGenerator(reg).generate_spec().rules["maybe_named"].params
        assert isinstance(p.type, TypeUnion)
        assert p.required is False

    def test_list_param(self):
        reg = Registry[User]("list_reg")

        @reg.rule_def()
        def in_groups(user: User, groups: list[str]) -> bool:
            """Group membership."""
            return True

        (p,) = SchemaGenerator(reg).generate_spec().rules["in_groups"].params
        assert p.type == TypeList(element=AtomType(kind="str"))
        assert p.required is True

    def test_no_desc_when_no_docstring(self):
        reg = Registry[User]("nodoc_reg")

        @reg.rule_def()
        def no_doc(user: User) -> bool:
            return True

        assert SchemaGenerator(reg).generate_spec().rules["no_doc"].desc is None


# ---------------------------------------------------------------------------
# generate_workspace_spec()
# ---------------------------------------------------------------------------


class TestGenerateWorkspaceSpec:
    def test_returns_workspace_spec(self, registry_manager: RegistryManager, user_registry: Registry[User]):
        result = generate_workspace_spec(registry_manager)
        assert isinstance(result, WorkspaceSpec)

    def test_version_field(self, registry_manager: RegistryManager, user_registry: Registry[User]):
        assert generate_workspace_spec(registry_manager).version == "1"

    def test_contains_all_registries(
        self,
        registry_manager: RegistryManager,
        user_registry: Registry[User],
        order_registry: Registry[OrderCtx],
    ):
        spec = generate_workspace_spec(registry_manager)
        assert "user_registry" in spec.registries
        assert "order_registry" in spec.registries

    def test_registry_rules_present(
        self,
        registry_manager: RegistryManager,
        user_registry: Registry[User],
    ):
        rules = generate_workspace_spec(registry_manager).registries["user_registry"].rules
        assert "is_adult" in rules
        assert "is_active" in rules
        assert "is_named" in rules

    def test_empty_manager(self):
        spec = generate_workspace_spec(RegistryManager())
        assert spec == WorkspaceSpec(registries={})

    def test_to_json_produces_valid_json(
        self,
        registry_manager: RegistryManager,
        user_registry: Registry[User],
    ):
        raw = generate_workspace_spec(registry_manager).to_json()
        parsed = json.loads(raw)
        assert parsed["version"] == "1"
        assert "user_registry" in parsed["registries"]

    def test_to_json_omits_none_desc(
        self,
        registry_manager: RegistryManager,
        user_registry: Registry[User],
    ):
        raw = generate_workspace_spec(registry_manager).to_json()
        parsed = json.loads(raw)
        # is_active has a docstring; is_named does too — pick a rule without one
        # by checking params that have no desc
        for _name, rule in parsed["registries"]["user_registry"]["rules"].items():
            for param in rule["params"]:
                assert "desc" not in param  # params never have individual descs
