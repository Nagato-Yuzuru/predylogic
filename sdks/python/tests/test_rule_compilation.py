"""
Test suite for RuleEngine compilation - validates rule compilation and execution.

Tests cover:
- Basic LeafNode compilation
- Logic composition (AndNode, OrNode, NotNode)
- Static RefNode resolution
- Error cases (RegistryNotFoundError, RuleDefNotFoundError, RuleDefRingError)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from predylogic import SchemaGenerator
from predylogic.register.errs import RegistryNotFoundError
from predylogic.rule_engine import RuleEngine
from predylogic.rule_engine.base import AndNode, LeafNode, NotNode, OrNode, RefNode
from predylogic.rule_engine.errs import RuleDefRingError

from .conftest import OrderCtx, Product, User


class TestBasicLeafCompilation:
    """Test basic LeafNode compilation and execution."""

    def test_compile_simple_leaf_node(
        self, registry_manager, user_registry, adult_user: User, minor_user: User,
    ):
        """Verify basic LeafNode compiles and executes correctly."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "adult_check": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),
            },
        )

        engine.update_manifests(manifest)
        handle = engine.get_predicate_handle("user_registry", "adult_check")

        # Test execution
        assert handle(adult_user) is True
        assert handle(minor_user) is False

    def test_compile_leaf_with_default_parameter(
        self, registry_manager, user_registry, adult_user: User,
    ):
        """Verify LeafNode with default parameter values works."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # is_adult has min_age with default=18
        manifest = manifest_model(
            rules={
                "adult_check": LeafNode(rule={"rule_def_name": "is_adult"}),  # Uses default min_age=18
            },
        )

        engine.update_manifests(manifest)
        handle = engine.get_predicate_handle("user_registry", "adult_check")

        assert handle(adult_user) is True  # 25 >= 18

    def test_compile_leaf_with_no_parameters(
        self, registry_manager, user_registry, adult_user: User,
    ):
        """Verify LeafNode with no parameters compiles correctly."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "active_check": LeafNode(rule={"rule_def_name": "is_active"}),
            },
        )

        engine.update_manifests(manifest)
        handle = engine.get_predicate_handle("user_registry", "active_check")

        assert handle(adult_user) is True  # adult_user.active=True

    def test_compile_multiple_leaf_nodes(self, registry_manager, user_registry, adult_user: User):
        """Verify multiple independent LeafNodes compile correctly."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "adult_check": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),
                "active_check": LeafNode(rule={"rule_def_name": "is_active"}),
                "name_check": LeafNode(rule={"rule_def_name": "is_named", "name": "Alice"}),
            },
        )

        engine.update_manifests(manifest)

        adult_handle = engine.get_predicate_handle("user_registry", "adult_check")
        active_handle = engine.get_predicate_handle("user_registry", "active_check")
        name_handle = engine.get_predicate_handle("user_registry", "name_check")

        assert adult_handle(adult_user) is True
        assert active_handle(adult_user) is True
        assert name_handle(adult_user) is True


class TestLogicComposition:
    """Test AndNode, OrNode, NotNode compilation."""

    def test_and_node_compilation(
        self, registry_manager, user_registry, adult_user: User, minor_user: User,
    ):
        """Verify AndNode compiles and executes with AND logic."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "adult_and_active": AndNode(
                    rules=[
                        LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),
                        LeafNode(rule={"rule_def_name": "is_active"}),
                    ],
                ),
            },
        )

        engine.update_manifests(manifest)
        handle = engine.get_predicate_handle("user_registry", "adult_and_active")

        # adult_user: age=25, active=True -> both True -> AND = True
        assert handle(adult_user) is True
        # minor_user: age=16, active=False -> both False -> AND = False
        assert handle(minor_user) is False

    def test_or_node_compilation(
        self, registry_manager, user_registry, adult_user: User, minor_user: User,
    ):
        """Verify OrNode compiles and executes with OR logic."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "adult_or_active": OrNode(
                    rules=[
                        LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),
                        LeafNode(rule={"rule_def_name": "is_active"}),
                    ],
                ),
            },
        )

        engine.update_manifests(manifest)
        handle = engine.get_predicate_handle("user_registry", "adult_or_active")

        # adult_user: age=25, active=True -> at least one True -> OR = True
        assert handle(adult_user) is True
        # minor_user: age=16, active=False -> both False -> OR = False
        assert handle(minor_user) is False

    def test_not_node_compilation(self, registry_manager, user_registry, adult_user: User):
        """Verify NotNode compiles and executes with NOT logic."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "not_active": NotNode(
                    rule=LeafNode(rule={"rule_def_name": "is_active"}),
                ),
            },
        )

        engine.update_manifests(manifest)
        handle = engine.get_predicate_handle("user_registry", "not_active")

        # adult_user.active=True -> NOT True = False
        assert handle(adult_user) is False

    def test_nested_logic_composition(
        self, registry_manager, user_registry, adult_user: User,
    ):
        """Verify nested logic nodes compile correctly."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # (is_adult AND is_active) OR is_named("Alice")
        manifest = manifest_model(
            rules={
                "complex_rule": OrNode(
                    rules=[
                        AndNode(
                            rules=[
                                LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),
                                LeafNode(rule={"rule_def_name": "is_active"}),
                            ],
                        ),
                        LeafNode(rule={"rule_def_name": "is_named", "name": "Alice"}),
                    ],
                ),
            },
        )

        engine.update_manifests(manifest)
        handle = engine.get_predicate_handle("user_registry", "complex_rule")

        # adult_user: (25>=18 AND True) OR "Alice"=="Alice" -> True OR True = True
        assert handle(adult_user) is True

    def test_triple_nested_logic(self, registry_manager, user_registry, minor_user: User):
        """Verify deeply nested logic nodes work."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # NOT (is_adult OR is_active)
        manifest = manifest_model(
            rules={
                "not_adult_or_active": NotNode(
                    rule=OrNode(
                        rules=[
                            LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),
                            LeafNode(rule={"rule_def_name": "is_active"}),
                        ],
                    ),
                ),
            },
        )

        engine.update_manifests(manifest)
        handle = engine.get_predicate_handle("user_registry", "not_adult_or_active")

        # minor_user: age=16, active=False -> (False OR False) = False -> NOT False = True
        assert handle(minor_user) is True


class TestStaticRefNode:
    """Test RefNode resolution where both rules exist in manifest."""

    def test_static_ref_node_resolution(
        self, registry_manager, user_registry, adult_user: User,
    ):
        """Verify RefNode resolves to referenced rule when both exist."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Rule A references Rule B, both defined in manifest
        manifest = manifest_model(
            rules={
                "rule_b": LeafNode(rule={"rule_def_name": "is_active"}),
                "rule_a": RefNode(ref_id="rule_b"),
            },
        )

        engine.update_manifests(manifest)
        handle_a = engine.get_predicate_handle("user_registry", "rule_a")

        # rule_a -> rule_b -> is_active
        assert handle_a(adult_user) is True

    def test_ref_node_with_logic_composition(
        self, registry_manager, user_registry, adult_user: User,
    ):
        """Verify RefNode works within logic compositions."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # rule_c = rule_a AND rule_b (both are refs)
        manifest = manifest_model(
            rules={
                "adult_leaf": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),
                "active_leaf": LeafNode(rule={"rule_def_name": "is_active"}),
                "rule_a": RefNode(ref_id="adult_leaf"),
                "rule_b": RefNode(ref_id="active_leaf"),
                "rule_c": AndNode(rules=[RefNode(ref_id="rule_a"), RefNode(ref_id="rule_b")]),
            },
        )

        engine.update_manifests(manifest)
        handle_c = engine.get_predicate_handle("user_registry", "rule_c")

        # rule_c -> (rule_a AND rule_b) -> (adult_leaf AND active_leaf)
        assert handle_c(adult_user) is True

    def test_transitive_ref_chain(self, registry_manager, user_registry, adult_user: User):
        """Verify transitive RefNode chains (A->B->C->Leaf) work."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "leaf": LeafNode(rule={"rule_def_name": "is_active"}),
                "ref_c": RefNode(ref_id="leaf"),
                "ref_b": RefNode(ref_id="ref_c"),
                "ref_a": RefNode(ref_id="ref_b"),
            },
        )

        engine.update_manifests(manifest)
        handle_a = engine.get_predicate_handle("user_registry", "ref_a")

        # ref_a -> ref_b -> ref_c -> leaf
        assert handle_a(adult_user) is True


class TestErrorCases:
    """Test error handling during compilation."""

    def test_registry_not_found_error(self, registry_manager, user_registry):
        """Verify RegistryNotFoundError raised for non-existent registry."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Create manifest but manually change registry name
        manifest = manifest_model(
            rules={
                "rule1": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),
            },
        )

        # Manually override registry to non-existent one
        manifest = manifest.model_copy(update={"registry": "non_existent_registry"})

        with pytest.raises(RegistryNotFoundError) as exc_info:
            engine.update_manifests(manifest)

        assert exc_info.value.registry_name == "non_existent_registry"

    def test_rule_def_not_found_error(self, registry_manager, user_registry, adult_user: User):
        """Verify RuleDefNotFoundError raised for non-existent rule_def."""
        # This test verifies that Pydantic's discriminator validation prevents invalid rule_def_names.
        # The SchemaGenerator creates a discriminated union that only allows registered rule_def_names,
        # so attempting to create a manifest with an unregistered rule_def_name will raise ValidationError.

        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Attempting to create a LeafNode with non-existent rule_def_name should raise ValidationError
        # because the discriminator only allows registered rule names
        with pytest.raises(ValidationError) as exc_info:
            manifest_model(
                rules={
                    "bad_rule": LeafNode(
                        rule={
                            "rule_def_name": "non_existent_rule_def",
                        },
                    ),
                },
            )

        # Verify the error mentions discriminator or rule_def_name
        assert "discriminator" in str(exc_info.value).lower() or "rule_def_name" in str(exc_info.value).lower()

    def test_cyclic_dependency_raises_ring_error(self, registry_manager, user_registry):
        """Verify RuleDefRingError raised for cyclic RefNode dependencies."""
        engine = RuleEngine(registry_manager)

        # Create manifest with cycle: A->B->C->A
        from predylogic.rule_engine.base import RuleSetManifest

        manifest_dict = {
            "registry": "user_registry",
            "rules": {
                "rule_a": {"node_type": "ref", "ref_id": "rule_b"},
                "rule_b": {"node_type": "ref", "ref_id": "rule_c"},
                "rule_c": {"node_type": "ref", "ref_id": "rule_a"},  # Cycle!
            },
        }

        with pytest.raises(RuleDefRingError) as exc_info:
            RuleSetManifest(**manifest_dict)

        assert len(exc_info.value.ring) >= 2  # Cycle should contain multiple nodes

    def test_self_referencing_rule_raises_ring_error(self, registry_manager, user_registry):
        """Verify RuleDefRingError raised for self-referencing rule."""
        engine = RuleEngine(registry_manager)

        from predylogic.rule_engine.base import RuleSetManifest

        manifest_dict = {
            "registry": "user_registry",
            "rules": {
                "rule_a": {"node_type": "ref", "ref_id": "rule_a"},  # Self-reference!
            },
        }

        with pytest.raises(RuleDefRingError) as exc_info:
            RuleSetManifest(**manifest_dict)

        assert "rule_a" in str(exc_info.value.ring)


class TestDiverseContextTypes:
    """Test compilation works with diverse context types."""

    def test_typeddict_context_compilation(
        self, registry_manager, order_registry, priority_order: OrderCtx,
    ):
        """Verify compilation works with TypedDict context."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(order_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "expensive_priority": AndNode(
                    rules=[
                        LeafNode(rule={"rule_def_name": "min_total", "amount": 100.0}),
                        LeafNode(rule={"rule_def_name": "is_priority"}),
                    ],
                ),
            },
        )

        engine.update_manifests(manifest)
        handle = engine.get_predicate_handle("order_registry", "expensive_priority")

        # priority_order: total=150.0, is_priority=True -> True AND True = True
        assert handle(priority_order) is True

    def test_plain_class_context_compilation(
        self, registry_manager, product_registry, expensive_product: Product,
    ):
        """Verify compilation works with plain class context."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(product_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "premium_in_stock": AndNode(
                    rules=[
                        LeafNode(rule={"rule_def_name": "min_price", "price": 1000.0}),
                        LeafNode(rule={"rule_def_name": "in_stock"}),
                    ],
                ),
            },
        )

        engine.update_manifests(manifest)
        handle = engine.get_predicate_handle("product_registry", "premium_in_stock")

        # expensive_product: price=1200.0, in_stock=True -> True AND True = True
        assert handle(expensive_product) is True
