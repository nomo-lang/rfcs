# RFC 0009：可复现的 Workspace、Package 与 Module 图

> 语言 / Language: 中文 | [English](../../en/rfcs/0009-reproducible-workspace-and-package-graphs.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0009 |
| 标题 | 可复现的 Workspace、Package 与 Module 图 |
| 状态 | Accepted（已接受） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 已落地：`WorkspaceGraph -> PackageGraph -> ModuleGraph`、稳定拓扑序、workspace lockfile、checksum、locked/offline/frozen、vendor 与 cycle/conflict 测试 |
| 关联主题 | workspace、dependency graph、lockfile、checksum、offline build |
| 关联 RFC | [RFC 0008](./0008-canonical-package-identity-and-aliases.md)、[RFC 0013](./0013-registry-protocol-and-package-integrity.md) |

---

## 1. 摘要

Nomo 使用三层显式图模型：workspace 发现成员，package graph 解析 canonical 依赖，module graph 解析源码 import。所有遍历采用稳定的依赖优先顺序；解析结果写入 workspace-root `nomo.lock`，可访问 source 以 `sha256:` checksum 固定。

## 2. 动机

把 workspace、包来源和模块 import 混成单个递归过程，会导致顺序不稳定、cycle 诊断模糊、LSP 与 CLI 结果分叉，也无法清晰定义离线与锁定构建。

## 3. 图模型

- `WorkspaceGraph`：成员、默认成员、继承字段、workspace root lockfile 和成员依赖顺序。
- `PackageGraph`：canonical package、source、版本/rev、checksum 与传递依赖。
- `ModuleGraph`：一个 package 内的 Flat+Dir 模块、可见性、import 边和 cycle path。

共享 graph 工具必须提供稳定拓扑序与包含闭环节点的 cycle path。重复 workspace package id、成员 path cycle、冲突 external package source/version 均在图构建阶段拒绝。

## 4. Lockfile 与模式

- workspace 使用单个 root `nomo.lock`；`[[root]]` 记录各成员直接边，`[[package]]` 去重共享依赖。
- path、git 与已下载 registry source 写入内容 checksum；registry archive checksum 与解包后 source checksum 分开记录和校验。
- `--locked` 禁止 lockfile 缺失或 manifest direct edge 漂移；`--offline` 禁止网络；`--frozen` 等价于二者组合。
- vendor 是 locked source 的可携带副本；原 source/cache 缺失时，locked/offline 构建可回退到 vendor。

## 5. 备选方案

| 方案 | 问题 | 决议 |
| --- | --- | --- |
| 每条命令即时递归 | 顺序和诊断不稳定，逻辑重复 | 拒绝 |
| 每个 member 单独 lockfile | workspace 共享依赖无法统一 | 拒绝 |
| 三层 typed graph + root lockfile | 边界清晰，可供 CLI/LSP/文档复用 | 接受 |

## 6. 缺点与风险

- v0.1 冲突策略是拒绝同一 canonical id 的多 source/version，不是完整版本求解。
- missing source 可作为离线锁定条目展示，但真正编译仍需要 cache 或 vendor 内容。
- checksum 算法与 archive 格式进入兼容面，修改必须版本化。

## 7. 对 v0.1 范围的影响

`check/build/run/test/doc/deps` 必须共享相同的 workspace/package/module 事实。`nomoc` 保持无 manifest 的单文件边界，不读取这些图。

## 8. 决议

接受三层图模型、稳定依赖优先遍历、workspace-root lockfile 和可验证 source checksum；locked/offline/frozen/vendor 行为成为 v0.1 工具契约。

## 9. 后续问题

- 语义化版本范围与多版本求解。
- 跨平台 target-specific dependency 与 lockfile 表示。
- lockfile/archive format 的版本升级策略。

## 10. 参考

- `nomo-graph`、`nomo-lockfile`、workspace/package/module graph API 与 CLI resolver 测试。
- [RFC 0008](./0008-canonical-package-identity-and-aliases.md)、[RFC 0013](./0013-registry-protocol-and-package-integrity.md)。
