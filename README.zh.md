[English](README.md) | 中文

# predylogic

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![CodSpeed](https://img.shields.io/endpoint?url=https://codspeed.io/badge.json)](https://codspeed.io/Nagato-Yuzuru/predylogic?utm_source=badge)
[![codecov](https://codecov.io/gh/Nagato-Yuzuru/predylogic/branch/main/graph/badge.svg)](https://codecov.io/gh/Nagato-Yuzuru/predylogic)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/predylogic)](https://pypi.org/project/predylogic/)

[![PyPI - Status](https://img.shields.io/pypi/status/predylogic)](https://pypi.org/project/predylogic/)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/Nagato-Yuzuru/predylogic/python-ci.yml)
[![Docs](https://img.shields.io/github/actions/workflow/status/Nagato-Yuzuru/predylogic/publish-docs.yml?label=docs)](https://nagato-yuzuru.github.io/predylogic/zh/)
[![Commit activity](https://img.shields.io/github/commit-activity/m/Nagato-Yuzuru/predylogic)](https://img.shields.io/github/commit-activity/m/Nagato-Yuzuru/predylogic)
[![License](https://img.shields.io/github/license/Nagato-Yuzuru/predylogic)](https://github.com/Nagato-Yuzuru/predylogic)

嵌入式、可组合、类型安全的 Python 谓词逻辑引擎。

> v0.x 阶段，minor 版本之间可能有破坏性变更。

______________________________________________________________________

业务规则很少一开始就复杂。先是一个 `if`，几周后多个分支，一个季度后这段判断已经散在订单、风控、报表三处，谁也不敢动。改一个阈值要改代码、过 review、重新部署。

predylogic 把逻辑拆成两层：**做什么**写在代码里，**怎么拼**写在数据里。策略可以从配置加载、运行时热换，求值结果可以完整追踪：

```
❌ AND
  ❌ is_safe
  ✅ OR
    ❌ is_high_value
    ✅ in_regions
```

## 安装

```shell
pip install predylogic
```

推荐使用uv

```shell
uv add predylogic
```

## 示例

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

# 安全 且（高额 或 命中地区）
policy = is_safe() & (is_high_value(2000) | in_regions(["US", "EU"]))

assert policy({"amount": 5000, "region": "JP", "is_fraud_flagged": False})

# 查看每一步的判定结果
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

`trace=True` 把返回值从 `bool` 换成结果树，记录每个节点的判定。`short_circuit=False` 关掉短路、跑完所有分支——一次就能看清哪些条件没通过，适合合规审计、排查逻辑问题，或者直接把失败原因展示给用户。不开 Trace 时没有这层开销，两条路径独立编译，互不影响。

策略也可以从 JSON 配置加载，支持运行时热更新。详见[Schema 与序列化](https://nagato-yuzuru.github.io/predylogic/zh/guides/serde/)和[热更新](https://nagato-yuzuru.github.io/predylogic/zh/guides/hot-reload/)。

## 和其他方案比

常见的三条路各有代价。

- 硬编码 `if/else` 写得快，但逻辑和控制流缠在一起，改一个阈值就要改代码、过 review、重新部署，没法在运行时换。
- 无类型 JSON/YAML 看着灵活，实则没人替你校验，类型写错、引用一个不存在的规则，都要等运行时才炸——时间一长 YAML 里可能自己长出一个解释器，又一次验证 [Greenspun 第十定律](https://en.wikipedia.org/wiki/Greenspun%27s_tenth_rule)。
- Drools、OPA 一类的重型引擎，要搭一整套独立的运行时和 DSL；为几十条规则引入 JVM 或旁路，多半是杀鸡用牛刀。

predylogic 在进程内运行，没有 JVM、没有 sidecar。原子规则是普通 Python 函数，配置按 schema 校验——类型写错、规则名打错，配置时就报，不会等到运行时。

## 性能

默认路径（开启短路、关闭 Trace）把谓词树编译为 Python 字节码并缓存。运行时开销落在原生 Python 的 7% 以内，接近手写的 `and` / `or`。详见 [ADR 002](docs/zh/design/adr/002_AST_compiler_optimization.md)。

## 文档

完整教程、API 参考、设计说明：[nagato-yuzuru.github.io/predylogic/zh](https://nagato-yuzuru.github.io/predylogic/zh/)

______________________________________________________________________

## 关于名字

> **predy** (adj.) *Archaic British. Nautical.*
>
> 1. (of a ship) prepared or ready for sailing or action.
> 2. to make the ship ready for battle (e.g., "predy the decks").
>     — *Collins English Dictionary*

predylogic 的名字来自 predy：逻辑不硬编码在控制流里，而是经过定义、"预备"（predy）好随时执行。同时也是"谓词逻辑"（Predicate Logic）的双关。
