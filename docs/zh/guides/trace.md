# Trace 追踪

!!! note "大纲草稿"

_本页目标:用求值树看清「为什么这条规则命中或失败」,并把它接进你的日志系统。_

## 开启 Trace

_待写:`policy(ctx, trace=True)` 返回一棵 Trace 树而非 `bool`;快路径不受影响(trace 是慢路径)。_

## 读懂 Trace 树

_待写:N-ary 节点(AND / OR 各是一个扁平节点,而非二叉嵌套);叶子带 context;_
_`short_circuit=False` 可看完整求值过程。_

## 定制 TraceStyle

_待写:替换渲染样式以适配不同输出目标(终端 / 日志 / 结构化)。_

## 对接日志

_待写:把 Trace 落进结构化日志的建议;呼应「可审计」这个卖点。注:Trace 仍在迭代中。_
