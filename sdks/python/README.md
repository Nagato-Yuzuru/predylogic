[中文](README.zh.md) | English

# predylogic

<!-- Single source of truth for badges. The docs homepages (docs/en/index.md,
     docs/zh/index.md) transclude this block via pymdownx.snippets:
     `--8<-- "README.md:badges"`. The marker comments are invisible on
     PyPI/GitHub. Edit badges here only. -->
<!-- --8<-- [start:badges] -->
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![CodSpeed](https://img.shields.io/endpoint?url=https://codspeed.io/badge.json)](https://codspeed.io/Nagato-Yuzuru/predylogic?utm_source=badge)
[![codecov](https://codecov.io/gh/Nagato-Yuzuru/predylogic/branch/main/graph/badge.svg)](https://codecov.io/gh/Nagato-Yuzuru/predylogic)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/predylogic)](https://pypi.org/project/predylogic/)

[![PyPI - Status](https://img.shields.io/pypi/status/predylogic)](https://pypi.org/project/predylogic/)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/Nagato-Yuzuru/predylogic/python-ci.yml)
[![Docs](https://img.shields.io/github/actions/workflow/status/Nagato-Yuzuru/predylogic/publish-docs.yml?label=docs)](https://nagato-yuzuru.github.io/predylogic)
[![Commit activity](https://img.shields.io/github/commit-activity/m/Nagato-Yuzuru/predylogic)](https://img.shields.io/github/commit-activity/m/Nagato-Yuzuru/predylogic)
[![License](https://img.shields.io/github/license/Nagato-Yuzuru/predylogic)](https://github.com/Nagato-Yuzuru/predylogic)
<!-- --8<-- [end:badges] -->

An embedded, composable, type-safe predicate logic engine for Python.

> v0.x; breaking changes can land between minor versions.

---

Business rules rarely start out complex. You write one `if`. A few weeks later you add a branch. A quarter later that decision is spread across orders, fraud checks, and reporting, and nobody dares touch it. Changing one threshold means a code change, a review, and a deploy.

predylogic splits logic in two: **what to check** lives in code, **how to combine it** lives in data. Policies can be loaded from config, swapped at runtime, and every evaluation can be traced:

```
❌ AND
  ❌ is_safe
  ✅ OR
    ❌ is_high_value
    ✅ in_regions
```

## Install

```shell
pip install predylogic
# or
uv add predylogic
```

## Example

```python
from typing import TypedDict
from predylogic import Registry

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

assert policy({"amount": 5000, "region": "JP", "is_fraud_flagged": False})

# inspect the reasoning
bad = {"amount": 500, "region": "US", "is_fraud_flagged": True}
trace = policy(bad, trace=True, short_circuit=False)
print(trace)
```

```
❌ AND
  ❌ is_safe
  ✅ OR
    ❌ is_high_value
    ✅ in_regions
```

`trace=True` switches the return value from `bool` to a result tree recording each node's verdict. `short_circuit=False` runs every branch so you see all the hits and misses at once — useful for compliance audits, debugging, or listing everything a user got wrong in one pass. The trace path is compiled separately, so leaving it off costs nothing.

Policies can also be loaded from JSON config and hot-reloaded at runtime without a restart. See [Schema & Serde](https://nagato-yuzuru.github.io/predylogic/guides/serde/) and [Hot Reloading](https://nagato-yuzuru.github.io/predylogic/guides/hot-reload/).

## Why not X?

The common alternatives each cost something.

- Hardcoded `if/else` is the fastest to write, but logic and control flow get tangled — changing one threshold means a code change, a PR, and a redeploy; there is no runtime swap.
- Untyped JSON/YAML looks flexible but nothing validates it: a wrong type or a reference to a rule that doesn't exist only blows up at runtime. Give it time and the YAML grows its own interpreter. [Greenspun's tenth rule](https://en.wikipedia.org/wiki/Greenspun%27s_tenth_rule), again.
- A heavyweight rule engine like Drools or OPA is capable, but you stand up a separate runtime, DSL, and deploy pipeline. For a few dozen rules, that's overkill.

predylogic runs in-process — no JVM, no sidecar. Atomic rules are plain Python functions you can test in isolation. Config is validated against a schema, so type mismatches and unknown rule names surface at config time, not runtime.

## Performance

On the default path (short-circuit on, Trace off) the predicate tree compiles to Python bytecode and is cached. Runtime overhead lands within 7% of native Python — close to a handwritten `and` / `or`. See [ADR 002](docs/en/design/adr/002_AST_compiler_optimization.md) for benchmarks.

## Docs

Full guides, API reference, and design notes: [nagato-yuzuru.github.io/predylogic](https://nagato-yuzuru.github.io/predylogic/)

---

## About the name

> **predy** (adj.) *Archaic British. Nautical.*
>
> 1. (of a ship) prepared or ready for sailing or action.
> 2. to make the ship ready for battle (e.g., "predy the decks").
>
> — *Collins English Dictionary*

predylogic takes its name from predy: logic that isn't hardcoded into the flow of control, but defined, cleared, and made "predy" for execution. It's also a nod to **Pred**icate **Logic**.
