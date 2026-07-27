# Nomo v0.1 Vision and Architecture Overview

> **Non-normative / 非规范性文档**
>
> This document explains the direction and architecture of Nomo Preview. It is
> not a language specification, API reference, release promise, or RFC status
> table. When it conflicts with the sources of truth linked below, those sources
> win.
>
> 本文说明 Nomo Preview 的方向与架构，不是语言规格、API 参考、发布承诺或 RFC
> 状态表。若本文与下列事实源冲突，以事实源为准。

Last reviewed against:

- `nomo` commit [`085da513ff6c042bd00571c49a6eb061722acf6f`](https://github.com/nomo-lang/nomo/commit/085da513ff6c042bd00571c49a6eb061722acf6f)
- `rfcs` commit [`2d9074ff6cf1fa790babdc76d142f2bdcb55a1a6`](https://github.com/nomo-lang/rfcs/commit/2d9074ff6cf1fa790babdc76d142f2bdcb55a1a6)

## English

### Positioning

Nomo is a preview programming language for predictable command-line tools,
automation, local services, and bounded Agent workloads. It favors explicit
effects, deterministic resource limits, readable diagnostics, and a portable
toolchain over a broad implicit runtime.

The project is useful today for controlled evaluation and development. It is
not yet a production-ready general-purpose service platform. Timestamped
snapshots may make breaking changes while syntax, runtime contracts, platform
coverage, packaging, and ecosystem gates converge.

### Compilation model

The native toolchain parses and checks Nomo source, lowers it through compiler
IR, emits readable C99, and invokes a target C compiler. C99 is the portable
implementation boundary for native targets, not an invitation for applications
to reimplement language semantics in handwritten C.

The browser path uses a restricted WebAssembly compiler/runtime. It deliberately
exposes fewer host capabilities than native builds. Unsupported process,
network, SQLite, or host operations fail through explicit capability errors;
the sandbox does not silently emulate them or evaluate secret-bearing operands
before rejecting them.

### Language model

The source model centers on:

- manifest-derived, lower-snake-case module roots;
- explicit imports and dependency aliases that do not rewrite package identity;
- value-oriented structs, enums, strings, arrays, and insertion-ordered maps;
- non-atomic ARC/COW for ordinary task-local managed values;
- explicit `Result<T, E>`, `Option<T>`, postfix `?`, and `panic`;
- constrained generics and static interface dispatch;
- explicit `unsafe` at the C FFI boundary;
- canonical omission of `-> void` on void-return declarations, while `void`
  remains a type/value and callable types retain their complete return type.

These bullets are orientation, not grammar. The bilingual specifications and
accepted RFCs define the actual contract.

### Direct-style suspension

Nomo's async direction uses `suspend fn` as an explicit effect. Calls remain
direct-style; there is no `await` expression. A normal function cannot call a
suspending function. Structured work is scoped and cancellation-aware rather
than detached by default.

The C99 backend lowers supported suspend call chains to stackless state
machines. Values live across suspension are stored in bounded frames and use
the same exactly-once ownership/drop rules as synchronous code. The implemented
surface is deliberately phased; Proposed RFCs may have executable slices
without the whole design being accepted or complete.

### Bounded Runtime

The native Runtime is designed around owner-affine executors, platform
reactors, bounded registration tables, bounded lazy blocking work, monotonic
timers, controlled child processes, bounded channels, and explicit lifecycle
counters. Current native slices cover epoll, kqueue, and IOCP paths for selected
operations. Browser WASM uses a host-driven single-threaded capability boundary.

“Bounded” is a correctness requirement: queue capacities, payload limits,
timeouts, handle generations, cancellation, late completion, and cleanup
behavior are part of the contract and test evidence. Internal benchmark results
are evidence for a particular gate; they are not a blanket production-readiness
claim.

### Ownership isolation

Ordinary managed values are task-local and use non-atomic ARC/COW. Cross-task
publication must be an explicit move through a compiler-known boundary. A
uniquely owned backing may move without copying; an aliased backing must detach
before publication. Borrowed values, guards, and owner-affine handles cannot
silently cross the boundary.

This keeps synchronous programs free of async runtime initialization and avoids
turning all collection reference counts into atomics. Broader `Send`, `Sync`,
`Freeze`, shared-lock, and cross-shard facilities remain gated by their RFC and
implementation evidence.

### Preview compatibility

Nomo does not have a stable `v0.1.0` release. Preview compatibility is expressed
through timestamped snapshots and pinned commits. A compatibility window must
name the accepted old form, its diagnostic or migration command, and the later
snapshot condition that removes it.

For the current syntax convergence:

- project module roots derive from `[package].name`;
- entry `src/main.nomo` declares the root directly;
- explicit declaration `-> void` remains parser-compatible while tools emit the
  omitted form;
- legacy `.main` roots are a one-snapshot migration surface governed by RFC
  0021 and `nomo fix module-roots`.

### Sources of truth

Use the narrowest authoritative source:

1. [`en/SPEC-v0.1.md`](en/SPEC-v0.1.md) for the English normative baseline;
2. [`zh-CN/SPEC-v0.1.md`](zh-CN/SPEC-v0.1.md) for the Chinese normative baseline;
3. accepted bilingual RFCs for decisions and their evidence;
4. [`RELEASE-GATE.md`](RELEASE-GATE.md) and
   [`VERSIONING.md`](VERSIONING.md) for readiness and compatibility;
5. compiler/runtime tests and protected CI for executable evidence;
6. this overview and repository READMEs for orientation only.

The original June 18 whitepaper is preserved as
[`archive/initial-whitepaper-2026-06-18.zh-CN.md`](archive/initial-whitepaper-2026-06-18.zh-CN.md).

## 中文

### 定位

Nomo 是一门处于 Preview 阶段的编程语言，面向可预测的命令行工具、自动化、本地服务与
有界 Agent 工作负载。它优先选择显式 effect、确定性资源边界、可读诊断和可移植工具链，
而不是范围宽泛的隐式 Runtime。

当前项目适合受控评估与开发，不是生产就绪的通用服务平台。语法、Runtime 契约、平台
覆盖、打包与生态门禁收敛前，时间戳 snapshot 仍可能包含破坏性变更。

### 编译模型

原生工具链解析并检查 Nomo 源码，经编译器 IR 降低后生成可读 C99，再调用目标 C
编译器。C99 是原生目标的可移植实现边界，不意味着应用应以手写 C 重做语言语义。

浏览器路径使用受限 WebAssembly 编译器与 Runtime，其 host capability 有意小于原生
目标。不支持的进程、网络、SQLite 或 host 操作通过明确 capability 错误失败；沙箱不会
静默模拟，也不会在拒绝前求值可能携带秘密的 operand。

### 语言模型

源码模型以 manifest 派生的 lower_snake_case 模块根、显式 import、值语义数据、
task-local 非原子 ARC/COW、显式 `Result`/`Option`/`?`、受约束泛型、静态 interface
dispatch 和受控 C FFI 为核心。无返回值声明规范性省略 `-> void`，但 `void` 类型和值
继续存在，callable type 仍写完整返回类型。

这些内容只是导航，不是语法定义；真实契约由双语 SPEC 与已接受 RFC 决定。

### Direct-style suspend

异步方向使用 `suspend fn` 显式标记 effect，调用保持 direct-style，不引入 `await`
表达式。普通函数不能调用 suspend 函数；并发工作默认受结构化 scope 和取消规则约束。

C99 后端把已支持的 suspend 调用链降低为 stackless state machine。跨 suspension
存活的值进入有界 frame，并继续遵守同步代码的 exactly-once 所有权与 drop 规则。
Proposed RFC 可以已有可执行 slice，但这不等于整篇设计已接受或全部实现。

### 有界 Runtime 与所有权隔离

原生 Runtime 围绕 owner-affine executor、平台 reactor、有界注册表、有界 lazy
blocking work、单调时钟 timer、受控子进程、有界 channel 与生命周期计数器构建。当前
原生 slice 对选定操作覆盖 epoll、kqueue 与 IOCP；浏览器 WASM 使用 host-driven
单线程 capability boundary。

普通 managed value 保持 task-local 非原子 ARC/COW。跨 task publication 必须经过
编译器已知的显式 move 边界；唯一 backing 可直接移动，存在别名时先 detach。borrow、
guard 与 owner-affine handle 不得隐式跨越边界。

资源上限、timeout、generation、取消、late completion 与清理行为都是正确性契约。
某个 benchmark gate 的内部结果不能外推为整体生产就绪结论。

### Preview 兼容政策

Nomo 尚无稳定 `v0.1.0`。Preview 兼容通过时间戳 snapshot 与固定 commit 表达。每个
兼容窗口都必须写明旧形式、诊断或迁移命令，以及后续 snapshot 的移除条件。

本次语法收敛中，项目模块根由 `[package].name` 派生，`src/main.nomo` 直接声明根；
显式声明级 `-> void` 仍可解析，但工具统一输出省略形式；旧 `.main` 根只保留一个
snapshot 的迁移窗口，由 RFC 0021 与 `nomo fix module-roots` 管理。

### 权威导航

事实源优先级为：双语 SPEC、已接受双语 RFC、`RELEASE-GATE.md`/`VERSIONING.md`、
编译器与 Runtime 测试及受保护 CI。本文与各仓库 README 只负责导航。

2026-06-18 的初始白皮书已保存为
[`archive/initial-whitepaper-2026-06-18.zh-CN.md`](archive/initial-whitepaper-2026-06-18.zh-CN.md)。
