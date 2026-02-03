"""
Test suite for RuleEngine lifecycle management (CRITICAL).

Tests cover:
- Hot Reload: Atomic handle updates when manifests change
- Lazy Linking/Tombstone: Missing rules raise RuleRevokedError, then resolve
- Handle Singleton: get_predicate_handle returns identical object instances
- Partial manifest updates and registry isolation
"""

from __future__ import annotations

import pytest

from predylogic import SchemaGenerator
from predylogic.rule_engine import RuleEngine
from predylogic.rule_engine.base import LeafNode, RefNode
from predylogic.rule_engine.errs import RuleRevokedError

from .conftest import OrderCtx, User


class TestHotReload:
    """Test hot reload - atomic handle updates without re-fetching."""

    def test_hot_reload_atomic_update(self, registry_manager, user_registry, adult_user: User):
        """
        CRITICAL: Verify existing handle instance updates atomically.
        1. Load Rule A (returns True)
        2. Get handle
        3. Update manifest where Rule A returns False
        4. Assert same handle instance now returns False
        """
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Initial manifest: is_active rule
        manifest_v1 = manifest_model(
            rules={
                "active_check": LeafNode(rule={"rule_def_name": "is_active"}),
            },
        )

        engine.update_manifests(manifest_v1)
        handle_v1 = engine.get_predicate_handle("user_registry", "active_check")

        # Verify initial behavior
        assert handle_v1(adult_user) is True  # adult_user.active=True

        # Update manifest: change to is_adult with high min_age (will return False for our user)
        manifest_v2 = manifest_model(
            rules={
                "active_check": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 100}),
            },
        )

        engine.update_manifests(manifest_v2)

        # Get handle again - should be same Python object
        handle_v2 = engine.get_predicate_handle("user_registry", "active_check")

        # CRITICAL: Verify singleton property - same object instance
        assert handle_v1 is handle_v2, "Handle should be same Python object instance"

        # CRITICAL: Verify atomic update - behavior changed without re-fetching
        assert handle_v1(adult_user) is False  # Now checks age >= 100, which is False
        assert handle_v2(adult_user) is False  # Same behavior

    def test_hot_reload_multiple_rules(
        self, registry_manager, user_registry, adult_user: User, minor_user: User,
    ):
        """Verify hot reload works with multiple rules independently."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Initial manifest with two rules
        manifest_v1 = manifest_model(
            rules={
                "rule_a": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),
                "rule_b": LeafNode(rule={"rule_def_name": "is_active"}),
            },
        )

        engine.update_manifests(manifest_v1)
        handle_a_v1 = engine.get_predicate_handle("user_registry", "rule_a")
        handle_b_v1 = engine.get_predicate_handle("user_registry", "rule_b")

        # Initial behavior
        assert handle_a_v1(adult_user) is True
        assert handle_b_v1(adult_user) is True

        # Update only rule_a, leave rule_b unchanged
        manifest_v2 = manifest_model(
            rules={
                "rule_a": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 100}),
                "rule_b": LeafNode(rule={"rule_def_name": "is_active"}),  # Unchanged
            },
        )

        engine.update_manifests(manifest_v2)

        # Get handles again
        handle_a_v2 = engine.get_predicate_handle("user_registry", "rule_a")
        handle_b_v2 = engine.get_predicate_handle("user_registry", "rule_b")

        # Verify singleton
        assert handle_a_v1 is handle_a_v2
        assert handle_b_v1 is handle_b_v2

        # Verify only rule_a changed
        assert handle_a_v1(adult_user) is False  # Updated
        assert handle_b_v1(adult_user) is True  # Unchanged

    def test_hot_reload_updates_referenced_rules(
        self, registry_manager, user_registry, adult_user: User,
    ):
        """Verify hot reload updates rules referenced by RefNodes."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Initial manifest: rule_a refs rule_b
        manifest_v1 = manifest_model(
            rules={
                "rule_b": LeafNode(rule={"rule_def_name": "is_active"}),
                "rule_a": RefNode(ref_id="rule_b"),
            },
        )

        engine.update_manifests(manifest_v1)
        handle_a = engine.get_predicate_handle("user_registry", "rule_a")
        handle_b = engine.get_predicate_handle("user_registry", "rule_b")

        # Initial behavior: rule_a -> rule_b -> is_active
        assert handle_a(adult_user) is True

        # Update rule_b (the referenced rule)
        manifest_v2 = manifest_model(
            rules={
                "rule_b": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 100}),
                "rule_a": RefNode(ref_id="rule_b"),  # Still references rule_b
            },
        )

        engine.update_manifests(manifest_v2)

        # Get handles again
        handle_a_v2 = engine.get_predicate_handle("user_registry", "rule_a")
        handle_b_v2 = engine.get_predicate_handle("user_registry", "rule_b")

        # Verify singletons
        assert handle_a is handle_a_v2
        assert handle_b is handle_b_v2

        # Verify rule_a now reflects updated rule_b behavior
        assert handle_a(adult_user) is False  # rule_b changed, so rule_a result changes


class TestLazyLinkingTombstone:
    """Test lazy linking and tombstone behavior for missing rules."""

    def test_tombstone_missing_rule_raises_revoked_error(
        self, registry_manager, user_registry, adult_user: User,
    ):
        """
        CRITICAL: Verify missing rule creates tombstone raising RuleRevokedError.
        1. Load Rule A referencing Rule B (B doesn't exist)
        2. Execute Rule A -> raises RuleRevokedError
        """
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Manifest with rule_a referencing non-existent rule_b
        manifest = manifest_model(
            rules={
                "rule_a": RefNode(ref_id="rule_b"),  # rule_b doesn't exist!
            },
        )

        engine.update_manifests(manifest)
        handle_a = engine.get_predicate_handle("user_registry", "rule_a")

        # rule_b doesn't exist, so rule_a should hit tombstone
        with pytest.raises(RuleRevokedError) as exc_info:
            handle_a(adult_user)

        assert exc_info.value.registry_name == "user_registry"
        assert exc_info.value.rule_name == "rule_b"

    def test_tombstone_resolves_after_update(
        self, registry_manager, user_registry, adult_user: User,
    ):
        """
        CRITICAL: Verify tombstone transitions to real logic after update.
        1. Load Rule A referencing missing Rule B -> raises RuleRevokedError
        2. Update manifest with Rule B
        3. Execute Rule A -> works successfully
        """
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Step 1: rule_a references missing rule_b
        manifest_v1 = manifest_model(
            rules={
                "rule_a": RefNode(ref_id="rule_b"),  # rule_b missing
            },
        )

        engine.update_manifests(manifest_v1)
        handle_a = engine.get_predicate_handle("user_registry", "rule_a")

        # Verify tombstone raises error
        with pytest.raises(RuleRevokedError):
            handle_a(adult_user)

        # Step 2: Update manifest to include rule_b
        manifest_v2 = manifest_model(
            rules={
                "rule_b": LeafNode(rule={"rule_def_name": "is_active"}),
                "rule_a": RefNode(ref_id="rule_b"),
            },
        )

        engine.update_manifests(manifest_v2)

        # Step 3: Get handle again (should be same instance)
        handle_a_v2 = engine.get_predicate_handle("user_registry", "rule_a")

        # Verify singleton
        assert handle_a is handle_a_v2, "Handle should be same instance"

        # CRITICAL: Verify tombstone resolved - now works
        assert handle_a(adult_user) is True  # rule_a -> rule_b -> is_active

    def test_direct_tombstone_access(self, registry_manager, adult_user: User):
        """Verify directly accessing non-existent rule creates tombstone."""
        engine = RuleEngine(registry_manager)

        # Get handle for rule that was never loaded
        handle = engine.get_predicate_handle("user_registry", "non_existent_rule")

        # Should raise RuleRevokedError
        with pytest.raises(RuleRevokedError) as exc_info:
            handle(adult_user)

        assert exc_info.value.rule_name == "non_existent_rule"

    def test_tombstone_in_logic_composition(
        self, registry_manager, user_registry, adult_user: User,
    ):
        """Verify tombstone in logic composition raises error."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # AndNode with one valid rule and one missing ref
        from predylogic.rule_engine.base import AndNode

        manifest = manifest_model(
            rules={
                "rule_a": AndNode(
                    rules=[
                        LeafNode(rule={"rule_def_name": "is_active"}),
                        RefNode(ref_id="missing_rule"),  # Missing!
                    ],
                ),
            },
        )

        engine.update_manifests(manifest)
        handle = engine.get_predicate_handle("user_registry", "rule_a")

        # Should raise when evaluating the missing ref
        with pytest.raises(RuleRevokedError):
            handle(adult_user)


class TestHandleSingleton:
    """Test PredicateHandle singleton property."""

    def test_get_handle_multiple_times_returns_same_instance(
        self, registry_manager, user_registry,
    ):
        """
        CRITICAL: Verify get_predicate_handle returns identical Python object.
        """
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "rule_a": LeafNode(rule={"rule_def_name": "is_active"}),
            },
        )

        engine.update_manifests(manifest)

        # Get handle multiple times
        handle_1 = engine.get_predicate_handle("user_registry", "rule_a")
        handle_2 = engine.get_predicate_handle("user_registry", "rule_a")
        handle_3 = engine.get_predicate_handle("user_registry", "rule_a")

        # Verify all are same instance
        assert handle_1 is handle_2
        assert handle_2 is handle_3
        assert id(handle_1) == id(handle_2) == id(handle_3)

    def test_different_rules_have_different_handles(
        self, registry_manager, user_registry,
    ):
        """Verify different rules have distinct handle instances."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "rule_a": LeafNode(rule={"rule_def_name": "is_active"}),
                "rule_b": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),
            },
        )

        engine.update_manifests(manifest)

        handle_a = engine.get_predicate_handle("user_registry", "rule_a")
        handle_b = engine.get_predicate_handle("user_registry", "rule_b")

        # Should be different instances
        assert handle_a is not handle_b
        assert id(handle_a) != id(handle_b)

    def test_tombstone_handle_is_singleton(self, registry_manager):
        """Verify tombstone handles are also singletons."""
        engine = RuleEngine(registry_manager)

        # Get handle for non-existent rule multiple times
        handle_1 = engine.get_predicate_handle("user_registry", "non_existent")
        handle_2 = engine.get_predicate_handle("user_registry", "non_existent")

        # Should be same instance
        assert handle_1 is handle_2


class TestPartialManifestUpdates:
    """Test partial manifest updates and registry isolation."""

    def test_updating_one_registry_doesnt_affect_another(
        self, registry_manager, user_registry, order_registry, adult_user: User, priority_order: OrderCtx,
    ):
        """Verify updating Registry A doesn't affect Registry B."""
        engine = RuleEngine(registry_manager)

        # Load manifests for both registries
        user_schema = SchemaGenerator(user_registry).generate()
        order_schema = SchemaGenerator(order_registry).generate()

        user_manifest = user_schema(
            rules={
                "user_rule": LeafNode(rule={"rule_def_name": "is_active"}),
            },
        )

        order_manifest = order_schema(
            rules={
                "order_rule": LeafNode(rule={"rule_def_name": "is_priority"}),
            },
        )

        engine.update_manifests(user_manifest, order_manifest)

        user_handle = engine.get_predicate_handle("user_registry", "user_rule")
        order_handle = engine.get_predicate_handle("order_registry", "order_rule")

        # Initial state
        assert user_handle(adult_user) is True
        assert order_handle(priority_order) is True

        # Update only user_registry
        user_manifest_v2 = user_schema(
            rules={
                "user_rule": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 100}),
            },
        )

        engine.update_manifests(user_manifest_v2)

        # Get handles again
        user_handle_v2 = engine.get_predicate_handle("user_registry", "user_rule")
        order_handle_v2 = engine.get_predicate_handle("order_registry", "order_rule")

        # Verify user_handle updated
        assert user_handle is user_handle_v2
        assert user_handle(adult_user) is False  # Changed

        # Verify order_handle unchanged
        assert order_handle is order_handle_v2
        assert order_handle(priority_order) is True  # Unchanged

    def test_update_subset_of_rules(self, registry_manager, user_registry, adult_user: User):
        """Verify updating subset of rules doesn't affect others."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Initial manifest with 3 rules
        manifest_v1 = manifest_model(
            rules={
                "rule_a": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),
                "rule_b": LeafNode(rule={"rule_def_name": "is_active"}),
                "rule_c": LeafNode(rule={"rule_def_name": "is_named", "name": "Alice"}),
            },
        )

        engine.update_manifests(manifest_v1)

        handle_a = engine.get_predicate_handle("user_registry", "rule_a")
        handle_b = engine.get_predicate_handle("user_registry", "rule_b")
        handle_c = engine.get_predicate_handle("user_registry", "rule_c")

        # Update only rule_b
        manifest_v2 = manifest_model(
            rules={
                "rule_a": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),  # Same
                "rule_b": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 100}),  # Changed
                "rule_c": LeafNode(rule={"rule_def_name": "is_named", "name": "Alice"}),  # Same
            },
        )

        engine.update_manifests(manifest_v2)

        # Verify all handles are singletons
        assert handle_a is engine.get_predicate_handle("user_registry", "rule_a")
        assert handle_b is engine.get_predicate_handle("user_registry", "rule_b")
        assert handle_c is engine.get_predicate_handle("user_registry", "rule_c")

        # Verify only rule_b changed
        assert handle_a(adult_user) is True  # Unchanged
        assert handle_b(adult_user) is False  # Changed
        assert handle_c(adult_user) is True  # Unchanged

    def test_remove_rule_from_manifest_preserves_handle(
        self, registry_manager, user_registry, adult_user: User,
    ):
        """Verify removing rule from manifest doesn't break existing handle."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Initial manifest with rule
        manifest_v1 = manifest_model(
            rules={
                "rule_a": LeafNode(rule={"rule_def_name": "is_active"}),
            },
        )

        engine.update_manifests(manifest_v1)
        handle_a = engine.get_predicate_handle("user_registry", "rule_a")

        # Verify works
        assert handle_a(adult_user) is True

        # Update manifest without rule_a
        manifest_v2 = manifest_model(rules={})

        engine.update_manifests(manifest_v2)

        # Handle should still exist and work with last-known-good state
        handle_a_v2 = engine.get_predicate_handle("user_registry", "rule_a")
        assert handle_a is handle_a_v2

        # Should still have old behavior (last-known-good)
        assert handle_a(adult_user) is True


class TestEdgeCases:
    """Test edge cases in lifecycle management."""

    def test_empty_manifest_update(self, registry_manager, user_registry):
        """Verify updating with empty manifest doesn't break engine."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest_empty = manifest_model(rules={})

        # Should not raise
        engine.update_manifests(manifest_empty)

    def test_update_before_any_get_handle(
        self, registry_manager, user_registry, adult_user: User,
    ):
        """Verify update_manifests works before any get_predicate_handle calls."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "rule_a": LeafNode(rule={"rule_def_name": "is_active"}),
            },
        )

        # Update before getting any handles
        engine.update_manifests(manifest)

        # Now get handle - should work
        handle = engine.get_predicate_handle("user_registry", "rule_a")
        assert handle(adult_user) is True

    def test_multiple_manifest_updates_in_sequence(
        self, registry_manager, user_registry, adult_user: User,
    ):
        """Verify multiple sequential updates work correctly."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Update 1
        manifest_v1 = manifest_model(
            rules={"rule_a": LeafNode(rule={"rule_def_name": "is_active"})},
        )
        engine.update_manifests(manifest_v1)
        handle = engine.get_predicate_handle("user_registry", "rule_a")
        assert handle(adult_user) is True

        # Update 2
        manifest_v2 = manifest_model(
            rules={"rule_a": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 100})},
        )
        engine.update_manifests(manifest_v2)
        assert handle(adult_user) is False

        # Update 3
        manifest_v3 = manifest_model(
            rules={"rule_a": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18})},
        )
        engine.update_manifests(manifest_v3)
        assert handle(adult_user) is True

        # Verify still same handle instance
        assert handle is engine.get_predicate_handle("user_registry", "rule_a")
