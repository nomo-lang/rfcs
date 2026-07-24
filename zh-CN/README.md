# Nomo RFC 流程

> 语言 / Language: 中文 | [English](../en/README.md)

本目录收录 Nomo 编程语言的 RFC（Request for Comments，征求意见稿）。RFC 用于对**需要正式决策的语言、编译器、标准库与工具链问题**进行公开讨论与留痕。

RFC 文档应自包含：说明当前设计现状、问题、备选方案、倾向建议与对 v0.1 交付范围的影响。RFC 之间可以互相引用，但不依赖其它说明文档作为索引入口。

---

## 1. 规格基线

当前 v0.1 规格基线见 [`SPEC-v0.1.md`](SPEC-v0.1.md)。它描述 RFC 讨论所依据的语言、标准库、编译器与验收范围。

RFC 的职责是讨论并修改这份规格基线中的待决问题；RFC 被 `Accepted` 后，应同步更新规格基线与实现。

---

## 2. 状态字段定义

每篇 RFC 在元信息中标注 `状态` 字段，取值如下：

| 状态 | 含义 |
| --- | --- |
| `Draft`（待决） | 草案。问题已成形、备选已列出，但尚未做出决策。 |
| `Proposed`（已提案） | 草案已完成、进入正式评审，等待接受或拒绝。 |
| `Accepted`（已接受） | 已被采纳，应据此更新语言规格与实现。 |
| `Rejected`（已拒绝） | 经讨论后不采纳，保留记录与理由。 |
| `Deferred`（已推迟） | 方向认可，但推迟到后续版本（如 v0.2+）再处理。 |

状态流转典型路径：`Draft → Proposed → Accepted / Rejected / Deferred`。

---

## 3. 编号规则

- RFC 文件名格式：`NNNN-短横线英文标题.md`，其中 `NNNN` 为四位零填充编号。
- 编号从 `0001` 顺序递增，一经分配不再复用（即使被 `Rejected`）。
- `0000-template.md` 为模板，不是一篇真正的 RFC。
- 新 RFC 取当前最大编号 +1。

---

## 4. 提交流程

1. 复制 [`0000-template.md`](0000-template.md) 为 `rfcs/NNNN-你的标题.md`，填写所有小节。
2. 在元信息中标注关联主题，并用 Markdown 链接引用相关 RFC。
3. 初始状态设为 `Draft（待决）`。
4. 在本 README 第 6 节「目录索引」表中登记该 RFC（保持表格与实际文件一致）。
5. 进入评审后，按第 2 节的状态流转更新 `状态` 字段。
6. 一篇 RFC 被 `Accepted` 后，应同步发起语言规格与实现的更新。

> 约束：本目录只放 RFC 相关 markdown 文件，不修改其它目录。

---

## 5. 模板

见 [`0000-template.md`](0000-template.md)。模板包含：元信息（编号、标题、状态、作者、创建日期、关联主题、关联 RFC）、摘要、动机、现状与问题、详细设计（语法/语义/C 后端影响/诊断影响）、备选方案、缺点与风险、对 v0.1 范围的影响、未决问题、参考。

---

## 6. 目录索引

| 编号 | 标题 | 状态 | 关联主题 | 一句话结论/倾向 |
| --- | --- | --- | --- | --- |
| [0001](./rfcs/0001-error-propagation-and-conversion.md) | `?` 传播与缺少自动错误转换的体验矛盾 | Accepted（已接受） | 错误处理、`Result`、`?` 传播、C 后端 | v0.1 使用显式 `std.result.map_err(named_converter)?`；`From` 风格自动转换推迟。 |
| [0002](./rfcs/0002-match-wildcard-and-nesting.md) | `match` 缺少 `_` 通配分支与嵌套解构 | Accepted（已接受） | 模式匹配、穷尽性、嵌套解构 | `match` 继续禁用 `_`；`let else`、`if let` 与 `Option` 的 `?` 已落地并压平嵌套样板。 |
| [0003](./rfcs/0003-arc-cow-runtime-cost.md) | 值语义 + ARC + COW 的运行时实现成本 | Accepted（已接受） | 内存模型、`string`、`Array<T>`、运行时 | `string` 使用不可变非原子 RC；`Array<T>` 使用非原子 RC+COW，生命周期与写时分离已有测试。 |
| [0004](./rfcs/0004-mutable-borrow-uniqueness.md) | 可变借用唯一性检查的真实难度 | Accepted（已接受） | 可变借用、别名检查、逃逸检查 | 借用存活期限定为单个调用表达式，检查调用点路径冲突，不引入 lifetime 或命名借用。 |
| [0005](./rfcs/0005-newline-sensitivity-and-dot-resolution.md) | 显著换行分隔与 `.` 命名空间消解 | Accepted（已接受） | 词法语法、换行规则、名称解析、`.` 消解 | 显著换行与续行锚点已落地；点链由名称解析按值/模块/类型及接收者所有权分派。 |
| [0006](./rfcs/0006-option-result-lang-items.md) | `Option`/`Result` 与编译器内建认知的循环依赖 | Accepted（已接受） | lang item、`Option`、`Result`、标准库边界 | 接受编译器内建 carrier 身份 + `std.option`/`std.result` 公共模块契约；v0.1 不使用 `#[lang]` 属性。 |
| [0007](./rfcs/0007-unqualified-variant-access.md) | `Enum.Variant` 是否可简化为非限定 `Variant` | Accepted（已接受） | 枚举变体、prelude、名称解析、人体工学 | 仅核心 `Some/None/Ok/Err` 可非限定；局部符号优先，用户枚举仍需限定，限定核心写法继续兼容。 |
| [0008](./rfcs/0008-canonical-package-identity-and-aliases.md) | Canonical 包身份与依赖别名分离 | Accepted（已接受） | package identity、manifest、import | canonical id 固定为 `owner/package`；alias 仅控制局部 import，source 不参与语言身份。 |
| [0009](./rfcs/0009-reproducible-workspace-and-package-graphs.md) | 可复现的 Workspace、Package 与 Module 图 | Accepted（已接受） | workspace、dependency graph、lockfile | 使用三层 typed graph、稳定依赖序、workspace root lockfile、checksum 与 locked/offline/vendor 契约。 |
| [0010](./rfcs/0010-constrained-generics-and-static-interface-dispatch.md) | 受约束泛型与 Interface 静态分派 | Accepted（已接受） | interface、generics、monomorphization | 每个 type parameter 最多一个 interface bound，显式 concrete type argument，单态化静态分派。 |
| [0011](./rfcs/0011-c-ffi-safety-and-link-boundary.md) | C FFI 的安全、所有权与链接边界 | Accepted（已接受） | FFI、unsafe、CString、Opaque | extern 调用要求 call-site `unsafe`，使用显式 CString/Opaque 和 manifest linker metadata。 |
| [0012](./rfcs/0012-shared-semantic-identities-and-verified-rename.md) | 共享语义身份与类型检查后的 Rename | Accepted（已接受） | semantic API、LSP、rename | compiler 是语义事实源；reference 按声明/receiver owner 解析，rename edits 必须重过类型检查。 |
| [0013](./rfcs/0013-registry-protocol-and-package-integrity.md) | Registry 协议、认证与包完整性 | Accepted（已接受） | registry、metadata、checksum、auth | exact-version `/api/v1`、确定性 archive、双层 checksum、yank、Bearer token 与 verified HTTPS。 |
| [0014](./rfcs/0014-semver-resolution-and-conflict-explanations.md) | 语义化版本求解与冲突解释 | Accepted（已接受） | semver、resolver、lockfile | 已实现项目/工作区确定性单版本求解、精确锁定、离线 index cache 与可追踪最小冲突。 |
| [0015](./rfcs/0015-source-defined-standard-library-and-intrinsics.md) | 标准库源码化与受控 Intrinsic 身份 | Accepted（已接受） | standard library、intrinsic、bootstrap | canonical Nomo 源码定义标准库公共表面，工具链清单约束表示相关 intrinsic。 |
| [0016](./rfcs/0016-incremental-semantic-graph-and-cache.md) | 增量语义图与持久化缓存 | Accepted（已接受） | incremental compilation、LSP、cache | compiler-owned query graph 与原子、带 checksum、容量受控的 disk value 提供可验证失效及跨进程 check/codegen 复用。 |
| [0017](./rfcs/0017-target-triples-and-cross-compilation.md) | Target Triple、条件依赖与交叉编译 | Accepted（已接受） | target、cross compilation、linker | canonical target predicate 驱动完整 lockfile、过滤 graph、条件 FFI metadata 与已验证的 macOS/Linux cross-build。 |
| [0018](./rfcs/0018-package-signing-provenance-and-transparency.md) | 包签名、来源证明与透明日志 | Accepted（已接受） | signing、provenance、registry | 已实现 Ed25519 publisher 授权、provenance、pinned transparency key、双签名日志 key rotation、signed-head gossip、freshness policy、回滚/equivocation 检测与 lockfile evidence。 |
| [0019](./rfcs/0019-typed-ffi-handles-callbacks-and-bindings.md) | 类型化 FFI Handle、Callback 与 Binding | Accepted（已接受） | FFI、callback、C ABI | nominal handle、显式 null/ownership、受限 callback、target 校验 C layout 与确定性 binding 已实现。 |
| [0020](./rfcs/0020-manifest-v2-workspace-and-project-configuration.md) | Manifest v2、Workspace 成员资格与项目配置 | Accepted（已接受） | manifest、workspace、migration、trust | 显式 schema v2、经过验证的继承、严格 package identity、项目本地运营 policy 与确定 migration。 |
| [0021](./rfcs/0021-manifest-derived-module-roots.md) | 由 Manifest 派生模块根并映射依赖别名 | Proposed（已提案） | package declaration、module identity、dependency alias、migration | 源码根由自身 package name 派生；消费方 alias 只做 import 映射，内部身份继续使用 canonical package id。 |
| [0022](./rfcs/0022-structured-http-client-and-host-runtime.md) | 结构化 HTTP Client 与工具链托管 Host Runtime | Accepted（已接受） | HTTP、HTTPS、TLS、标准库、host runtime | 受限的结构化 HTTPS client 已实现，native FFI 被封装在工具链 runtime 内。 |
| [0023](./rfcs/0023-pull-based-http-streaming-and-sse.md) | Pull-Based HTTP 文本 Streaming 与 SSE | Accepted（已接受） | HTTP、HTTPS、streaming、SSE、取消、timeout | 已在不引入 async 语法的前提下实现受限同步文本/SSE 拉取、idle timeout 与 cooperative cancellation。 |
| [0024](./rfcs/0024-controlled-child-processes-and-stdio.md) | 受控子进程与多路复用标准 I/O | Proposed（已提案） | process、stdin、stdout、stderr、timeout、termination、MCP | 增加 shell-free 长生命周期 child handle、受限 queued stdin 与多路复用 output/exit event。 |

> 注：`0000-template.md` 为模板，不计入上表。
