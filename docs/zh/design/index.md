# 设计与架构

> 设计笔记反映的是迭代早期的想法，API 可能已经变动（甚至被推翻）。最新接口以 [API 参考](../reference.md) 为准。

本节记录 predylogic 为什么这么设计、做过哪些trade-off。

## ADR

重大架构变更用 ADR 记录：

- [ADR 001:求值引擎](adr/001_evaluation_engine.md) — 为什么从闭包递归换成迭代式 AST 引擎。
- [ADR 002:AST 编译优化](adr/002_AST_compiler_optimization.md) — 做过哪些编译优化尝试，以及最终的基准数据。
