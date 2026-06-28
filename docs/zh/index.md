# predylogic

--8<-- "README.md:badges"

嵌入式、可组合、类型安全的逻辑谓词引擎

## 关于名字

> predy (adj.) Archaic British. Nautical.
>
> 1. (of a ship) prepared or ready for sailing or action.
> 2. to make the ship ready for battle (e.g., "predy the decks").
>
> -- Collins English Dictionary

predylogic 的名字来源 predy。它表示不将逻辑 hardcode 在代码中，而是经过定义，并“预备”(predy)执行。

并且这也来自“谓词逻辑”（Predicate Logic）。

## 问题:逻辑蔓延(Logic Sprawl)

业务规则很少一开始就复杂。通常是先写一个 `if`。几周后加个分支。一个季度后这段判断已经散在订单、风控、报表三处，谁也不敢动。

绕开这种蔓延,常见的三条路各有代价:

- **硬编码 `if/else`**:写得最快，但逻辑和控制流缠在一起。改一条规则就得改代码、过 review、重新部署,没法在运行时热更换;需求变更往往比这条发布链路来得快。
- **塞进配置(无类型 JSON/YAML)**:看着灵活,实则没人替你校验。类型写错、引用一个不存在的规则,都要等运行时才炸;随着时间推移YAML里可能自己长出一个解释器。又一次对 [Greenspun 第十定律](https://en.wikipedia.org/wiki/Greenspun%27s_tenth_rule)验证。
- **上重型规则引擎(Drools、OPA 一类)**:能力够,但要搭一整套独立的运行时、DSL 和deploy。为几十条规则引入 JVM 旁路或外部服务,多半是杀鸡用牛刀。

我们希望(至少我希望)有一个运行时能改、类型安全、够简单的方法。

## 定位

predylogic 想要达成这三点。我们把逻辑拆成两层：**做什么**写在代码里，**怎么拼**写在数据里。

每条最小规则是一个带类型的纯 Python 函数，像 `is_vip`、`amount_gt` 这样的函数。它们组合成一条策略（AND / OR / NOT）的方案是一份配置，可以从外部以数据加载（也可以在代码中用类似的方法组合现有的规则），运行时换掉而不用重新部署。

配置按 schema 和类型校验，并编译为 python 字节码并惰性执行。整个引擎在进程内，没有 JVM、没有 sidecar。

## 示例


```python
from typing import TypedDict

from predylogic import Registry


# 可以使用 Pydantic model、dataclass、dict 或者任何合法的 python 类型
class Transaction(TypedDict):
    amount: int
    region: str
    is_fraud_flagged: bool


# 给 Registry 命名
txn = Registry[Transaction]("txn")


# 1. 定义原子规则：就是普通的、带类型的纯函数
@txn.rule_def()
def is_high_value(ctx: Transaction, threshold: int = 1000) -> bool:
    return ctx["amount"] >= threshold


@txn.rule_def()
def in_regions(ctx: Transaction, regions: list[str]) -> bool:
    return ctx["region"] in regions


@txn.rule_def()
def is_safe(ctx: Transaction) -> bool:
    return not ctx["is_fraud_flagged"]


# 2. 组合：安全,且(高额 或 命中地区)
policy = is_safe() & (is_high_value(2000) | in_regions(["US", "EU"]))

# 3. 执行
res = policy({"amount": 5000, "region": "JP", "is_fraud_flagged": False})
assert res

```

导出 schema、从配置加载、热更新、Trace 追踪,完整教程见[快速开始](quick-start.md)。

## 关键差异

- **可审计的 Trace**。允许在求值时配置 `trace=True`，一次求值返回一棵结果树，结果树包含每个原子谓词的判定结果。再关掉短路（`short_circuit=False`），它会把所有分支跑完，一次告诉你哪些条件不满足，而不是碰到第一个不成立就停。在审计、排查，或者一次把所有不满足的条件列给用户都可以使用。详见 [Trace 追踪](guides/trace.md)。
- *Trace 是特化编译出来的，*不开启几乎没有额外性能开销。trace 会单独编译的慢路径；不开 trace 时，谓词树编译成 Python 字节码，跑原生 opcode，接近手写的 `and` / `or`。原理见[设计](design/index.md)。

## 下一步

- 想直接用 → [快速开始](quick-start.md)
- 按任务查 → [指南](guides/index.md)
- 想看原理 → [设计与 ADR](design/index.md)
- 查 API → [API 参考](reference.md)
