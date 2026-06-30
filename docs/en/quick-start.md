# Quick Start

We'll walk through predylogic's core flow in a few minutes, using a small transaction-risk example:

- define atomic rules
- compose a policy
- evaluate
- read a Trace

Deeper usage is split across the [guides](guides/index.md).

## Installation

predylogic is on [PyPI](https://pypi.org/project/predylogic/). Install with pip:

```shell
pip install predylogic
```

Or with uv:

```shell
uv add predylogic
```

!!! note "Version"

    predylogic is at v0.x; breaking changes can land between minor versions.

## What you'll build

A transaction-risk policy: **safe AND (high value OR in a target region)**, i.e. `Safe AND (High Value OR In Region)`.

It breaks into three steps: define the smallest units of judgment (atomic rules), compose them into a policy, then evaluate against data.

## 1. Define atomic rules

An atomic rule is the smallest unit of judgment: a typed, pure function that takes a context and returns a `bool`. The `@registry.rule_def()` decorator turns it into a **rule factory**.

```python
from typing import TypedDict

from predylogic import Registry


# Context type: a TypedDict, dataclass, Pydantic model, or any valid type
class Transaction(TypedDict):
    amount: int
    region: str
    is_fraud_flagged: bool


# Name the registry and bind its context type
txn = Registry[Transaction]("txn")


@txn.rule_def()
def is_high_value(ctx: Transaction, threshold: int = 1000) -> bool:
    return ctx["amount"] >= threshold


@txn.rule_def()
def in_regions(ctx: Transaction, regions: list[str]) -> bool:
    return ctx["region"] in regions


@txn.rule_def()
def is_safe(ctx: Transaction) -> bool:
    return not ctx["is_fraud_flagged"]
```

A function decorated with `@registry.rule_def()` must take the registry's bound context type as its first parameter. Concretely, the expected signature is:

```python
# RunCtx_contra is the bound context, e.g. Transaction above
RunCtx_contra = TypeVar("RunCtx_contra", contravariant=True)
RuleParams = ParamSpec("RuleParams")

type RuleDef = Callable[Concatenate[RunCtx_contra, RuleParams], bool]
```

Calling `is_high_value(2000)` doesn't evaluate anything yet. It binds `threshold` up front and returns a single-argument predicate that takes only the context (currying / partial application). Configuration (`2000`) and logic (the comparison) are now separate, which is also why atomic rules can be tested as plain pure functions. More in [Composition & Performance](guides/composition.md) and [Design](design/index.md).

## 2. Compose a policy

Use `&` (and), `|` (or), `~` (not) to compose atomic rules into a predicate tree:

```python
policy = is_safe() & (is_high_value(2000) | in_regions(["US", "EU"]))
```

You can also use `all_of` / `any_of`. They're equivalent, and for large homogeneous groups the latter is cheaper, since it builds a flat N-ary node directly:

```python
from predylogic import all_of, any_of

policy = all_of(
    [
        is_safe(),
        any_of([is_high_value(2000), in_regions(["US", "EU"])]),
    ]
)
```

See [Composition & Performance](guides/composition.md) for the trade-off.

## 3. Evaluate

Evaluate against one record to get a `bool`:

```python
ok = {"amount": 5000, "region": "JP", "is_fraud_flagged": False}
bad = {"amount": 500, "region": "US", "is_fraud_flagged": True}

assert policy(ok)
assert not policy(bad)
```

On the first call the predicate tree compiles to Python bytecode and is cached; later calls take this fast path, with overhead close to a handwritten `and` / `or`. See [ADR 002](design/adr/002_AST_compiler_optimization.md) for how.

## 4. See the reasoning: Trace

Pass `trace=True` and evaluation returns a Trace tree instead of a `bool`, recording each node's verdict. Add `short_circuit=False` to evaluate every branch, so you see all the hits and misses at once:

```python
trace = policy(bad, trace=True, short_circuit=False)
print(trace)
```

```text
❌ AND
  ❌ is_safe
  ✅ OR
    ❌ is_high_value
    ✅ in_regions
```

Trace is a separately compiled slow path; it doesn't touch the fast path above. For render styles (`TraceStyle`) and logging, see [Tracing](guides/trace.md).

!!! note

    Trace is still evolving; more detail (such as a per-node context snapshot) will be added.

## Loading from config

Besides composing in code, a policy can be serialized to JSON (a rule AST) and loaded from config at runtime. That decouples logic from code and supports hot reloading without a redeploy. For the full flow (export a schema, then load and validate with `RuleEngine`), see [Schema & Serde](guides/serde.md).

!!! note "DSL config"

    Hand-writing a JSON AST is verbose. We're working on a more concise DSL config to replace raw JSON / YAML.

## Full example

The four steps as one runnable script:

```python
from typing import TypedDict

from predylogic import Registry, all_of, any_of


class Transaction(TypedDict):
    amount: int
    region: str
    is_fraud_flagged: bool


txn = Registry[Transaction]("txn")


@txn.rule_def()
def is_high_value(ctx: Transaction, threshold: int = 1000) -> bool:
    return ctx["amount"] >= threshold


@txn.rule_def()
def in_regions(ctx: Transaction, regions: list[str]) -> bool:
    return ctx["region"] in regions


@txn.rule_def()
def is_safe(ctx: Transaction) -> bool:
    return not ctx["is_fraud_flagged"]


# safe AND (high value OR in a target region)
policy = is_safe() & (is_high_value(2000) | in_regions(["US", "EU"]))

# evaluate
assert policy({"amount": 5000, "region": "JP", "is_fraud_flagged": False})
assert not policy({"amount": 500, "region": "US", "is_fraud_flagged": True})

# inspect the reasoning
trace = policy({"amount": 500, "region": "US", "is_fraud_flagged": True}, trace=True, short_circuit=False)
print(trace)
```

## Next

- Look up usage by task → [Guides](guides/index.md)
- How it works inside → [Design & ADRs](design/index.md)
- The API → [Reference](reference.md)
