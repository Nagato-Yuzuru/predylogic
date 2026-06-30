# Tracing

Trace shows you why a rule passed or failed: one evaluation returns a result tree recording each node's verdict. It's a separately compiled slow path and doesn't affect the default fast path (see [Composition & Performance](composition.md)).

This guide reuses the `policy` and its three rules from the [Quick Start](../quick-start.md).

## Turning Trace on

Pass `trace=True` and the return value goes from a `bool` to a `Trace`. A `Trace` still works as a boolean (`bool(trace)` equals the overall result), but it also carries each node's verdict:

```python
policy = is_safe() & (is_high_value(2000) | in_regions(["US", "EU"]))
bad = {"amount": 500, "region": "US", "is_fraud_flagged": True}

trace = policy(bad, trace=True)
print(bool(trace))  # False, same as evaluating without trace
print(trace)
```

```text
❌ AND
  ❌ is_safe
```

Short-circuiting is on by default, so the tree stops at the first node that decides the result: `is_safe` is false, the AND is settled, and the OR branch isn't evaluated.

## Reading the Trace tree

Turn off short-circuiting (`short_circuit=False`) and every branch is evaluated, so you see all the hits and misses at once:

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

A few notes:

- Icons: `✅` passed, `❌` failed, `⏭️` skipped (below).
- AND / OR are **flat N-ary nodes**, not nested binary ones, matching the N-ary flattening done at compile time (see [Composition & Performance](composition.md)).
- The default renderer currently expands `Context` and error details only for skipped nodes; ordinary nodes show just the verdict.

## Skipping failing rules: fail_skip

Pass `fail_skip=(SomeError, ...)` and a rule that raises one of those exceptions is **skipped** rather than crashing the whole evaluation. A skipped leaf falls back to the value that doesn't change its parent's result (here, `True` under AND), and shows up as `⏭️` in the trace, with the context and exception attached:

```python
@txn.rule_def()
def risky(ctx: Transaction) -> bool:
    raise ValueError("boom")


policy2 = risky() & is_safe()
ok = {"amount": 5000, "region": "JP", "is_fraud_flagged": False}

print(policy2(ok, fail_skip=(ValueError,)))  # True: risky is skipped, result decided by is_safe
print(policy2(ok, trace=True, short_circuit=False, fail_skip=(ValueError,)))
```

```text
✅ AND
  ⏭️  risky
    └─ Context: {'amount': 5000, 'region': 'JP', 'is_fraud_flagged': False}
    💥 Error: ValueError('boom')
  ✅ is_safe
```

`fail_skip` works without trace too (you just don't get a tree); use it to tolerate a rule's transient failure.

## Customizing TraceStyle

Rendering is decided by a `TraceStyle`: a protocol whose only requirement is `render(self, trace, level=0) -> str`. Render the result tree with your own style to change the output, for example to wire it into logging or a frontend:

```python
from predylogic.trace import Trace


class FlatStyle:
    def render(self, trace: Trace, level: int = 0) -> str:
        pad = "  " * level
        name = (trace.node.desc or trace.node.name) if trace.node else trace.operator.upper()
        head = f"{pad}{'PASS' if trace.success else 'FAIL'} {name}"
        return "\n".join([head, *(self.render(c, level + 1) for c in trace.children)])


trace = policy(bad, trace=True, short_circuit=False)
print(FlatStyle().render(trace))
```

```text
FAIL AND
  FAIL is_safe
  PASS OR
    FAIL is_high_value
    PASS in_regions
```

Fields you can read while rendering: `success` (the verdict), `operator` (`and` / `or` / `not` / `leaf` / `SKIP`), `children`, `node` (the original predicate, with `name` / `desc`), `value` (the context, filled only on skip / failure), and `error`.

## Wiring Trace into logging

A `Trace` is an ordinary object. Walk its `children` to pull out structured fields and write them to your structured log. This is what "auditable" means here: recording the full reasoning path of a decision, not just the final `bool`.

!!! note

    Trace is still evolving; more detail (such as a per-node context snapshot) will be added. For custom rendering, call `style.render(trace)` directly.
