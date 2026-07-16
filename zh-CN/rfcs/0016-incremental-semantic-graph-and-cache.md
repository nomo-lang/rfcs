# RFC 0016：增量语义图与持久化缓存

> 语言 / Language: 中文 | [English](../../en/rfcs/0016-incremental-semantic-graph-and-cache.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0016 |
| 标题 | 增量语义图与持久化缓存 |
| 状态 | Accepted（已接受） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 已接受基线：compiler-owned query key、内容指纹、依赖边、传递失效、统计/snapshot、保守 semantic/LSP cache、带 schema 版本的持久化 check/C-codegen value、原子写入、容量回收、损坏恢复与随机 clean 等价性测试均已落地 |
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
2. **已落地：**`IncrementalSemanticSession` 基于保守的 project/external-source
   指纹缓存完整 project check 与 symbol 结果，并已有 clean-result 等价性测试；
   更细的 parser、name-resolution 与 type-query 复用可在同一正确性契约下继续优化。
3. **已落地：**LSP 已缓存 diagnostics、completion、document symbols 与
   semantic tokens；open overlay 参与 fingerprint，edit 会失效声明依赖，diagnostic
   携带 document version。release gate 现在测量 cold/warm completion 与
   edit-to-diagnostics latency，并要求可观测的 hit/invalidation。request cancellation
   属于 LSP 调度优化，不再作为 cache 正确性前置条件。
4. **已落地：**`.nomo/cache/incremental/v1` 跨进程持久化成功的 project check
   value 与 target-specific generated C。entry 使用带 checksum 的 envelope、已同步
   temporary file 与 atomic replacement；损坏会作为 miss 自动删除重算。默认容量
   为 512 MiB，可通过 `NOMO_INCREMENTAL_CACHE_MAX_BYTES` 配置；`nomo cache
   stats|prune|clean` 提供观测、回收与清理。确定性随机编辑会对比 persistent/clean
   diagnostics；CLI 测试覆盖 cold/warm process、source invalidation、损坏恢复、
   codegen 复用与强制 eviction。

## 5. 备选方案

| 方案 | 问题 | 倾向 |
| --- | --- | --- |
| 仅按文件缓存 AST | 跨模块类型依赖仍会全量重算 | 不足 |
| LSP 自建缓存 | 重新产生两套语义事实 | 拒绝 |
| compiler-owned query graph | CLI 与编辑器共享正确性和性能模型 | 采用 |

## 6. 缺点与风险

错误失效会产生比编译失败更危险的陈旧成功；磁盘 schema、并发和取消增加实现复杂度。

## 7. 兼容与迁移

缓存不是构建输入或可移植工件，删除后必须可完整重建；schema 不兼容时直接丢弃，不迁移语义结果。

## 8. 接受门槛

确定性随机编辑已验证 incremental/clean 等价；跨进程 CLI 测试已验证损坏 entry
自动恢复、cold/warm 命中可观测，既有 LSP/rebuild latency gate 持续生效。cache
删除与强制回收也已作为普通 clean miss 覆盖，因此验收门槛已满足。

## 9. 未决问题

- accepted baseline 中跨文件移动会使保守 source fingerprint 失效；identity 跨移动
  稳定性后续再做。
- 首版持久化成功 check result 与 generated C，不持久化 typed IR 或 linked binary。
- 容量与隐私清理由 project/workspace 管理，并提供环境默认覆盖与显式
  `nomo cache prune|clean` 命令。

## 10. 参考

- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)、[RFC 0012](./0012-shared-semantic-identities-and-verified-rename.md)。
