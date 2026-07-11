# RFC 0016：增量语义图与持久化缓存

> 语言 / Language: 中文 | [English](../../en/rfcs/0016-incremental-semantic-graph-and-cache.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0016 |
| 标题 | 增量语义图与持久化缓存 |
| 状态 | Proposed（已提案） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 未实现；compiler/LSP 已共享语义 API，但 workspace 查询仍以完整重算为基线 |
| 关联主题 | incremental compilation、semantic graph、cache、LSP、invalidation |
| 关联 RFC | [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)、[RFC 0012](./0012-shared-semantic-identities-and-verified-rename.md) |

---

## 1. 摘要

在现有 workspace/package/module 图和 compiler-owned declaration identity 上增加内容寻址的查询缓存。每个语义结果记录输入指纹与依赖边；文件、manifest、target 或 toolchain 变化只使传递受影响的查询失效。

## 2. 动机

共享语义事实解决了正确性来源，却没有解决大型 workspace 的重复解析、类型检查和 LSP 延迟。增量化必须保持与 clean build 完全相同的诊断、符号身份和生成物。

## 3. 提议设计

- 查询键包含 toolchain/schema、target、package identity、module path、source hash 与相关配置。
- parser、name resolution、type facts、references 和可复用 codegen 输入分层缓存；不缓存依赖外部进程的非确定结果。
- dependency edge 由查询执行记录，变更按反向边传播失效。
- 内存缓存服务编辑会话；磁盘缓存使用原子写入、版本目录和容量回收。
- rename 等变更操作仍在 fresh semantic snapshot 上复验；缓存命中不能绕过类型检查门槛。
- `nomo clean` 清项目产物，另提供可观测的 cache stats/清理入口。

## 4. 实现切片

1. query key、fingerprint、dependency edge 与失效引擎。
2. parser/name-resolution/type-query 内存增量化。
3. LSP overlay、取消、并发 snapshot 与延迟基准。
4. 持久化 cache、schema migration、clean-build 等价性和故障注入测试。

## 5. 备选方案

| 方案 | 问题 | 倾向 |
| --- | --- | --- |
| 仅按文件缓存 AST | 跨模块类型依赖仍会全量重算 | 不足 |
| LSP 自建缓存 | 重新产生两套语义事实 | 拒绝 |
| compiler-owned query graph | CLI 与编辑器共享正确性和性能模型 | 提议 |

## 6. 缺点与风险

错误失效会产生比编译失败更危险的陈旧成功；磁盘 schema、并发和取消增加实现复杂度。

## 7. 兼容与迁移

缓存不是构建输入或可移植工件，删除后必须可完整重建；schema 不兼容时直接丢弃，不迁移语义结果。

## 8. 接受门槛

随机编辑序列下 incremental 与 clean 诊断/生成物一致，跨进程缓存损坏可安全恢复，并达到约定的 LSP 与 rebuild 基准后才能 `Accepted`。

## 9. 未决问题

- declaration identity 是否需要跨文件移动保持稳定。
- 首版是否持久化 codegen 中间层。
- cache 容量与隐私清理策略由项目还是全局配置控制。

## 10. 参考

- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)、[RFC 0012](./0012-shared-semantic-identities-and-verified-rename.md)。
