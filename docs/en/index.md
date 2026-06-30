# predylogic

--8<-- "README.md:badges"

An embedded, composable, type-safe predicate logic engine.

## About the name

> predy (adj.) Archaic British. Nautical.
>
> 1. (of a ship) prepared or ready for sailing or action.
> 2. to make the ship ready for battle (e.g., "predy the decks").
>
> -- Collins English Dictionary

predylogic takes its name from predy: logic that isn't hardcoded into the flow of control, but defined, cleared, and made "predy" for execution. It's also a nod to **Pred**icate **Logic**.

## The problem: logic sprawl

Business rules rarely start out complex. You write one `if`. A few weeks later you add a branch. A quarter later that decision is spread across orders, fraud checks, and reporting, and nobody dares touch it.

The usual ways around this each cost you something:

- **Hardcoded `if/else`**: fastest to write, but logic and control flow are tangled. Changing one rule means changing code, a review, and a deploy; there's no runtime swap, and requirements tend to move faster than that release path.
- **Pushed into config (untyped JSON/YAML)**: looks flexible, but nothing validates it for you. A wrong type, or a reference to a rule that doesn't exist, only blows up at runtime. Give it time and the YAML grows its own interpreter. [Greenspun's tenth rule](https://en.wikipedia.org/wiki/Greenspun%27s_tenth_rule), again.
- **A heavyweight rule engine (Drools, OPA, and the like)**: capable, but you stand up a separate runtime, DSL, and deploy. For a few dozen rules, a JVM sidecar or an external service is overkill.

What I wanted was something you can change at runtime, that's type-safe, and that stays simple.

## Where predylogic fits

predylogic aims for those three. It splits logic in two: **what to check** lives in code, **how to combine it** lives in data.

Each atomic rule is a typed, pure Python function, like `is_vip` or `amount_gt`. The plan for combining them into a policy (AND / OR / NOT) is configuration. You can load it as data from outside (or compose existing rules the same way in code) and swap it at runtime without redeploying.

Config is validated against a schema and types, compiled to Python bytecode, and evaluated lazily. The whole engine runs in-process: no JVM, no sidecar.

## Example

```python
from typing import TypedDict

from predylogic import Registry


# A Pydantic model, dataclass, dict, or any valid Python type works
class Transaction(TypedDict):
    amount: int
    region: str
    is_fraud_flagged: bool


# Name the registry
txn = Registry[Transaction]("txn")


# 1. Define atomic rules: plain, typed, pure functions
@txn.rule_def()
def is_high_value(ctx: Transaction, threshold: int = 1000) -> bool:
    return ctx["amount"] >= threshold


@txn.rule_def()
def in_regions(ctx: Transaction, regions: list[str]) -> bool:
    return ctx["region"] in regions


@txn.rule_def()
def is_safe(ctx: Transaction) -> bool:
    return not ctx["is_fraud_flagged"]


# 2. Compose: safe AND (high value OR in region)
policy = is_safe() & (is_high_value(2000) | in_regions(["US", "EU"]))

# 3. Evaluate
res = policy({"amount": 5000, "region": "JP", "is_fraud_flagged": False})
assert res
```

Exporting a schema, loading from config, hot reloading, and Trace are all in the [Quick Start](quick-start.md).

## What's different

Pass `trace=True` and a single evaluation returns a result tree with the verdict of every atomic predicate. Turn off short-circuiting (`short_circuit=False`) and it runs every branch, telling you all the failing conditions at once instead of stopping at the first. Handy for audits, debugging, or listing everything a user got wrong in one pass. See [Tracing](guides/trace.md).

Trace is a separately compiled slow path, so with it off there's almost no overhead. Without trace, the predicate tree compiles to Python bytecode and runs native opcodes, close to a handwritten `and` / `or`. See [Design](design/index.md) for how.

## Next

- Want to use it → [Quick Start](quick-start.md)
- Looking by task → [Guides](guides/index.md)
- How it works → [Design & ADRs](design/index.md)
- The API → [Reference](reference.md)
