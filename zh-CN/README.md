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
| [0024](./rfcs/0024-controlled-child-processes-and-stdio.md) | 受控子进程与多路复用标准 I/O | Accepted（已接受） | process、stdin、stdout、stderr、timeout、termination、MCP | 增加 shell-free 长生命周期 child handle、受限 queued stdin 与多路复用 output/exit event。 |
| [0025](./rfcs/0025-structured-json-values-and-construction.md) | 结构化 JSON Value、访问与构造 | Accepted（已接受） | JSON、标准库、Agent、Unicode、limit、C backend、browser WASM | 保持 `JsonValue` opaque，增加受限遍历与安全构造，并保证 native/browser parity。 |
| [0026](./rfcs/0026-isolated-native-tasks-and-cooperative-cancellation.md) | 隔离式 Native Task 与协作取消 | Accepted（已接受） | concurrency、task、isolation、cancellation、C99 backend、Agent | 通过 copied string boundary 与 compile-time task-safety check 运行受限顶层 native task，不引入 shared managed value 或 async 语法。 |
| [0027](./rfcs/0027-bundled-sqlite-persistence-and-pull-queries.md) | 内置 SQLite 持久化与 Pull-Based Query | Accepted（已接受） | SQLite、持久化、database、标准库、C99 backend、Agent | 在工具链内固定并按需编译 SQLite，提供受限参数化执行与 pull-based row，应用侧无需 FFI。 |
| [0028](./rfcs/0028-bounded-json-rpc-and-newline-stdio-framing.md) | 受限 JSON-RPC 与换行分帧标准 I/O | Accepted（已接受） | JSON-RPC、MCP、stdio、framing、process、JSON、Agent | 验证受限 JSON-RPC 2.0 envelope，并以 opaque value state 增量解码换行分帧 stdio。 |
| [0029](./rfcs/0029-bounded-utc-cron-schedule-calculation.md) | 受限 UTC Cron Schedule 计算 | Accepted（已接受） | cron、scheduling、time、Agent、bounds、browser WASM | 解析受限五字段 UTC schedule，并在不引入 process-global scheduler 的情况下确定性计算匹配分钟。 |
| [0030](./rfcs/0030-collection-literals-indexing-and-ordered-map.md) | 集合字面量、索引与有序 Map | Accepted（已接受） | 数组、索引、COW、泛型、Map、确定性、Agent | 增加数组字面量、检查式 COW 安全索引和唯一的插入有序通用 Map，不重复提供 HashMap。 |
| [0031](./rfcs/0031-direct-style-suspend-functions-and-structured-concurrency.md) | 直写式挂起函数与结构化并发 | Proposed（已提案） | suspend 函数、effect、stackless coroutine、取消、C99 | 使用显式 `suspend fn`、直写调用、词法 task scope 与 exactly-once stackless-frame cleanup。 |
| [0032](./rfcs/0032-sharded-executor-reactor-and-blocking-pool.md) | 分片 Executor、Reactor 与 Blocking Pool | Proposed（已提案） | executor、reactor、epoll、kqueue、IOCP、WASM、affinity | 从 current-thread reactor 起步，通过 owner-affine shard 扩展，并把阻塞工作隔离到 bounded lazy pool。 |
| [0033](./rfcs/0033-task-ownership-transfer-and-concurrent-values.md) | 任务所有权转移与并发值 | Proposed（已提案） | Send、Sync、Local、Freeze、channel、lock、collection | 普通 ARC/COW 保持 task-local；跨 task 使用 consuming move/detach 或显式 frozen/shared/concurrent storage。 |
| [0034](./rfcs/0034-async-runtime-acceptance-and-benchmark-gates.md) | 异步 Runtime 验收与基准门禁 | Proposed（已提案） | 性能、内存、Go 对比、低配设备、跨平台 | 强制验证 unused/ready-path 成本、正确性/泄漏、平台矩阵与公平可复现 Agent benchmark。 |
| [0035](./rfcs/0035-monotonic-suspend-timers-and-blocking-sleep-migration.md) | 单调时钟挂起 Timer 与阻塞 Sleep 迁移 | Proposed（已提案） | suspend function、timer、monotonic clock、blocking compatibility、C99 | 增加唯一有界 `task.sleep(Duration)` timer，并在不破坏 legacy 同步代码的前提下禁止 async worker 调用阻塞 `time.sleep*`。 |
| [0036](./rfcs/0036-bounded-channels-publication-moves-and-static-select.md) | 有界 Channel、Publication Move 与静态 Select | Proposed（已提案） | channel、select、move publication、Send、backpressure、cancellation、C99 | 在实现前固定类型化 channel API、consuming publication boundary、确定性 static select 语法与分阶段 ownership/correctness 门禁。 |
| [0037](./rfcs/0037-owner-affine-async-tcp-client-and-blocking-migration.md) | Owner-affine async TCP client 与 blocking migration | Proposed（已提案） | async TCP、reactor、owner affinity、bounded I/O、DNS | 定义 bounded suspend connect/read/write、generation-checked stream ownership、显式 blocking 迁移与 native platform gate。 |
| [0038](./rfcs/0038-owner-affine-async-process-pipes-and-blocking-migration.md) | Owner-affine async process pipe 与 blocking migration | Proposed（已提案） | process、async pipe、reactor、MCP、owner affinity | 定义 bounded suspend process start/event progress、owner-local pipe、显式 blocking 迁移与 native platform gate。 |
| [0039](./rfcs/0039-loop-carried-coroutine-state-and-suspension-safe-mutation.md) | Loop-carried coroutine state 与 suspension-safe mutation | Proposed（已提案） | suspend function、loop、mutable local、liveness、ARC、C99、MCP | 允许 task-local owned mutable state 穿过受限 suspending loop，同时禁止 borrow/guard 跨挂起且不增加 atomic 成本。 |
| [0040](./rfcs/0040-owner-affine-async-http-and-sse-migration.md) | Owner-affine async HTTP/HTTPS、SSE 与 blocking migration | Proposed（已提案） | HTTP、HTTPS、TLS、SSE、reactor、owner affinity、connection reuse | 把受限 client 与 stream API 迁移为 suspend operation，采用 owner-local transport progress、显式 blocking compatibility 与 native platform gate。 |
| [0041](./rfcs/0041-canonical-implicit-void-return-declarations.md) | Canonical 隐式 `void` 返回声明 | Proposed（已提案） | function declaration、method、suspend、interface、extern、formatter、LSP | Declaration canonical 省略 `-> void`，同时保留显式 parser 兼容与完整 callable/type/value use。 |

> 注：`0000-template.md` 为模板，不计入上表。
