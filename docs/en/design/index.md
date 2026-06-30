# Design & architecture

> The design notes here reflect early-iteration thinking; the API may have changed (or been dropped). The [API Reference](../reference.md) is the source of truth for current interfaces.

This section records why predylogic is built the way it is, and the trade-offs behind it.

## ADRs

We record significant architectural changes as ADRs:

- [ADR 001: Evaluation Engine](adr/001_evaluation_engine.md) — why we moved from closure recursion to an iterative AST engine.
- [ADR 002: AST Compiler Optimization](adr/002_AST_compiler_optimization.md) — the compiler optimizations we tried, and the final benchmarks.
