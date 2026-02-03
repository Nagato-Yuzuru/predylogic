"""
Test suite for RuleEngine concurrency - validates thread safety.

Tests cover:
- Thread-safe handle creation (Double-Checked Locking)
- Concurrent get_predicate_handle calls create only one handle
- Concurrent update_manifests safety
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from predylogic import SchemaGenerator
from predylogic.rule_engine import RuleEngine
from predylogic.rule_engine.base import LeafNode

from .conftest import User


class TestConcurrentHandleCreation:
    """Test concurrent handle creation uses proper locking."""

    def test_concurrent_get_handle_creates_single_instance(
        self,
        registry_manager,
        user_registry,
    ):
        """
        CRITICAL: Verify Double-Checked Locking works.
        Launch multiple threads requesting same handle simultaneously.
        Only one PredicateHandle instance should be created.
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

        # Launch 50 threads simultaneously requesting same handle
        num_threads = 50
        handles = []
        barrier = threading.Barrier(num_threads)  # Synchronize threads to start together

        def get_handle():
            barrier.wait()  # Wait for all threads to be ready
            handle = engine.get_predicate_handle("user_registry", "rule_a")
            return handle

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(get_handle) for _ in range(num_threads)]
            handles = [f.result() for f in as_completed(futures)]

        # CRITICAL: All handles should be same instance
        first_handle = handles[0]
        for handle in handles:
            assert handle is first_handle, "All handles should be same Python object"
            assert id(handle) == id(first_handle)

    def test_concurrent_get_different_handles(self, registry_manager, user_registry):
        """Verify concurrent requests for different handles work correctly."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={
                "rule_a": LeafNode(rule={"rule_def_name": "is_active"}),
                "rule_b": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18}),
                "rule_c": LeafNode(rule={"rule_def_name": "is_named", "name": "Alice"}),
            },  # ty:ignore[invalid-argument-type]
        )  # ty:ignore[missing-argument]

        engine.update_manifests(manifest)

        # Launch threads requesting different handles
        num_threads = 30
        results = []

        def get_mixed_handles(rule_name: str):
            handle = engine.get_predicate_handle("user_registry", rule_name)
            return rule_name, handle

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for i in range(num_threads):
                rule_name = ["rule_a", "rule_b", "rule_c"][i % 3]
                futures.append(executor.submit(get_mixed_handles, rule_name))

            results = [f.result() for f in as_completed(futures)]

        # Group by rule name
        handles_by_rule = {"rule_a": [], "rule_b": [], "rule_c": []}
        for rule_name, handle in results:
            handles_by_rule[rule_name].append(handle)

        # Verify each rule has singleton handles
        for rule_name, handles in handles_by_rule.items():
            first = handles[0]
            for handle in handles:
                assert handle is first, f"All handles for {rule_name} should be same instance"

    def test_concurrent_tombstone_creation(self, registry_manager):
        """Verify concurrent access to non-existent rule creates single tombstone."""
        engine = RuleEngine(registry_manager)

        num_threads = 30
        handles = []
        barrier = threading.Barrier(num_threads)

        def get_missing_handle():
            barrier.wait()
            handle = engine.get_predicate_handle("user_registry", "non_existent")
            return handle

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(get_missing_handle) for _ in range(num_threads)]
            handles = [f.result() for f in as_completed(futures)]

        # All should be same tombstone instance
        first_handle = handles[0]
        for handle in handles:
            assert handle is first_handle


class TestConcurrentManifestUpdates:
    """Test concurrent manifest updates are thread-safe."""

    def test_concurrent_updates_dont_corrupt_state(
        self,
        registry_manager,
        user_registry,
        adult_user: User,
    ):
        """
        Verify concurrent update_manifests calls don't corrupt engine state.
        """
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Pre-create handle
        manifest_initial = manifest_model(
            rules={"rule_a": LeafNode(rule={"rule_def_name": "is_active"})},
        )
        engine.update_manifests(manifest_initial)
        handle = engine.get_predicate_handle("user_registry", "rule_a")

        # Launch concurrent updates
        num_threads = 20

        def update_manifest(iteration: int):
            # Alternate between two different rule configs
            if iteration % 2 == 0:
                manifest = manifest_model(
                    rules={"rule_a": LeafNode(rule={"rule_def_name": "is_active"})},
                )
            else:
                manifest = manifest_model(
                    rules={"rule_a": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18})},
                )
            engine.update_manifests(manifest)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(update_manifest, i) for i in range(num_threads)]
            for f in as_completed(futures):
                f.result()  # Raise any exceptions

        # Verify engine still functional and handle is singleton
        handle_after = engine.get_predicate_handle("user_registry", "rule_a")
        assert handle is handle_after

        # Should execute without errors
        result = handle(adult_user)
        assert isinstance(result, bool)

    def test_concurrent_get_and_update(
        self,
        registry_manager,
        user_registry,
        adult_user: User,
    ):
        """
        Verify concurrent get_predicate_handle and update_manifests calls work.
        """
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={"rule_a": LeafNode(rule={"rule_def_name": "is_active"})},
        )
        engine.update_manifests(manifest)

        num_readers = 20
        num_writers = 5
        handles_collected = []

        def reader():
            for _ in range(10):
                handle = engine.get_predicate_handle("user_registry", "rule_a")
                handles_collected.append(handle)
                try:
                    handle(adult_user)  # Try to execute
                except Exception:
                    pass  # Might hit RuleRevokedError during updates

        def writer(iteration: int):
            manifest = manifest_model(
                rules={"rule_a": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18})},
            )
            engine.update_manifests(manifest)

        with ThreadPoolExecutor(max_workers=num_readers + num_writers) as executor:
            futures = []
            for i in range(num_readers):
                futures.append(executor.submit(reader))
            for i in range(num_writers):
                futures.append(executor.submit(writer, i))

            for f in as_completed(futures):
                f.result()

        # Verify all collected handles are same instance
        if handles_collected:
            first = handles_collected[0]
            for handle in handles_collected:
                assert handle is first

    def test_concurrent_updates_multiple_registries(
        self,
        registry_manager,
        user_registry,
        order_registry,
    ):
        """Verify concurrent updates to different registries are isolated."""
        engine = RuleEngine(registry_manager)

        user_schema = SchemaGenerator(user_registry).generate()
        order_schema = SchemaGenerator(order_registry).generate()

        # Pre-load manifests
        user_manifest = user_schema(
            rules={"rule_a": LeafNode(rule={"rule_def_name": "is_active"})},
        )
        order_manifest = order_schema(
            rules={"rule_b": LeafNode(rule={"rule_def_name": "is_priority"})},
        )

        engine.update_manifests(user_manifest, order_manifest)

        user_handle = engine.get_predicate_handle("user_registry", "rule_a")
        order_handle = engine.get_predicate_handle("order_registry", "rule_b")

        num_threads = 20

        def update_user(iteration: int):
            manifest = user_schema(
                rules={"rule_a": LeafNode(rule={"rule_def_name": "is_active"})},
            )
            engine.update_manifests(manifest)

        def update_order(iteration: int):
            manifest = order_schema(
                rules={"rule_b": LeafNode(rule={"rule_def_name": "is_priority"})},
            )
            engine.update_manifests(manifest)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(num_threads):
                if i % 2 == 0:
                    futures.append(executor.submit(update_user, i))
                else:
                    futures.append(executor.submit(update_order, i))

            for f in as_completed(futures):
                f.result()

        # Verify handles still singletons
        assert user_handle is engine.get_predicate_handle("user_registry", "rule_a")
        assert order_handle is engine.get_predicate_handle("order_registry", "rule_b")


class TestConcurrentExecution:
    """Test concurrent execution of predicates."""

    def test_concurrent_predicate_execution(
        self,
        registry_manager,
        user_registry,
        adult_user: User,
        minor_user: User,
    ):
        """Verify concurrent execution of same handle is thread-safe."""
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={"rule_a": LeafNode(rule={"rule_def_name": "is_adult", "min_age": 18})},
        )

        engine.update_manifests(manifest)
        handle = engine.get_predicate_handle("user_registry", "rule_a")

        num_threads = 50
        results = []

        def execute_predicate(user: User, expected: bool):
            result = handle(user)
            return result, expected

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for i in range(num_threads):
                if i % 2 == 0:
                    futures.append(executor.submit(execute_predicate, adult_user, True))
                else:
                    futures.append(executor.submit(execute_predicate, minor_user, False))

            for future in as_completed(futures):
                result, expected = future.result()
                results.append((result, expected))

        # Verify all results match expectations
        for result, expected in results:
            assert result == expected


class TestRacConditions:
    """Test potential race conditions."""

    def test_no_race_in_handle_cache_access(self, registry_manager, user_registry):
        """
        Verify no race conditions when multiple threads access handle cache.
        """
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        # Create manifest with multiple rules
        manifest = manifest_model(
            rules={f"rule_{i}": LeafNode(rule={"rule_def_name": "is_active"}) for i in range(20)},
        )

        engine.update_manifests(manifest)

        num_threads = 50
        all_handles = []

        def get_random_handles():
            handles = []
            for i in range(20):
                handle = engine.get_predicate_handle("user_registry", f"rule_{i}")
                handles.append((f"rule_{i}", handle))
            return handles

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(get_random_handles) for _ in range(num_threads)]
            for f in as_completed(futures):
                all_handles.extend(f.result())

        # Group by rule name and verify singleton
        handles_by_name = {}
        for rule_name, handle in all_handles:
            if rule_name not in handles_by_name:
                handles_by_name[rule_name] = []
            handles_by_name[rule_name].append(handle)

        for rule_name, handles in handles_by_name.items():
            first = handles[0]
            for handle in handles:
                assert handle is first, f"Rule {rule_name} should have singleton handle"

    def test_update_during_handle_creation(self, registry_manager, user_registry):
        """
        Verify updating manifest during handle creation doesn't cause issues.
        """
        engine = RuleEngine(registry_manager)
        schema_gen = SchemaGenerator(user_registry)
        manifest_model = schema_gen.generate()

        manifest = manifest_model(
            rules={"rule_a": LeafNode(rule={"rule_def_name": "is_active"})},
        )

        num_threads = 30
        handles = []

        def get_or_update(iteration: int):
            if iteration % 3 == 0:
                # Update
                engine.update_manifests(manifest)
            else:
                # Get handle
                handle = engine.get_predicate_handle("user_registry", "rule_a")
                return handle

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_or_update, i) for i in range(num_threads)]
            for f in as_completed(futures):
                result = f.result()
                if result is not None:
                    handles.append(result)

        # All handles should be same instance
        if handles:
            first = handles[0]
            for handle in handles:
                assert handle is first
