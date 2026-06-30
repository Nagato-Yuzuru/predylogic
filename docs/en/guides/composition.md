# Composition & Performance

predylogic gives you two ways to compose atomic rules into a predicate tree. They mean the same thing; they differ in build cost and readability. This reuses the rules from the [Quick Start](../quick-start.md).

## Two ways to compose

- **Operator overloads** `&` (and), `|` (or), `~` (not).
- **`all_of(...)` / `any_of(...)`**: take a sequence of predicates and build a flat N-ary node in one shot.

The two are equivalent and give the same result on any input:

```python
op = is_safe() & (is_high_value(2000) | in_regions(["US", "EU"]))
fn = all_of([is_safe(), any_of([is_high_value(2000), in_regions(["US", "EU"])])])
```

The difference is in building. `a & b & c ...` is a left-associative binary chain: each `&` allocates one binary node (O(1) each, O(N) for the chain). `all_of([...])` allocates from the list in one batch and states the intent ("all of these must hold") directly. For large homogeneous groups, especially ones loaded in bulk from config, `all_of` / `any_of` build more cheaply and read more clearly. For a handful of rules, pick whichever reads better.

## N-ary flattening

AND / OR are associative (they form a monoid), so nesting flattens at compile time: `all_of([a, all_of([b, c])])` is equivalent to `all_of([a, b, c])`, and both compile to **a single flat N-ary node** rather than nested binaries. The left-associative binary chain from `&` is collected into the same flat N-ary by the compiler.

This avoids deep-tree recursion and makes the runtime a single linear pass of `and` / `or`. See [ADR 002](../design/adr/002_AST_compiler_optimization.md) for the mechanism and benchmarks.

## The fast path: compiling to bytecode

The predicate tree isn't interpreted node by node. On the first call (the default case: short-circuit on, trace off) it compiles to Python bytecode, cached by `(trace, short_circuit, fail_skip)`; later calls run the cached bytecode directly as native opcodes (`JUMP_IF_FALSE` and friends), with overhead close to a handwritten `and` / `or`.

By ADR 002's CodSpeed benchmarks, the default mode runs within about 7% of native Python (`def`), and on deep chains (depth 1000) the build is even faster than handwritten. Turning on trace or off short-circuit takes a separate slow path; keep those off the fast path.

## When to care about performance

Most of the time you don't need to. Business rule sets are usually a dozen or so rules, and real evaluation is often I/O-bound (database lookups, fetching user profiles), so the engine's microsecond overhead is negligible next to network latency.

Reach for `all_of` / `any_of` when composing many homogeneous rules at once, especially when loading config in bulk — cheaper to build, clearer intent. Deep chains (hundreds or thousands of levels) are a stress test, not the norm; the engine handles arbitrary depth (iterative compilation, no recursion limit), but treat that as a reliability guarantee, not a daily need.
