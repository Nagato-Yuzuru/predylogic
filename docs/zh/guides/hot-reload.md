# 热更新

!!! note "大纲草稿"

_本页目标:不重启进程、不更换 handle 对象,原子地替换谓词逻辑。_

## 为什么需要

_待写:规则要随业务调整,但调用方持有的引用不应失效。_

## PredicateHandle:可变指针

_待写:`get_predicate_handle` 对 `(registry, rule_name)` 是单例;`update_manifests` 在 `RLock` 下热替换内部谓词,_
_调用方持有的 handle 对象不变。_

## Tombstone:引用尚未定义的规则

_待写:引用一个还没定义的规则会拿到 tombstone handle,待 manifest 更新后自动解析。_

## 并发保证

_待写:`get_predicate_handle` 与 `update_manifests` 的原子性;指向回归测试 `test_concurrency.py`。_

## 相关

_待写:配置加载见[Schema 与序列化](serde.md)。_
