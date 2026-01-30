# PredyLogic

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![CodSpeed](https://img.shields.io/endpoint?url=https://codspeed.io/badge.json)](https://codspeed.io/Nagato-Yuzuru/predylogic?utm_source=badge)
[![codecov](https://codecov.io/gh/Nagato-Yuzuru/predylogic/branch/main/graph/badge.svg)](https://codecov.io/gh/Nagato-Yuzuru/predylogic)

![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/Nagato-Yuzuru/predylogic/python-ci.yml)
[![Docs](https://img.shields.io/github/actions/workflow/status/Nagato-Yuzuru/predylogic/publish-docs.yml?label=docs)](https://nagato-yuzuru.github.io/predylogic)
[![Release](https://img.shields.io/github/v/release/Nagato-Yuzuru/predylogic)](https://img.shields.io/github/v/release/Nagato-Yuzuru/predylogic)
[![Commit activity](https://img.shields.io/github/commit-activity/m/Nagato-Yuzuru/predylogic)](https://img.shields.io/github/commit-activity/m/Nagato-Yuzuru/predylogic)
[![License](https://img.shields.io/github/license/Nagato-Yuzuru/predylogic)](https://img.shields.io/github/license/Nagato-Yuzuru/predylogic)

An embedded, composable schema-driven predicate logic engine.


> **Inspiration:** Heavily inspired by the architectural concepts discussed
> by [ArjanCodes](https://www.youtube.com/watch?v=KqfMiuL3cx4).

## About Name

> **predy** (adj.) *Archaic British. Nautical.*
>1. (of a ship) prepared or ready for sailing or action.
>2. to make the ship ready for battle (e.g., "predy the decks").\
     — *Collins English Dictionary*

**predylogic** takes its name from this concept. It represents logic that is not hardcoded into the flow of battle, but
defined, cleared for action, and "predy" for execution.

It also serves as a nod to **Pred**icate **Logic**.

## Overview

**predylogic** is a headless, composable predicate logic engine for Python.

It decouples business logic from control flow by treating rules as data, not code blocks. Unlike heavy-weight rule
engines (e.g., Drools OAP ) or simple `if/else` spaghetti, predylogic sits in the middle: it offers **strong type
safety**, *
*zero external dependencies**, and **deferred execution**.

It represents the shift from **imperative** control flow (hardcoded `if/else` checks) to **declarative** predicate
definitions. The goal is to make logic "ready" (predy) for serialization, composition, and reuse.

Designed for developers who need to define rules in Python, serialize them (planned), and execute them against strict
data contexts.

## Why PredyLogic?

Applications often struggle with "Logic Sprawl":

1. **Hardcoded `if/else**`: Fast but rigid. Changing logic requires code deployment.
2. **Configuration Spaghetti**: JSON/YAML files that are untyped, hard to validate, and impossible to debug.
   (Then it becomes a demonstration
   of [Greenspun's tenth rule](https://en.wikipedia.org/wiki/Greenspun%27s_tenth_rule).)
3. **Heavy Rule Engines**: Overkill solutions (Java-based or OPA like) that introduce significant latency and
   infrastructure complexity.

**PredyLogic** bridges the gap. It adopts a **Hybrid Architecture**:

* **Define in Code**: Atomic logic (the "What") is written as pure, testable Python functions.
* **Compose in Data**: Logic flow (the "How") is structured as data, loaded dynamically, and compiled at runtime.

It provides the flexibility of a rule engine with the performance of native code.

## Key Features

* **Zero Infrastructure Dependencies**: No JVM, no sidecars, no external API servers. It runs entirely in-process using
  the modern Python stack.
* **Native-Level Performance**: Rules are not interpreted step-by-step; they are **compiled** into flat Python bytecode.
  The abstraction cost is near-zero (comparable to handwritten code).
* **Atomic Rule Factories**: Define your basic building blocks (`is_vip`, `amount_gt`) as plain Python functions.
  Compose them dynamically from configuration files without changing code.
* **Schema-Driven Validation**: Export a dynamic JSON Schema from your registry to validate your rule configurations.
  Catch logic errors (e.g., passing a string to an integer field, using a non-existent rule definition.) at config
  time, not runtime.
* **Audit-Ready Execution**: Logic is no longer a black box. Trace every decision path to understand exactly *why* a
  rule matched or failed (e.g., for compliance or debugging).

## Quick Start

1. Define what can be checked. These are your stable building blocks.
    ```python
    from typing import TypedDict
    from predylogic import Registry, Predicate


    # 1. Define the Context (Protocol or dataclass or Pydantic BaseModel, or any other type)
    class Transaction(TypedDict):
        amount: int
        region: str
        is_fraud_flagged: bool

    # 2. Initialize Registry
    registry = Registry[Transaction]("transaction_rules")


    # 3. Define Atomic Predicates
    @registry.rule_def()
    def is_high_value(ctx: Transaction, threshold: int = 1000) -> bool:
        return ctx["amount"] >= threshold

    # Define aliases using parameter
    @registry.rule_def("check_region")
    def in_regions(ctx: Transaction, regions: list[str]) -> bool:
        return ctx["region"] in regions

    @registry.rule_def()
    def is_safe(ctx: Transaction) -> bool:
        return not ctx["is_fraud_flagged"]
    ```

2. Dynamic Composition (Simulation)
   > In a real app, this structure would be loaded from a JSON/YAML file or from database. Here we construct it to show
   > the API.

    ```python
    # Rule: "Safe AND (High Value OR In Target Region)"
    # This structure validates against the schema derived from the registry.
    policy = Predicate.all([
        is_safe(),
        Predicate.any([
            is_high_value(2000),
            in_regions(["US", "EU"])
        ])
    ])
    # The 'policy' object is now compiled and ready for hot-loop execution.
    ```
3. Execution & Trace
    ```python
    tx_data = {"amount": 500, "region": "US", "is_fraud_flagged": True}

    # Execute (Fast Path)
    assert policy(tx_data) is False

    # Execute with Audit Log (Slow Path)
    trace = policy(tx_data, trace=True, short_circuit=False)
    assert not policy(tx_data)
    print(trace)
    # >>> Output:
    # ❌ AND
    #  ❌ is_safe
    #    └─ Context: {'amount': 500, 'region': 'US', 'is_fraud_flagged': True}
    #  ✅ OR
    #    ❌ is_high_value
    #      └─ Context: {'amount': 500, 'region': 'US', 'is_fraud_flagged': True}
    #    ✅ in_regions
    ```
   > NOTE: The trace functionality is currently undergoing iteration. Additional information will be incorporated.
   > You can customize the `TraceStyle` to fit your logging system.


## Under the Hood: The Engineering

PredyLogic is not just a collection of helper functions; it is a domain-specific language (DSL) compiler built on strict
computer science principles.

### 1. Algebraic Structures (Monoids)

Boolean operators (`AND`, `OR`) form a **Monoid**. They are associative (`(A & B) & C == A & (B & C)`) and have an
identity element (`True` for AND, `False` for OR).
We leverage this mathematical property to perform **AST Flattening**. A deeply nested tree of binary operations (depth
2000+)
is algebraically reduced to a single N-ary operation during the compilation phase, enabling stack usage at runtime.

### 2. Embedded JIT Compilation

Instead of interpreting the rule tree recursively (which is slow and stack-limited), PredyLogic acts as an embedded
compiler.

* **AOT Construction**: Rule definitions are validated and constructed as data structures.
* **JIT Compilation**: Upon the first execution (or explicit compilation), the object tree is transformed into Python's
  native
  `ast` (Abstract Syntax Tree) and compiled into raw bytecode.
  This means your logic runs at the speed of native Python opcodes (`JUMP_IF_FALSE`, etc.), bypassing the overhead of
  function calls and object dispatch.

### 3. Type Theory (Contravariance)

The `Predicate[T]` type is **contravariant** in `T`.

This ensures strict type safety in a polymorphic context: A rule expecting a generic `Transaction` context can safely
handle a more specific `FraudTransaction` context, but not vice versa.

This prevents runtime `AttributeError` by catching schema mismatches
during static analysis (MyPy/Pyright/ty).

### 4. Partial Application (Currying)

The engine strictly separates **Logic** from **Configuration** via **Partial Application**.

When you invoke a rule factory like `is_high_value(threshold=1000)`, you are binding the parameters (Configuration) to
the function (Logic) *before* execution.
This transforms a generic multi-argument function into a specialized single-argument predicate (`CTX -> bool`).

**This makes testing trivial: since your atomic rule definitions are typically pure functions, you can verify complex
business logic with simple unit tests—no mocks,
no fixtures, and no database required.**
