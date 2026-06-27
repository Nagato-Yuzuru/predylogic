# Design & Architecture

Welcome to the architectural documentation of **Predylogic**. This section details the internal design decisions,
trade-offs, and performance considerations.

> **Heads up: The design notes here capture our thoughts during the early stages.
Please don't treat these APIs as the "source of truth"—they may have changed (or been scrapped) as we iterated.
Always refer to the API Reference for the latest updates.**

## Architecture Decision Records (ADR)

We use ADRs to document significant architectural changes.

* [ADR 001: Evaluation Engine Migration](adr/001_evaluation_engine.md) - Why we moved from Recursive Closures
  to an Iterative AST Engine.
* [ADR 002: AST compiler optimization](adr/002_AST_compiler_optimization.md) - What attempts have we made?
