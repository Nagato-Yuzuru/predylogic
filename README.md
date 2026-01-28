# PredyLogic

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![CodSpeed](https://img.shields.io/endpoint?url=https://codspeed.io/badge.json)](https://codspeed.io/Nagato-Yuzuru/predylogic?utm_source=badge)

![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/Nagato-Yuzuru/predylogic/python-ci.yml)
[![Release](https://img.shields.io/github/v/release/Nagato-Yuzuru/predylogic)](https://img.shields.io/github/v/release/Nagato-Yuzuru/predylogic)
[![codecov](https://codecov.io/gh/Nagato-Yuzuru/predylogic/branch/main/graph/badge.svg)](https://codecov.io/gh/Nagato-Yuzuru/predylogic)
[![Commit activity](https://img.shields.io/github/commit-activity/m/Nagato-Yuzuru/predylogic)](https://img.shields.io/github/commit-activity/m/Nagato-Yuzuru/predylogic)
[![License](https://img.shields.io/github/license/Nagato-Yuzuru/predylogic)](https://img.shields.io/github/license/Nagato-Yuzuru/predylogic)

An embedded, composable schema-driven predicate logic engine.


> **Inspiration:** Heavily inspired by the architectural concepts discussed
> by [ArjanCodes](https://www.youtube.com/watch?v=KqfMiuL3cx4).

## About Name

> **predy** (adj.) *Archaic British. Nautical.*
> 1. (of a ship) prepared or ready for sailing or action.
> 2. to make the ship ready for battle (e.g., "predy the decks").
     > — *Collins English Dictionary*

**predylogic** takes its name from this concept. It represents logic that is not hardcoded into the flow of battle, but
defined, cleared for action, and "predy" for execution.

It also serves as a nod to **Pred**icate **Logic**.

## Overview

**predylogic** is a headless, composable predicate logic engine for Python.

It decouples business logic from control flow by treating rules as data, not code blocks. Unlike heavy-weight rule
engines (e.g., Drools) or simple `if/else` spaghetti, predylogic sits in the middle: it offers **strong type safety**, *
*zero external dependencies**, and **deferred execution**.

It represents the shift from **imperative** control flow (hardcoded `if/else` checks) to **declarative** predicate
definitions. The goal is to make logic "ready" (predy) for serialization, composition, and reuse.

Designed for developers who need to define rules in Python, serialize them (planned), and execute them against strict
data contexts.

## Core Philosophy

* **Functional & Pure:** Built on Functional Programming principles. Predicates are **pure functions** (no side effects)
  that can be composed using standard combinators.
* **Type Safety First:** Leveraging generics to ensure your rules match your data schema at
  static analysis time.
* **Composition over Inheritance:** Complex rules are just trees of simple atomic predicates combined with `&` (AND),
  `|` (OR), and `~` (NOT).
* **Headless:** No API server, no dashboard, no sidecars. Just a library.

## Quick Start

Define your context, register atomic predicates, and compose them using standard bitwise operators.

```python
from typing import TypedDict
from predylogic import Registry, rule_def


# 1. Define the Context (or Protocol or Pydantic BaseModel, or any other type)
class UserCtx(TypedDict):
    age: int
    is_active: bool
    role: str


# 2. Initialize Registry
registry = Registry[UserCtx]("my_first_registry")


# 3. Define Atomic Predicates
@rule_def(registry)
def is_adult(ctx: UserCtx, threshold: int = 18) -> bool:
    return ctx["age"] >= threshold


@rule_def(registry)
def has_role(ctx: UserCtx, role: str) -> bool:
    return ctx["role"] == role


# 4. Compose Logic (Deferred Execution)
# This creates a rule object, it does not execute yet.
access_policy = is_adult(18) & has_role("admin")

# 5. Execute
user = {"age": 20, "is_active": True, "role": "admin"}
assert access_policy(user) is True
```

## Roadmap

- [ ] v0.0.1 (Current): Core predicate logic, registry system, and type-safe rule definitions.

- [ ] v0.0.2: Schema generation and JSON-based configuration builder.

- [ ] v0.0.3: CLI tools for exporting logic schemas and validation.

- [ ] v0.1.0: First stable release.
