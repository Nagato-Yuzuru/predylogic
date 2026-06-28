# 指南

!!! note "大纲草稿"
    本页是指南区的总览大纲。

_待写:一段话说明指南区的定位——任务导向的 how-to,一页一题;假设你已读过[快速开始](../quick-start.md)。_

按任务选择:

- **[Schema 与序列化](serde.md)** — _从 registry 导出 JSON Schema、用 manifest 从配置加载规则、在 config 时校验。_
- **[热更新](hot-reload.md)** — _运行时原子替换谓词逻辑;`PredicateHandle` 与 tombstone;并发保证。_
- **[Trace 追踪](trace.md)** — _定制 `TraceStyle`、对接日志系统、用 `short_circuit` 控制求值。_
- **[组合与性能](composition.md)** — _`&` `|` `~` 与 `all_of` / `any_of` 的取舍、N-ary 展平、bytecode 快路径。_
