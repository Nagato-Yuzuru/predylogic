# Schema & Serde

predylogic's goals are config-as-data, type safety, and hot reloading. This guide covers the first: export a JSON Schema for validation, then load executable predicates from a manifest. That lets rules live in a file or a database and ship independently of code.

It reuses the `txn` registry and its three rules (`is_safe` / `is_high_value` / `in_regions`) from the [Quick Start](../quick-start.md).

## Export a JSON Schema

`SchemaGenerator` reads the signatures of every atomic rule in a registry and builds a Pydantic model (the manifest model); `model_json_schema()` exports it as a standard JSON Schema:

```python
from predylogic import SchemaGenerator

Manifest = SchemaGenerator(txn).generate()

schema = Manifest.model_json_schema()  # a standard JSON Schema (dict)
```

The schema models each rule on its own (for example, `IsHighValueParams` describes `threshold: int`) and uses `rule_def_name` as the discriminator. Hand it to any JSON Schema validator, or a schema-aware editor, and you catch type mismatches or references to rules that don't exist while writing the config, not at runtime.

## Load rules from a manifest

Loading is three steps: register the registry with a `RegistryManager`, parse the config with the generated manifest model, hand it to a `RuleEngine`, then pull back an executable predicate handle.

!!! note "DSL config"

    Hand-writing a JSON AST is verbose. We're working on a more concise DSL config to replace raw JSON / YAML.

```python
from predylogic import RegistryManager, RuleEngine

config = """
{
  "registry": "txn",
  "rules": {
    "policy": {
      "node_type": "and",
      "rules": [
        {"node_type": "leaf", "rule": {"rule_def_name": "is_safe", "params": {}}},
        {"node_type": "or", "rules": [
          {"node_type": "leaf", "rule": {"rule_def_name": "is_high_value", "params": {"threshold": 2000}}},
          {"node_type": "leaf", "rule": {"rule_def_name": "in_regions", "params": {"regions": ["US", "EU"]}}}
        ]}
      ]
    }
  }
}
"""

# 1. parse and validate the config (config errors surface here)
manifest = Manifest.model_validate_json(config)

# 2. register the registry, load the manifest
manager = RegistryManager()
manager.add_register(txn)
engine = RuleEngine(manager)
engine.update_manifests(manifest)

# 3. pull back a predicate handle and call it like any predicate
policy = engine.get_predicate_handle("txn", "policy")

assert policy({"amount": 5000, "region": "JP", "is_fraud_flagged": False})
assert not policy({"amount": 500, "region": "US", "is_fraud_flagged": True})
```

This `policy` is exactly the one written with `&` / `|` in the [Quick Start](../quick-start.md). The config is just the data form of the same predicate tree.

## Manifest structure

A manifest looks like `{"registry": <name>, "rules": {<rule-name>: <node>}}`. `rules` is a DAG keyed by rule name; each node is tagged by `node_type`:

| `node_type` | Key fields | Meaning |
|---|---|---|
| `leaf` | `rule`: `{rule_def_name, params}` | a single atomic rule |
| `and` | `rules`: array of children (≥ 2) | all must pass |
| `or` | `rules`: array of children (≥ 2) | any must pass |
| `not` | `rule`: a single child | negation |
| `ref` | `ref_id`: another rule's name | references another rule in `rules` |

A leaf's `params` map one-to-one onto the atomic rule's signature: `is_safe` takes none, so `{}` (you can also omit it); `is_high_value`'s `threshold` and `in_regions`'s `regions` are given by name. `and` / `or` / `not` / `leaf` correspond to `all_of`, `any_of`, `~`, and a single atomic rule; `and` and `or` are flat N-ary nodes (two or more children), isomorphic to `all_of` / `any_of`.

`ref` lets one rule reference another, which is why `rules` is a DAG rather than an isolated tree. Referencing a rule that isn't defined yet doesn't fail immediately; you get a placeholder handle that resolves later. See [Hot Reloading](hot-reload.md).

## Validation and errors

predylogic prefers to fail early: errors it can catch at config time aren't deferred to runtime.

`model_validate_json` (config time) catches type mismatches (`threshold` as a string raises `int_parsing`), unknown rule names (a `rule_def_name` not in the registry raises `literal_error`), structural errors (extra fields, an `and` / `or` with fewer than two children, a node missing a field), and `ref` cycles (`RuleDefRingError`).

A few errors can only surface at load or runtime:

- At load, `update_manifests` raises `RegistryNotFoundError` if the config names a registry that isn't registered.
- Calling a handle that references a missing or revoked rule raises `RuleRevokedError` (see [Hot Reloading](hot-reload.md)).

## See also

- Swapping loaded rules at runtime without invalidating the handles callers hold: [Hot Reloading](hot-reload.md).
