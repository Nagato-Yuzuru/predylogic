# 快速开始

我们用一个交易风控的小例子，在几分钟内走完 predylogic 的核心流程：

- 定义原子规则
- 组合成策略
- 求值
- 查看 Trace。

更深入的用法分流到各篇[指南](guides/index.md)。

## 安装

predylogic 已发布到 [ PyPI ](https://pypi.org/project/predylogic/)，用 pip 安装：

```shell
pip install predylogic
```

推荐使用 uv：

```shell
uv add predylogic
```

!!! note "版本"

    当前处于 v0.x，minor 版本之间可能出现破坏性变更。

## 你将构建什么

本教程构建一条交易风控策略：**安全 并且 （高额 或 命中目标地区）**，对应布尔表达式 `Safe AND (High Value OR In Region)`。

下面把它拆成三步：先定义判断的最小单元（原子规则），再把它们组合成策略，最后对数据求值。

## 1. 定义原子规则

原子规则是判断的最小单元。一个带类型的纯函数：接收上下文，返回 `bool`。用 `@registry.rule_def()` 装饰后，它变成一个**规则工厂**。

```python
from typing import TypedDict

from predylogic import Registry


# 上下文类型:TypedDict / dataclass / Pydantic 模型 / 任意合法类型均可
class Transaction(TypedDict):
    amount: int
    region: str
    is_fraud_flagged: bool


# 给 Registry 命名,并绑定上下文类型
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
```

被 `@registry.rule_def()` 装饰的函数要求第一个参数是Registry绑定的上下文类型。技术上来说，需要

```python
# 即上文的 Transaction
RunCtx_contra = TypeVar("RunCtx_contra", contravariant=True)
RuleParams = ParamSpec("RuleParams")

type RuleDef = Callable[Concatenate[RunCtx_contra, RuleParams], bool]
```

调用 `is_high_value(2000)` 不会立即求值，而是把参数 `threshold` 预先绑定，返回一个只接收上下文的单参谓词（currying / 偏应用）。配置（`2000`）与逻辑（比较）就此分离，原子规则因此可以作为纯函数单独测试。细节见[组合与性能](guides/composition.md)与[设计](design/index.md)。

## 2. 组合成策略

用 `&`（与）、`|`（或）、`~`（非）把原子规则组合成一棵谓词树：

```python
policy = is_safe() & (is_high_value(2000) | in_regions(["US", "EU"]))
```

也可以用 `all_of` / `any_of`，两种写法等价；在大量同构组合时后者更高效（编译期展平成扁平 N-ary）：

```python
from predylogic import all_of, any_of

policy = all_of(
    [
        is_safe(),
        any_of([is_high_value(2000), in_regions(["US", "EU"])]),
    ]
)
```

两者的取舍见[组合与性能](guides/composition.md)。

## 3. 执行

对一条数据求值，得到 `bool`：

```python
ok = {"amount": 5000, "region": "JP", "is_fraud_flagged": False}
bad = {"amount": 500, "region": "US", "is_fraud_flagged": True}

assert policy(ok)
assert not policy(bad)
```

> 首次调用时，谓词树会编译成 Python 字节码并缓存；之后的调用走这条快路径，开销接近手写的 `and` / `or`。原理见 [ADR 002](design/adr/002_AST_compiler_optimization.md)。

## 4. 看清过程：Trace

传入 `trace=True`，求值返回一棵 Trace 树而非 `bool`，记录每个节点的判定结果。再设 `short_circuit=False` 关闭短路，让所有分支都被求值，从而一次看清全部命中与未命中：

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

Trace 是特化编译的慢路径，不影响上面的快路径。渲染样式（`TraceStyle`）与日志对接见[Trace 追踪](guides/trace.md)。

!!! note

    Trace 仍在迭代中，后续会补充更多信息（如各节点的上下文快照）。

## 从配置导入

除了在代码里组合，策略也可以序列化为 JSON（一棵规则 AST），在运行时从配置加载，从而把逻辑与代码解耦、支持热更新而无需重新部署。完整流程（导出 schema、用 `RuleEngine` 装载并校验）见[Schema 与序列化](guides/serde.md)。

!!! note "DSL 配置"

    手写 JSON AST 较为冗长；我们正在推进一套更简洁的 DSL 配置，用于替代原始 JSON / YAML。

## 完整示例

把上面四步合成一段可直接运行的代码：

```python
from typing import TypedDict

from predylogic import Registry, all_of, any_of


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


# 安全,且(高额 或 命中目标地区)
policy = is_safe() & (is_high_value(2000) | in_regions(["US", "EU"]))

# 求值
assert policy({"amount": 5000, "region": "JP", "is_fraud_flagged": False})
assert not policy({"amount": 500, "region": "US", "is_fraud_flagged": True})

# 查看过程
trace = policy({"amount": 500, "region": "US", "is_fraud_flagged": True}, trace=True, short_circuit=False)
print(trace)
```

## 下一步

- 按任务查用法 → [指南](guides/index.md)
- 了解内部原理 → [设计与 ADR](design/index.md)
- 查具体 API → [API 参考](reference.md)
