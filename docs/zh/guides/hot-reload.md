# 热更新

规则会随业务调整，但持有规则引用的调用方不应因为一次更新而失效。predylogic 把「取得规则」和「规则的当前实现」分开：`get_predicate_handle` 返回一个稳定的句柄，`update_manifests` 在其背后原子地替换实现。

本页承接[Schema 与序列化](serde.md)的加载流程，沿用其中的 `txn` registry、`Manifest` 模型与 `engine`。

## 为什么需要

典型场景：风控阈值要在不重启服务的前提下调整。调用方往往在启动时取得一次谓词句柄并长期持有（存进某个配置对象或闭包）。如果每次规则更新都要求调用方重新获取引用，就很容易漏更新、用上过期的逻辑。

predylogic 的做法是：句柄对象本身始终不变，只在它背后替换所指向的实现。

## PredicateHandle：可变指针

`get_predicate_handle(registry, rule_name)` 对同一个 `(registry, rule_name)` 始终返回**同一个 Python 对象**（单例）。它内部持有一个谓词引用；`update_manifests` 会在 `RLock` 下把这个引用原子替换为新编译的谓词。调用方持有的句柄不变，行为却随之更新：

```python
def gate_manifest(threshold: int):
    return Manifest.model_validate(
        {
            "registry": "txn",
            "rules": {
                "gate": {
                    "node_type": "leaf",
                    "rule": {"rule_def_name": "is_high_value", "params": {"threshold": threshold}},
                },
            },
        }
    )


tx = {"amount": 5000, "region": "JP", "is_fraud_flagged": False}

# v1:阈值 1000
engine.update_manifests(gate_manifest(1000))
gate = engine.get_predicate_handle("txn", "gate")
assert gate(tx)  # 5000 >= 1000

# v2:阈值调到 10000. 不重启、不重新获取句柄
engine.update_manifests(gate_manifest(10000))
assert gate is engine.get_predicate_handle("txn", "gate")  # 同一个对象
assert not gate(tx)  # 5000 < 10000,行为已更新
```

通过 `ref` 引用其它规则时，这种更新会传递：更新被引用的规则，引用方的行为也随之改变，因为引用方持有的正是被引用规则那个会被原子替换的句柄。

!!! note "移除 ≠ 撤销"

    `update_manifests` 是增量覆盖：只新增或替换 manifest 中出现的规则，不会删除其它规则。若新 manifest 省略了某条已加载的规则，它的句柄会保留上一次成功编译的实现（last-known-good），而非被撤销。要让一条规则失效，需显式把它替换成期望的逻辑。

## Tombstone：引用尚未定义的规则

取一个尚未定义的规则，或一条 `ref` 指向尚未定义的目标，都不会立刻报错，而是得到一个 **tombstone** 句柄（同样是单例）。在该规则被定义之前调用它会抛 `RuleRevokedError`；一旦后续 `update_manifests` 补上定义，同一个句柄对象会自动解析为真正的逻辑：

```python
from predylogic.rule_engine.errs import RuleRevokedError

# alias 引用尚未定义的 missing
engine.update_manifests(
    Manifest.model_validate(
        {"registry": "txn", "rules": {"alias": {"node_type": "ref", "ref_id": "missing"}}}
    )
)
alias = engine.get_predicate_handle("txn", "alias")

try:
    alias(tx)  # missing 尚未定义
except RuleRevokedError as e:
    print(e)  # Rule 'missing' in txn revoked or missing.

# 补上 missing 的定义 —— 同一个 alias 句柄自动生效
engine.update_manifests(
    Manifest.model_validate(
        {
            "registry": "txn",
            "rules": {
                "missing": {"node_type": "leaf", "rule": {"rule_def_name": "is_safe", "params": {}}},
                "alias": {"node_type": "ref", "ref_id": "missing"},
            },
        }
    )
)
assert alias is engine.get_predicate_handle("txn", "alias")
assert alias(tx)  # 解析为 is_safe -> True
```

这让规则的加载顺序无关紧要：可以先取得句柄、分发给调用方，稍后再补齐其依赖的定义。

## 并发保证

`get_predicate_handle` 与 `update_manifests` 都是线程安全的。句柄创建采用双重检查锁，即使大量线程同时请求同一个 `(registry, rule_name)` 也只会创建一个实例。`update_manifests` 在 `RLock` 下进行，并发的读取（取句柄、求值）与写入（更新）互不破坏状态。不同 registry、不同规则之间彼此独立，一次更新只触及 manifest 中出现的规则。

## 相关

- 配置格式与 schema 校验：[Schema 与序列化](serde.md)
- 若只在代码里组合、无需运行时更新，直接用[快速开始](../quick-start.md)的 `&` / `|` 即可。
