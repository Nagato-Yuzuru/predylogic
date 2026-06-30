# Schema 与序列化

predylogic 的目标是”配置即数据”、”类型安全”和”支持热更新”。这篇指南聚焦第一点：导出 JSON Schema 用于校验，然后从 manifest 加载可执行的谓词。

本页沿用[快速开始](../quick-start.md)里的 `txn` registry 及其三条规则（`is_safe` / `is_high_value` / `in_regions`）。

## 导出 JSON Schema

`SchemaGenerator` 读取 registry 中所有原子规则的签名，生成一个 Pydantic 模型（manifest 模型）；`model_json_schema()` 再把它导出为标准 JSON Schema：

```python
from predylogic import SchemaGenerator

Manifest = SchemaGenerator(txn).generate()

schema = Manifest.model_json_schema()  # 标准 JSON Schema(dict)
```

生成的 schema 为每条规则单独建模（例如 `IsHighValueParams` 描述 `threshold: int`），并以 `rule_def_name` 作为判别字段（discriminator）。把它交给任意 JSON Schema 校验器，或喂给支持 schema 的编辑器，就能在**编写配置时**发现类型错配、引用不存在的规则等问题，而不必等到运行时。

## 用 manifest 从配置加载

加载分三步：把 registry 注册进 `RegistryManager`； 用生成的 manifest 模型解析配置； 交给 `RuleEngine`，再取回可执行的谓词句柄。

!!! note "DSL 配置"

    手写 JSON AST 较为冗长；我们正在推进一套更简洁的 DSL 配置，用于替代原始 JSON / YAML。

```python
from predylogic import RegistryManager, RuleEngine

config = """
{
  "registry": "txn",
  "rules": {
    "policy": {
      "node_type": "and",
      "rules": [
        {"node_type": "leaf", "rule": {"rule_def_name": "is_safe", "params": {}}},
        {"node_type": "or", "rules": [
          {"node_type": "leaf", "rule": {"rule_def_name": "is_high_value", "params": {"threshold": 2000}}},
          {"node_type": "leaf", "rule": {"rule_def_name": "in_regions", "params": {"regions": ["US", "EU"]}}}
        ]}
      ]
    }
  }
}
"""

# 1. 解析并校验配置(这一步就会抓出配置错误)
manifest = Manifest.model_validate_json(config)

# 2. 注册 registry,装载 manifest
manager = RegistryManager()
manager.add_register(txn)
engine = RuleEngine(manager)
engine.update_manifests(manifest)

# 3. 取回谓词句柄,像普通谓词一样调用
policy = engine.get_predicate_handle("txn", "policy")

assert policy({"amount": 5000, "region": "JP", "is_fraud_flagged": False})
assert not policy({"amount": 500, "region": "US", "is_fraud_flagged": True})
```

这条 `policy` 与[快速开始](../quick-start.md)里用 `&` / `|` 写出来的那条完全等价。配置只是同一棵谓词树的数据形式。

## manifest 结构

一份 manifest 形如 `{"registry": <名字>, "rules": {<规则名>: <节点>}}`。`rules` 是一张以规则名为键的 DAG；每个节点用 `node_type` 区分：

| `node_type` | 关键字段                          | 含义                        |
| ----------- | --------------------------------- | --------------------------- |
| `leaf`      | `rule`: `{rule_def_name, params}` | 一个原子规则                |
| `and`       | `rules`: 子节点数组（≥ 2）        | 全部满足                    |
| `or`        | `rules`: 子节点数组（≥ 2）        | 任一满足                    |
| `not`       | `rule`: 单个子节点                | 取反                        |
| `ref`       | `ref_id`: 另一条规则名            | 引用 `rules` 里的另一条规则 |

`leaf` 的 `params` 与原子规则的签名一一对应：`is_safe` 无参数，写 `{}`（也可省略）；`is_high_value` 的 `threshold`、`in_regions` 的 `regions` 按名字给值。`and` / `or` / `not` / `leaf` 分别对应代码里的 `all_of`、`any_of`、`~`、单个原子规则；其中 `and` / `or` 是扁平的 N-ary 节点（子节点 ≥ 2），与 `all_of` / `any_of` 同构。

`ref` 允许一条规则引用另一条（因此 `rules` 是 DAG 而非孤立的树）。引用一条尚未定义的规则不会立刻报错，而是得到一个待解析的占位句柄，详见[热更新](hot-reload.md)。

## 校验与报错

predylogic 倾向于**尽早失败**：能在配置时发现的错误不延后到运行时。

`model_validate_json`（配置时）会抓出类型错配（`threshold` 写成字符串报 `int_parsing`）、引用不存在的规则（`rule_def_name` 不在 registry 中报 `literal_error`）、结构错误（多余字段、`and` / `or` 子节点不足 2 个、节点缺字段），以及 `ref` 之间形成环（`RuleDefRingError`）。

少数错误只能等到装载或运行时：

- `update_manifests` 装载时，若配置引用的 registry 未注册 → `RegistryNotFoundError`。
- 调用一个引用了「未定义 / 已撤销」规则的句柄时 → `RuleRevokedError`（见[热更新](hot-reload.md)）。

## 相关

- 在运行时原子替换已加载的规则：[热更新](hot-reload.md)。
