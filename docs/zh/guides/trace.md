# Trace 追踪

Trace 让你看清「为什么这条规则命中或失败」：一次求值返回一棵结果树，记录每个节点的判定。它是单独编译的慢路径，不影响默认的快路径（见[组合与性能](composition.md)）。

本页沿用[快速开始](../quick-start.md)里的 `policy` 及其三条规则。

## 开启 Trace

调用时传 `trace=True`，返回值就从 `bool` 变成一棵 `Trace`。`Trace` 仍可当布尔用——`bool(trace)` 等于整体结果——但额外带着每个节点的判定：

```python
policy = is_safe() & (is_high_value(2000) | in_regions(["US", "EU"]))
bad = {"amount": 500, "region": "US", "is_fraud_flagged": True}

trace = policy(bad, trace=True)
print(bool(trace))  # False —— 与不带 trace 的求值结果一致
print(trace)
```

```text
❌ AND
  ❌ is_safe
```

默认开启短路，所以这棵树在第一个能决定结果的节点就停了：`is_safe` 为假，AND 已注定失败，OR 分支不再求值。

## 读懂 Trace 树

关掉短路（`short_circuit=False`），所有分支都会被求值，一次看清全部命中与未命中：

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

几点：

- 图标：`✅` 通过、`❌` 未通过、`⏭️` 跳过（见下）。
- AND / OR 是**扁平的 N-ary 节点**，不是二叉嵌套——与编译期的 N-ary 展平一致（见[组合与性能](composition.md)）。
- 默认渲染目前只在节点被跳过时额外展开 `Context` 与错误信息；普通节点只显示判定结果。

## 跳过出错的规则：fail_skip

传入 `fail_skip=(SomeError, ...)`，当某条规则在求值时抛出其中的异常，它会被**跳过**而不是让整次求值崩溃。被跳过的叶子回退为不影响父运算的中性值（本例 AND 下回退为 `True`），在 Trace 里显示为 `⏭️`，并附上上下文与异常：

```python
@txn.rule_def()
def risky(ctx: Transaction) -> bool:
    raise ValueError("boom")


policy2 = risky() & is_safe()
ok = {"amount": 5000, "region": "JP", "is_fraud_flagged": False}

print(policy2(ok, fail_skip=(ValueError,)))  # True —— risky 被跳过,结果由 is_safe 决定
print(policy2(ok, trace=True, short_circuit=False, fail_skip=(ValueError,)))
```

```text
✅ AND
  ⏭️  risky
    └─ Context: {'amount': 5000, 'region': 'JP', 'is_fraud_flagged': False}
    💥 Error: ValueError('boom')
  ✅ is_safe
```

`fail_skip` 在不开 trace 时同样生效（只是没有树），用于容忍个别规则的临时故障。

## 定制 TraceStyle

渲染由 `TraceStyle` 决定——一个只需实现 `render(self, trace, level=0) -> str` 的协议。直接用它渲染结果树，即可换一套输出（例如对接日志或前端）：

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

渲染时可读取的字段：`success`（判定）、`operator`（`and` / `or` / `not` / `leaf` / `SKIP`）、`children`（子节点）、`node`（原谓词，带 `name` / `desc`）、`value`（上下文，仅跳过 / 失败时填充）、`error`（异常）。

## 对接日志

`Trace` 是普通对象，可以遍历 `children` 自行抽取结构化字段，落进结构化日志——这正是 predylogic「可审计」的用途：记录一次决策的完整判定路径，而不仅是最终的 `bool`。

!!! note

    Trace 仍在迭代中，后续会补充更多信息（如各节点的上下文快照）。自定义渲染请直接调用 `style.render(trace)`。
