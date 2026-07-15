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
| 实现状态 | 部分实现：compiler-owned query key、内容指纹、依赖边、传递失效、统计/snapshot、保守的增量 semantic check/symbol 与带 edit benchmark 的 LSP session cache 已落地；持久化与细粒度 type query 尚未完成 |
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

1. **已落地：**包含 schema/toolchain/target 的 query key、带长度 framing 的
   SHA-256 内容指纹、input/query 依赖边、传递失效、cache statistics 与不可变
   generation snapshot。
2. **部分实现：**`IncrementalSemanticSession` 基于保守的 project/external-source
   指纹缓存完整 project check 与 symbol 结果，并已有 clean-result 等价性测试；
   parser、name-resolution 与 type-query 的细粒度复用尚未完成。
3. **部分实现：**LSP 已缓存 diagnostics、completion、document symbols 与
   semantic tokens；open overlay 参与 fingerprint，edit 会失效声明依赖，diagnostic
   携带 document version。release gate 现在测量 cold/warm completion 与
   edit-to-diagnostics latency，并要求可观测的 hit/invalidation。request cancellation
   及直接使用新 compiler session 需要等待下一次 pinned compiler revision。
4. **待实现：**持久化 value、原子 disk write、容量回收、损坏恢复，以及随机化
   clean/incremental fault-injection tests。

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
