"""
Test suite for the pdyl DSL compiler - .pdyl source to RuleSetManifest.

Tests cover:
- Leaf calls: keyword, positional, defaults, star-spread, var-kwargs
- Composition shape: flat N-ary and/or, not, precedence, parentheses
- Bindings: value substitution, private inlining, forward refs, exports
- Errors: whitelist rejections, unknown names, binding/type errors, cycles
- End to end: compile -> engine -> evaluate -> trace, hot swap
"""

from __future__ import annotations

import traceback

import pytest
from predylogic import Registry, RuleEngine, compile_pdyl
from predylogic.dsl import PdylError
from predylogic.rule_engine.base import AndNode, LeafNode, NotNode, OrNode, RuleSetManifest

from .conftest import User


@pytest.fixture
def geo_registry(registry_manager) -> Registry[User]:
    """Registry exercising var-positional, var-keyword, and container params."""
    registry = Registry[User]("geo_registry")

    @registry.rule_def()
    def name_in(user: User, *names: str) -> bool:
        """Check membership of the user's name in a spread of names."""
        return user.name in names

    @registry.rule_def()
    def has_tags(user: User, **tags: str) -> bool:
        """Placeholder atom exercising var-keyword params."""
        return bool(tags)

    @registry.rule_def()
    def scored(user: User, weights: dict[str, float], floors: list[int] | None = None) -> bool:
        """Placeholder atom exercising dict / list params."""
        return True

    registry_manager.add_register(registry)
    return registry


def root(manifest, name):
    return manifest.rules[name].root


def kids(node):
    return [child.root for child in node.rules]


class TestLeaves:
    def test_keyword_call(self, user_registry):
        manifest = compile_pdyl("adult = is_adult(min_age=21)", user_registry)
        assert isinstance(manifest, RuleSetManifest)
        assert manifest.registry == "user_registry"
        leaf = root(manifest, "adult")
        assert isinstance(leaf, LeafNode)
        assert leaf.rule.rule_def_name == "is_adult"
        assert leaf.rule.params.min_age == 21

    def test_positional_call(self, user_registry):
        manifest = compile_pdyl('named = is_named("Alice")', user_registry)
        assert root(manifest, "named").rule.params.name == "Alice"

    def test_default_parameter_applies(self, user_registry):
        manifest = compile_pdyl("adult = is_adult()", user_registry)
        assert root(manifest, "adult").rule.params.min_age == 18

    def test_star_spread_into_var_positional(self, geo_registry):
        src = 'NAMES = ["Alice", "Bob"]\nrisky = name_in(*NAMES)\nboth = name_in("Zoe", *NAMES)'
        manifest = compile_pdyl(src, geo_registry)
        assert list(root(manifest, "risky").rule.params.names) == ["Alice", "Bob"]
        assert list(root(manifest, "both").rule.params.names) == ["Zoe", "Alice", "Bob"]

    def test_tuple_binding_spreads_like_list(self, geo_registry):
        src = 'NAMES = ("Alice", "Bob")\nrisky = name_in(*NAMES)'
        manifest = compile_pdyl(src, geo_registry)
        assert list(root(manifest, "risky").rule.params.names) == ["Alice", "Bob"]

    def test_natural_var_keyword_spelling(self, geo_registry):
        manifest = compile_pdyl('tagged = has_tags(region="jp", tier="gold")', geo_registry)
        assert root(manifest, "tagged").rule.params.tags == {"region": "jp", "tier": "gold"}

    def test_container_and_negative_values(self, geo_registry):
        src = 'w = scored(weights={"a": 1.5, "b": -2}, floors=[1, 2])'
        manifest = compile_pdyl(src, geo_registry)
        params = root(manifest, "w").rule.params
        assert params.weights == {"a": 1.5, "b": -2}
        assert list(params.floors) == [1, 2]


class TestComposition:
    def test_chain_is_flat_nary(self, user_registry):
        src = 'c = is_adult(min_age=18) & is_active() & ~is_named("Bob")'
        node = root(compile_pdyl(src, user_registry), "c")
        assert isinstance(node, AndNode)
        children = kids(node)
        assert len(children) == 3
        assert isinstance(children[2], NotNode)

    def test_parenthesized_same_op_flattens(self, user_registry):
        src = 'c = is_active() & (is_adult() & is_named("A"))'
        node = root(compile_pdyl(src, user_registry), "c")
        assert isinstance(node, AndNode)
        assert len(kids(node)) == 3

    def test_precedence_not_over_and_over_or(self, user_registry):
        src = 'c = ~is_active() | is_adult() & is_named("A")'
        node = root(compile_pdyl(src, user_registry), "c")
        assert isinstance(node, OrNode)
        children = kids(node)
        assert isinstance(children[0], NotNode)
        assert isinstance(children[1], AndNode)


class TestBindings:
    def test_value_binding_substituted_and_not_exported(self, user_registry):
        src = "LIMIT = 21\nadult = is_adult(min_age=LIMIT)"
        manifest = compile_pdyl(src, user_registry)
        assert set(manifest.rules) == {"adult"}
        assert root(manifest, "adult").rule.params.min_age == 21

    def test_private_predicate_inlined_and_not_exported(self, user_registry):
        src = "_grown = is_adult(min_age=18)\ngate = _grown & is_active()"
        manifest = compile_pdyl(src, user_registry)
        assert set(manifest.rules) == {"gate"}
        children = kids(root(manifest, "gate"))
        assert isinstance(children[0], LeafNode)
        assert children[0].rule.rule_def_name == "is_adult"

    def test_public_reference_inlined_and_both_exported(self, user_registry):
        src = "grown = is_adult()\ngate = grown & is_active()"
        manifest = compile_pdyl(src, user_registry)
        assert set(manifest.rules) == {"grown", "gate"}
        assert '"node_type":"ref"' not in manifest.model_dump_json()

    def test_forward_reference(self, user_registry):
        src = "gate = grown & is_active()\ngrown = is_adult()"
        manifest = compile_pdyl(src, user_registry)
        assert set(manifest.rules) == {"grown", "gate"}

    def test_predicate_alias_resolves_transitively(self, user_registry):
        src = "grown = is_adult()\nalias = grown\ngate = alias & is_active()"
        manifest = compile_pdyl(src, user_registry)
        assert set(manifest.rules) == {"grown", "alias", "gate"}
        assert isinstance(root(manifest, "alias"), LeafNode)

    def test_value_alias_substitutes_transitively(self, user_registry):
        src = "BASE = 18\nLIMIT = BASE\nadult = is_adult(min_age=LIMIT)"
        manifest = compile_pdyl(src, user_registry)
        assert set(manifest.rules) == {"adult"}
        assert root(manifest, "adult").rule.params.min_age == 18

    def test_docstring_and_comments_allowed(self, user_registry):
        src = '"""Fraud rules."""\n\n# threshold tuned 2026-08\nadult = is_adult(min_age=21)  # inline comment\n'
        manifest = compile_pdyl(src, user_registry)
        assert set(manifest.rules) == {"adult"}

    def test_empty_source(self, user_registry):
        assert compile_pdyl("", user_registry).rules == {}

    def test_unused_value_binding_still_checked(self, user_registry):
        with pytest.raises(PdylError, match="string literals"):
            compile_pdyl("BAD = {1: 2}", user_registry)

    def test_unused_private_predicate_still_checked(self, user_registry):
        with pytest.raises(PdylError, match="unknown rule_def"):
            compile_pdyl("_x = frobnicate()", user_registry)


class TestErrors:
    def test_unknown_rule_def_did_you_mean(self, user_registry):
        with pytest.raises(PdylError, match="did you mean 'is_adult'"):
            compile_pdyl("x = is_adlt(min_age=18)", user_registry)

    def test_unknown_rule_def_lists_available(self, user_registry):
        with pytest.raises(PdylError, match="available:"):
            compile_pdyl("x = frobnicate()", user_registry)

    def test_bare_rule_def_name_hints_call(self, user_registry):
        with pytest.raises(PdylError, match=r"must be called: is_active\(\.\.\.\)"):
            compile_pdyl("x = is_adult() & is_active", user_registry)

    def test_undefined_name(self, user_registry):
        with pytest.raises(PdylError, match="undefined name 'ghost'"):
            compile_pdyl("x = ghost & is_active()", user_registry)

    @pytest.mark.parametrize(
        ("src", "fragment"),
        [
            ("x = is_active() and is_adult()", "use '&'"),
            ("x = is_active() or is_adult()", "'or' is not pdyl"),
            ("x = not is_active()", "use '~'"),
            ("x = is_adult() > is_active()", "comparisons are not pdyl"),
            ("x = lambda u: True", "Lambda is not a pdyl value"),
            ('x = is_named(f"a{1}")', "JoinedStr is not a pdyl value"),
            ("x = is_adult(min_age={1, 2})", "Set is not a pdyl value"),
            ("import os", "Import is not pdyl"),
            ("if True:\n    x = 1", "If is not pdyl"),
            ("def f():\n    pass", "FunctionDef is not pdyl"),
            ("x, y = 1, 2", "single-name assignment"),
            ("x = y = is_active()", "single-name assignment"),
            ("x = is_adult(min_age=is_active())", "pure data"),
            ("x = is_named({**{}})", "string literals"),
            ('x = has_tags(**{"a": "b"})', "'\\*\\*' unpacking is not pdyl"),
        ],
    )
    def test_whitelist_rejections(self, user_registry, geo_registry, src, fragment):
        registry = geo_registry if "has_tags" in src else user_registry
        with pytest.raises(PdylError, match=fragment):
            compile_pdyl(src, registry)

    def test_unexpected_keyword(self, user_registry):
        with pytest.raises(PdylError, match="unexpected keyword argument"):
            compile_pdyl("x = is_adult(min_agee=1)", user_registry)

    def test_missing_required_argument(self, user_registry):
        with pytest.raises(PdylError, match="missing a required argument"):
            compile_pdyl("x = is_named()", user_registry)

    def test_too_many_positional(self, user_registry):
        with pytest.raises(PdylError, match="too many positional"):
            compile_pdyl("x = is_active(1)", user_registry)

    def test_param_type_error_positioned(self, user_registry):
        src = 'ok = is_active()\nx = is_adult(min_age="abc")'
        with pytest.raises(PdylError, match=r"params\.min_age") as exc_info:
            compile_pdyl(src, user_registry)
        assert exc_info.value.lineno == 2

    def test_value_used_as_predicate(self, user_registry):
        with pytest.raises(PdylError, match="value binding, not a predicate"):
            compile_pdyl("LIMIT = 5\nx = LIMIT & is_active()", user_registry)

    def test_predicate_used_as_value(self, user_registry):
        with pytest.raises(PdylError, match="cannot be a parameter value"):
            compile_pdyl("p = is_active()\nx = is_adult(min_age=p)", user_registry)

    def test_duplicate_definition(self, user_registry):
        with pytest.raises(PdylError, match="already defined on line 1") as exc_info:
            compile_pdyl("x = is_active()\nx = is_adult()", user_registry)
        assert exc_info.value.lineno == 2

    def test_circular_reference(self, user_registry):
        src = "a = b & is_active()\nb = a & is_active()"
        with pytest.raises(PdylError, match="circular reference"):
            compile_pdyl(src, user_registry)

    def test_self_reference_is_a_cycle(self, user_registry):
        with pytest.raises(PdylError, match="circular reference: a -> a"):
            compile_pdyl("a = a", user_registry)

    def test_empty_registry_names_the_emptiness(self):
        with pytest.raises(PdylError, match="<empty registry>"):
            compile_pdyl("x = anything()", Registry("empty_registry"))

    def test_error_position_on_continuation_line(self, user_registry):
        src = "gate = (\n    is_adult(min_age=18)\n    & vip_whitelist()\n)"
        with pytest.raises(PdylError, match="unknown rule_def 'vip_whitelist'") as exc_info:
            compile_pdyl(src, user_registry)
        err = exc_info.value
        assert err.lineno == 3
        assert err.text is not None
        assert "vip_whitelist" in err.text

    def test_renders_like_a_syntax_error(self, user_registry):
        with pytest.raises(PdylError) as exc_info:
            compile_pdyl("x = frobnicate()", user_registry, filename="fraud.pdyl")
        rendered = "".join(traceback.format_exception_only(exc_info.value))
        assert 'File "fraud.pdyl", line 1' in rendered
        assert "unknown rule_def 'frobnicate'" in rendered

    def test_star_non_list(self, geo_registry):
        with pytest.raises(PdylError, match="unpack a list"):
            compile_pdyl('x = name_in(*{"a": 1})', geo_registry)

    def test_syntax_error_wrapped(self, user_registry):
        with pytest.raises(PdylError) as exc_info:
            compile_pdyl("x = is_adult(min_age=1", user_registry)
        assert exc_info.value.lineno == 1

    def test_position_and_filename(self, user_registry):
        src = "# comment\nok = is_active()\nx = frobnicate()"
        with pytest.raises(PdylError) as exc_info:
            compile_pdyl(src, user_registry, filename="fraud.pdyl")
        err = exc_info.value
        assert err.filename == "fraud.pdyl"
        assert err.lineno == 3
        assert err.text == "x = frobnicate()"

    def test_cjk_offset_is_character_based(self, user_registry):
        src = 'x = is_named("张三") & 幽灵'
        with pytest.raises(PdylError, match="undefined name '幽灵'") as exc_info:
            compile_pdyl(src, user_registry)
        err = exc_info.value
        assert err.text is not None
        assert err.offset is not None
        assert err.text[err.offset - 1 :].startswith("幽灵")


class TestEndToEnd:
    def test_compile_evaluate(self, registry_manager, user_registry, adult_user, minor_user):
        engine = RuleEngine(registry_manager)
        src = "adult_active = is_adult(min_age=18) & is_active()"
        engine.update_manifests(compile_pdyl(src, user_registry))
        handle = engine.get_predicate_handle("user_registry", "adult_active")
        assert handle(adult_user) is True
        assert handle(minor_user) is False

    def test_trace_reaches_atoms_through_inlining(self, registry_manager, user_registry, minor_user):
        engine = RuleEngine(registry_manager)
        src = "_grown = is_adult(min_age=18)\ngate = _grown & is_active()"
        engine.update_manifests(compile_pdyl(src, user_registry))
        handle = engine.get_predicate_handle("user_registry", "gate")
        trace = handle(minor_user, trace=True, short_circuit=False)
        assert trace.success is False
        assert trace.operator == "and"
        assert len(trace.children) == 2
        assert all(child.operator == "leaf" for child in trace.children)

    def test_hot_swap_same_handle(self, registry_manager, user_registry, adult_user):
        engine = RuleEngine(registry_manager)
        engine.update_manifests(compile_pdyl("gate = is_adult(min_age=18)", user_registry))
        handle = engine.get_predicate_handle("user_registry", "gate")
        assert handle(adult_user) is True
        engine.update_manifests(compile_pdyl("gate = is_adult(min_age=99)", user_registry))
        assert handle(adult_user) is False
