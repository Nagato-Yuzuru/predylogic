# Schema 与序列化

!!! note "大纲草稿"

_本页目标:把规则在「代码定义」和「配置数据」之间打通——导出 schema 做校验,从 manifest 加载规则。_

## 导出 JSON Schema

_待写:`SchemaGenerator(registry).generate()` 得到一个 Pydantic 模型;`model_json_schema()` 导出标准 JSON Schema。_
_说明用途:在 config 时校验规则配置(类型错配、引用不存在的 rule_def)。_

## 用 manifest 从配置加载

_待写:`RegistryManager` + `RuleEngine`;`model_validate_json` 解析 manifest;`update_manifests` 装载;_
_`get_predicate_handle` 取回可执行谓词。给一段完整的 JSON 示例。_

## manifest 结构

_待写:`node_type`(`and` / `or` / `leaf`)、`rule_def_name`、`params` 的对应关系;_
_以及它和代码里 `all_of` / `any_of` 组合的同构关系。_

## 校验与报错

_待写:config 时能抓到哪些错误、运行时才暴露哪些;呼应「早失败」原则。_

## 相关

_待写:运行时替换规则见[热更新](hot-reload.md)。_
