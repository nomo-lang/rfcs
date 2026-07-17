# RFC 0020：Manifest v2、Workspace 成员资格与项目配置

> 语言 / Language: 中文 | [English](../../en/rfcs/0020-manifest-v2-workspace-and-project-configuration.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0020 |
| 标题 | Manifest v2、Workspace 成员资格与项目配置 |
| 状态 | Accepted（已接受） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-17 |
| 关联主题 | manifest、package management、workspace、migration、registry trust |
| 关联 RFC | [RFC 0008](./0008-canonical-package-identity-and-aliases.md)、[RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)、[RFC 0013](./0013-registry-protocol-and-package-integrity.md)、[RFC 0018](./0018-package-signing-provenance-and-transparency.md) |

---

## 1. 摘要

引入显式版本化的 `nomo.toml` schema，把可发布 package/workspace 事实与项目、
组织的运营 policy 分离。Manifest v2 要求稳定 package identity，使用一个显式
workspace 继承开关，在继承前验证成员资格，并继续区分依赖 alias 与 canonical
package identity。Registry trust、透明日志 gossip 等环境 policy 迁移到
`.nomo/config.toml`，由 `nomo manifest migrate` 完成 v1 到 v2 的转换。

## 2. 动机

原 manifest 逐步容纳 package identity、workspace default、source selection、
target condition、FFI metadata 与 transparency policy，现状存在这些问题：

- 缺少 package 字段时静默回退到目录名、`local`、`0.1.0` 和 edition `2026`；
- `workspace.package.name` 可以继承，但 member name 本应各自唯一；
- `namespace.workspace = true` 等逐字段继承写法重复；
- 发现祖先 `[workspace]` 后，在证明当前 package 属于 member 前就可能继承；
- 可发布 `nomo.toml` 携带消费者侧 registry trust 与 gossip path；
- legacy 顶层 `name = "..."` 在没有显式 schema 边界时仍被接受。

这些行为使 package identity 与运营 policy 难以审计。应在 preview 将
`nomo.toml` 稳定为公共兼容面之前完成迁移。

## 3. 现状与问题

RFC 0008 规定 canonical package identity 是 `namespace/name`；RFC 0009
规定 workspace-root 唯一 lockfile 与 typed workspace/package/module graph。
实现已支持 workspace dependency 继承、target-conditioned edge、registry
求解、signed release 和 offline operation。

当前缺口不是 graph 能力，而是 permissive `toml::Value` parser 把 schema
识别、继承、membership 与 local policy 耦合。工具无法可靠区分 legacy input、
standalone package、virtual workspace 与 combined root package。

## 4. 详细设计

### 4.1 Schema 选择与文档类型

Manifest v2 以如下字段开头：

```toml
manifest-version = 2
```

缺少 `manifest-version` 时进入 legacy v1 compatibility parser。不支持的值直接
报错，不能回退 v1。V2 顶层只接受 `manifest-version`、`package`、
`workspace`、`dependencies` 与 `ffi`；`[trust]` 给出迁移到
`.nomo/config.toml` 的定向错误。

文档类型只有三种：

- package：只有 `[package]`；
- virtual workspace：只有 `[workspace]`；
- combined workspace root：同时存在两者；root package 参与时必须在
  `workspace.members` 中显式包含 `"."`。

### 4.2 Package identity 与 metadata

Standalone package 必须声明完整 identity：

```toml
manifest-version = 2

[package]
namespace = "acme"
name = "calculator"
version = "1.2.0"
edition = "2026"
description = "A deterministic calculator"
license = "Apache-2.0"
repository = "https://example.com/acme/calculator"
publish = true
```

V2 不再为 `namespace`、`name`、`version`、`edition` 提供目录或版本 fallback。
`name` 始终属于 member 自身，不能继承。描述 metadata 进入 typed manifest 与
archive tooling，不再被静默忽略。

Member 用一条声明选择 workspace default：

```toml
manifest-version = 2

[package]
name = "cli"
inherit = "workspace"
publish = false
```

Member 显式值优先；缺少的 `namespace`、`version`、`edition` 必须存在于
`[workspace.package]`，否则解析失败。只有 package root 已被证明匹配
`members` 且未被 `exclude` 后，`inherit` 才有效。

### 4.3 Workspace topology

```toml
manifest-version = 2

[workspace]
members = ["apps/*", "packages/*"]
default-members = ["apps/cli"]
exclude = ["packages/legacy"]
resolver = "2"

[workspace.package]
namespace = "acme"
version = "0.1.0"
edition = "2026"
license = "Apache-2.0"

[workspace.dependencies]
json = { package = "nomo-lang/json", version = "^1.2.0" }
core = { path = "packages/core" }
```

Member/exclude path 是不能逃出 workspace root 的 normalized relative path。
每个选中 member 必须含 v2 package manifest；`default-members` 必须是 included
member 的子集。Duplicate canonical identity、duplicate canonical path、nested
workspace ambiguity 与 symlink escape 都是错误。

Workspace dependency table 是 source/version catalog，不会隐式授予 import。
Member 必须显式选择：

```toml
[dependencies]
json = { workspace = true }
core = { workspace = true }
```

### 4.4 Dependencies

Dependency table key 继续作为 package-local import alias。Registry dependency
必须提供 canonical package 与 version constraint。Path dependency 可以省略
`package`，由 Nomo 读取目标 manifest 推导 canonical id；若显式提供则作为
assertion，必须匹配。Git dependency 继续要求显式 canonical package，因为网络
checkout 前必须知道 identity。

```toml
[dependencies]
json = { package = "nomo-lang/json", version = "^1.2.0" }
core = { path = "../core" }
http = { package = "nomo-lang/http", git = "https://example.com/http.git", rev = "abc123" }
win = { package = "acme/windows", version = "1.0.0", target = { os = ["windows"], env = ["msvc"] } }
```

只能选择一个 source family：registry（`version`）、`path` 或 `git`。Workspace
inheritance 不能和 source field 同时出现。既有 target condition canonicalization
与完整 lockfile 表示保持不变。

### 4.5 项目与组织配置

运营 policy 迁移到 `.nomo/config.toml`：

```toml
config-version = 1

[registry]
policy = "signed+transparent"
transparency-keys = ["<32-byte-ed25519-public-key-hex>"]
proof-max-age-seconds = 86400
offline-proof-max-age-seconds = 604800
max-future-skew-seconds = 300
gossip-checkpoints = ["trust/peer-a.json"]
```

Workspace member 使用已经验证的 workspace-root config；standalone package 使用
自身 project-root config。Dependency package config 绝不能改变 consumer project
的 trust policy。Path 相对 project/workspace root 解析，而不是相对 `.nomo`
目录。Credential 与 private key 继续位于两个文件之外。

V1 `[trust]` 只由 v1 compatibility parser 读取；V2 拒绝它，避免新发布
manifest 携带 consumer policy。

### 4.6 Lockfile 与命令 scope

Standalone package 视为单 package resolution root；workspace 继续只拥有一个
root `nomo.lock`。在 member 内运行命令选中该 member；在 virtual workspace
root 运行时选中 `default-members`；`--workspace` 选择全部 member，
`--package` 按 canonical id 或唯一 package name 选择一个。

`nomo add/remove` 编辑选中 member。未来可以增加显式 workspace catalog 编辑
参数，而不改变 v2 parsing。

### 4.7 Migration

`nomo manifest migrate [path]`：

1. 解析 v1 document；
2. 写入 `manifest-version = 2`；
3. 物化过去来自 default 的字段；
4. 把逐字段 workspace inheritance 转换成 `inherit = "workspace"`；
5. 删除无效 `workspace.package.name`；
6. 把 `[trust]` 移入 `.nomo/config.toml`；
7. 验证转换后的 package/workspace graph；
8. 所有输出验证通过后才原子替换文件。

`--check` 执行同样分析但不写入，需迁移时返回失败。已是 v2 的输入保持幂等。
除非 dependency 语义改变且用户之后主动 resolve，否则工具不重写 `nomo.lock`。

### 4.8 Typed API 与 diagnostics

`nomo-manifest` 暴露 schema enum、typed document kind、typed package/workspace
declaration 与 typed project configuration。Consumer 不再根据 optional raw TOML
table 猜测 document kind。

Manifest failure 继续走 project diagnostic `E0901`，message 包含 file、schema、
table/field 与可执行 migration hint。关键 negative case 包括 unknown field、
缺少显式 identity、membership 外继承、v2 manifest 中出现 trust、path identity
mismatch 与 unsupported schema version。

### 4.9 Compiler、C backend、standard library 与 runtime 影响

没有语言或 C ABI 变化。Compiler 继续获得相同 resolved canonical package 与
target-filtered dependency graph。Standard library/runtime 除 toolchain std
manifest 迁移到 v2、描述 metadata 进入 typed model 外不受影响。

### 4.10 测试计划

- v1 compatibility 与确定 migration snapshot；
- v2 positive/negative parser 和 unknown-field 测试；
- standalone、virtual、combined workspace discovery；
- non-member/excluded/nested/symlink membership 拒绝；
- workspace inheritance 与 dependency catalog；
- path identity 推导及显式 mismatch；
- `.nomo/config.toml` scope、trust、gossip path、dependency isolation；
- CLI `manifest migrate` check/write/idempotence；
- 既有 resolver、lockfile、offline、vendor、target、signing 与 cross-build suite。

## 5. 备选方案

| 方案 | 做法 | 优点 | 缺点 |
| --- | --- | --- | --- |
| 继续扩展 v1 | 增加更多 optional table/default | 不需要 migration command | identity 歧义与 policy coupling 永久化 |
| Package/workspace 使用不同文件名 | 使用 `nomo.package.toml` 与 `nomo.workspace.toml` | 文件级类型明确 | discovery rule 更多，combined root 笨重 |
| 显式 v2 + project config | 版本化 `nomo.toml`、验证 kind、把运营项迁移到 `.nomo/config.toml` | 兼容边界明确、package 语义可复现 | 需要 migration 和临时双 parser |

## 6. 缺点与风险

实现会临时维护两个 parser，必须避免 v1 default 泄漏到 v2。Trust policy 迁移若
只完成一半可能造成意外，因此文件替换必须 transactional。严格 membership 会
拒绝过去偶然继承成功的目录布局。在引入 lossless TOML document model 前，CLI
修改的注释保留能力仍有限。

## 7. 对 v0.1 范围的影响

Manifest v2 属于 v1.0 前的 preview stabilization。本 RFC 不增加 feature、build
script、multiple binary target 或 dev/build dependency；这些需要独立兼容决策。
验收矩阵新增 manifest migration 与严格 workspace/configuration case，同时保留
全部既有 graph/cross-build gate。

## 8. 倾向性建议

接受显式 v2 schema、严格 identity/document kind、经过验证的 workspace
inheritance、dependency catalog 语义、project config 分离与确定 migration
command。Preview 期间保留 v1 parser 只读兼容，之后只能通过后续 RFC 移除。

## 9. 未决问题

- 后续是否引入 lossless TOML editor，在全部 CLI mutation 中保留注释。
- Named registry 与 per-registry trust policy 是否由后续 RFC 扩展
  `.nomo/config.toml`。
- Optional feature、dev dependency 与 multiple build target 应归入同一 package
  model RFC 还是拆分提案。

## 10. 实现状态

本 RFC 已于 2026-07-17 接受并完成实现。实现包括 typed v1/v2 兼容边界、严格
v2 package/workspace/config 校验、membership-before-inheritance、path dependency
identity 推导、workspace root config、transactional `nomo manifest migrate`、v2
项目脚手架、标准库与代表性示例迁移及文档更新。完整 Cargo workspace 测试套件在
保留 v1 兼容的同时全部通过。

## 11. 参考

- [RFC 0008](./0008-canonical-package-identity-and-aliases.md)
- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)
- [RFC 0013](./0013-registry-protocol-and-package-integrity.md)
- [RFC 0018](./0018-package-signing-provenance-and-transparency.md)
