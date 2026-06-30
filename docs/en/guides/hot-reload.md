# Hot Reloading

Rules change as the business changes, but a caller holding a reference to one shouldn't break because of an update. predylogic separates *getting a rule* from *the rule's current implementation*: `get_predicate_handle` returns a stable handle, and `update_manifests` swaps the implementation behind it atomically.

This guide continues the loading flow from [Schema & Serde](serde.md), reusing its `txn` registry, `Manifest` model, and `engine`.

## Why it exists

A common case: a risk threshold needs to change without restarting the service. Callers usually fetch a predicate handle once at startup and hold onto it (in a config object, a closure). If every update forced them to re-fetch the reference, it's easy to miss one and run stale logic.

predylogic's approach: the handle object never changes; only what it points to is swapped behind it.

## PredicateHandle: a mutable pointer

`get_predicate_handle(registry, rule_name)` always returns the **same Python object** for a given `(registry, rule_name)` (a singleton). Internally it holds a reference to a predicate; `update_manifests` swaps that reference for a freshly compiled one under an `RLock`. The handle the caller holds stays the same, but its behavior updates:

```python
def gate_manifest(threshold: int):
    return Manifest.model_validate(
        {
            "registry": "txn",
            "rules": {
                "gate": {
                    "node_type": "leaf",
                    "rule": {"rule_def_name": "is_high_value", "params": {"threshold": threshold}},
                },
            },
        }
    )


tx = {"amount": 5000, "region": "JP", "is_fraud_flagged": False}

# v1: threshold 1000
engine.update_manifests(gate_manifest(1000))
gate = engine.get_predicate_handle("txn", "gate")
assert gate(tx)  # 5000 >= 1000

# v2: threshold raised to 10000; no restart, no re-fetch
engine.update_manifests(gate_manifest(10000))
assert gate is engine.get_predicate_handle("txn", "gate")  # same object
assert not gate(tx)  # 5000 < 10000, behavior updated
```

When a rule references another via `ref`, the update propagates: update the referenced rule and the referencing rule's behavior changes too, because what it holds is the referenced rule's handle, which is swapped atomically.

!!! note "Removal ≠ revocation"

    `update_manifests` is an incremental overwrite: it adds or replaces the rules present in the manifest and leaves the rest alone. If a new manifest omits a rule that was already loaded, its handle keeps the last implementation that compiled cleanly (last-known-good) rather than being revoked. To disable a rule, replace it explicitly with the logic you want.

## Tombstones: references to not-yet-defined rules

Fetching a rule that isn't defined yet, or a `ref` pointing at a target that isn't defined yet, doesn't fail right away. You get a **tombstone** handle (also a singleton). Calling it before the rule is defined raises `RuleRevokedError`; once a later `update_manifests` supplies the definition, the same handle object resolves to the real logic:

```python
from predylogic.rule_engine.errs import RuleRevokedError

# alias references a not-yet-defined rule "missing"
engine.update_manifests(
    Manifest.model_validate(
        {"registry": "txn", "rules": {"alias": {"node_type": "ref", "ref_id": "missing"}}}
    )
)
alias = engine.get_predicate_handle("txn", "alias")

try:
    alias(tx)  # missing isn't defined yet
except RuleRevokedError as e:
    print(e)  # Rule 'missing' in txn revoked or missing.

# supply missing's definition; the same alias handle now works
engine.update_manifests(
    Manifest.model_validate(
        {
            "registry": "txn",
            "rules": {
                "missing": {"node_type": "leaf", "rule": {"rule_def_name": "is_safe", "params": {}}},
                "alias": {"node_type": "ref", "ref_id": "missing"},
            },
        }
    )
)
assert alias is engine.get_predicate_handle("txn", "alias")
assert alias(tx)  # resolves to is_safe -> True
```

This makes load order irrelevant: you can fetch a handle and hand it to callers, then fill in the rules it depends on later.

## Concurrency guarantees

Both `get_predicate_handle` and `update_manifests` are thread-safe. Handle creation uses double-checked locking, so even with many threads requesting the same `(registry, rule_name)` at once, only one instance is created. `update_manifests` runs under an `RLock`, so concurrent reads (fetching handles, evaluating) and writes (updates) don't corrupt state. Different registries and rules are independent; one update only touches the rules present in the manifest.

These guarantees are covered by the regression tests in `tests/test_concurrency.py` (singleton handle creation, concurrent updates, concurrent read/write, concurrent execution).

## See also

- Config format and schema validation: [Schema & Serde](serde.md).
- If you only compose in code and don't need runtime updates, the `&` / `|` from the [Quick Start](../quick-start.md) is enough.
