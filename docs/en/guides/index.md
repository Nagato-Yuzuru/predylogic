# Guides

The guides are task-oriented how-tos, one topic each. Each assumes you've read the [Quick Start](../quick-start.md), so reach for them as needed.

Pick by task:

- **[Schema & Serde](serde.md)** — export a JSON Schema from a registry, load rules from a manifest, and validate at config time.
- **[Hot Reloading](hot-reload.md)** — swap predicate logic at runtime: `PredicateHandle`, tombstones, and concurrency guarantees.
- **[Tracing](trace.md)** — customize `TraceStyle`, wire Trace into your logging, and control evaluation with `short_circuit`.
- **[Composition & Performance](composition.md)** — `&` `|` `~` vs `all_of` / `any_of`, N-ary flattening, and the bytecode fast path.
