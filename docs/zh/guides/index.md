# 指南

指南是任务导向的 how-to，针对某个具体问题展开。每篇都假设你已读过[快速开始](../quick-start.md)，可按需查阅。

按任务选择：

- **[Schema 与序列化](serde.md)** — 从 registry 导出 JSON Schema，用 manifest 从配置加载规则，并在 config 时完成校验。
- **[热更新](hot-reload.md)** — 运行时原子替换谓词逻辑：`PredicateHandle`、tombstone，以及并发保证。
- **[Trace 追踪](trace.md)** — 定制 `TraceStyle`、对接日志系统，用 `short_circuit` 控制求值过程。
- **[组合与性能](composition.md)** — `&` `|` `~` 与 `all_of` / `any_of` 的取舍、N-ary 展平，以及 bytecode 快路径。
