# Nomo v0.1 Whitepaper

> Languages: English summary and Chinese summary in one repository-level document.

---

## 中文摘要

Nomo v0.1 的目标不是一次性设计一门完整的大语言，而是交付一条可以被实现、测试和讨论持续校正的 Stage 0 闭环：从 `.nomo` 源码出发，经前端检查、类型与可变性分析、C99 转译、系统 C 编译器链接，最终运行可执行程序。

这份白皮书是 `rfcs` 仓库内的总览文档。它说明 v0.1 的设计边界、工程取舍和已经落地的 RFC 决议；详细的可执行规格以 [中文规格基线](zh-CN/SPEC-v0.1.md) 和 [English specification baseline](en/SPEC-v0.1.md) 为准，后续演进问题记录在各 RFC 的「后续问题」中。

### 1. 设计目标

Nomo v0.1 追求的是“最小完整性”：

- 语言核心足够表达真实的小程序：包、导入、函数、结构体、枚举、泛型、`match`、`Result`、`Option`、数组、字符串。
- 编译链路足够真实：`nomo check` 做静态检查，`nomo build` 生成可读 C99，`nomo run` 构建并运行。
- 错误与诊断可被工具消费：除人类可读输出外，诊断还应有稳定 JSON 结构。
- 设计演进可追踪：所有需要正式决策的争议进入 RFC，而不是散落在临时讨论里。

v0.1 明确不做协程、GPU、WebAssembly、裸机、自举、LLVM/Cranelift 原生后端、完整 Rust 风格 trait/interface 系统或完整 lifetime 系统；当前只提供单 interface bound 的静态约束。它先把“语言规格、编译器实现、标准库、示例、测试、RFC 决策”串成一条能跑通的线。

### 2. 语言模型

Nomo 采用显式包与导入模型，符号来源必须可追踪；变量默认不可变，通过 `let mut` 和调用处 `mut` 明确表达可变性。函数允许尾表达式返回，也允许显式 `return` 做早退。

类型系统在 v0.1 覆盖基础类型、结构体、枚举、泛型函数与泛型类型。`Result<T, E>` 表达业务失败，`Option<T>` 表达可能缺值；程序缺陷由 `panic` 处理，不引入异常展开。

`match` 要求穷尽所有枚举变体并继续禁用 `_` 通配分支；`let else`、`if let` 与后缀 `?` 用于压平常见嵌套。核心 prelude 允许非限定 `Some`/`None`/`Ok`/`Err`，用户枚举仍保持限定形式。

### 3. 编译器与运行时

v0.1 的编译链路面向 C99：

```text
.nomo source
  -> Lexer
  -> Parser
  -> AST
  -> Name Resolution
  -> Type Check + Mutability Check
  -> HIR
  -> C99 Codegen
  -> cc / clang / gcc
  -> Executable
```

选择 C99 后端的理由是降低 Stage 0 的实现风险：C 编译器普遍可用，生成物便于检查，运行时布局也可以通过 C 结构体和标签联合体直接验证。后续是否引入 LLVM、Cranelift 或其它后端，应建立在 v0.1 语义已稳定的基础上。

内存模型以值语义为用户视角。纯值按 C 值传递；`string` 与 `Array<T>` 是标准库托管值，其中 `string` 不可变，`Array<T>` 的写操作需要与引用计数、写时复制和可变借用检查协调。这是 v0.1 实现风险最高的区域之一，因此由 RFC 0003 与 RFC 0004 共同约束。

### 4. 标准库边界

v0.1 从闭环必需能力起步，当前实现已经覆盖：

- `std.io`、`std.fs`、`std.env`：输入输出、文件系统与进程环境。
- `std.result` / `std.option`：错误与缺值建模。
- `std.array` / `std.string` / `std.collections`：托管容器与字符串。
- `std.path`、`std.process`、`std.time`、`std.math`、`std.num`：系统与数值 helper。
- `std.json`、`std.net`、`std.http`、`std.regex`、`std.hash`、`std.crypto`：数据、网络与常用运行时能力。
- `std.testing`、`std.debug`、`std.log`、`std.ffi`：测试、诊断、日志与原生边界。

标准库不是“语法糖堆放处”。`Option`、`Result`、`Array`、`string` 同时影响类型检查、穷尽性、C 后端和运行时布局。当前 `Option`/`Result` 采用编译器内建 carrier 身份，`std.option`/`std.result` 保持公共模块契约；v0.1 不依赖 `#[lang]` 属性或可独立编译的标准库源码层。

### 5. 已接受的 RFC 决议

当前十三篇 RFC 均已按实现事实完成决议，并同步进入规格基线：

| RFC | 主题 | 已接受结论 |
| --- | --- | --- |
| [0001](zh-CN/rfcs/0001-error-propagation-and-conversion.md) | 错误传播与转换 | `?` 保持同 carrier 传播；跨层转换显式使用 `map_err(named_converter)?`。 |
| [0002](zh-CN/rfcs/0002-match-wildcard-and-nesting.md) | `match` 通配与嵌套 | 禁用 `_`，提供 `let else`、`if let` 与 Option `?`。 |
| [0003](zh-CN/rfcs/0003-arc-cow-runtime-cost.md) | ARC/COW 成本 | `string` 使用不可变 RC；`Array<T>` 使用非原子 RC+COW。 |
| [0004](zh-CN/rfcs/0004-mutable-borrow-uniqueness.md) | 可变借用唯一性 | 借用限定为单调用表达式并检查路径冲突，不引入 lifetime。 |
| [0005](zh-CN/rfcs/0005-newline-sensitivity-and-dot-resolution.md) | 换行与点消解 | 接受显著换行、续行锚点与统一点链的名称解析分派。 |
| [0006](zh-CN/rfcs/0006-option-result-lang-items.md) | `Option`/`Result` 内建身份 | 编译器内建 carrier 身份，`std.*` 保持公共模块契约。 |
| [0007](zh-CN/rfcs/0007-unqualified-variant-access.md) | 非限定枚举变体 | 仅核心四个变体进入 prelude，局部符号优先，限定写法兼容。 |
| [0008](zh-CN/rfcs/0008-canonical-package-identity-and-aliases.md) | 包身份与 alias | canonical id、局部 import alias 与物理 source 分层。 |
| [0009](zh-CN/rfcs/0009-reproducible-workspace-and-package-graphs.md) | 可复现依赖图 | 三层 typed graph、root lockfile、checksum 与 offline/vendor 契约。 |
| [0010](zh-CN/rfcs/0010-constrained-generics-and-static-interface-dispatch.md) | 受约束泛型 | 单 interface bound、显式 concrete type argument 与静态分派。 |
| [0011](zh-CN/rfcs/0011-c-ffi-safety-and-link-boundary.md) | C FFI 边界 | call-site unsafe、CString/Opaque 与 package linker metadata。 |
| [0012](zh-CN/rfcs/0012-shared-semantic-identities-and-verified-rename.md) | 共享语义查询 | compiler-owned declaration/member identity 与重检 rename。 |
| [0013](zh-CN/rfcs/0013-registry-protocol-and-package-integrity.md) | Registry 协议 | exact version、metadata/checksum、认证、yank 与 verified HTTPS。 |

这些 RFC 不替代规格基线。它们记录原始问题、备选方案、最终决议、实现状态与后续问题；规格基线描述当前对外契约。

后续实现 RFC 中，[0014](zh-CN/rfcs/0014-semver-resolution-and-conflict-explanations.md) 版本求解、[0015](zh-CN/rfcs/0015-source-defined-standard-library-and-intrinsics.md) 标准库源码化、[0017](zh-CN/rfcs/0017-target-triples-and-cross-compilation.md) 条件依赖与真实交叉编译、[0018](zh-CN/rfcs/0018-package-signing-provenance-and-transparency.md) 包签名与透明日志验证，以及 [0019](zh-CN/rfcs/0019-typed-ffi-handles-callbacks-and-bindings.md) 类型化 FFI 已达到接受门槛；[0016](zh-CN/rfcs/0016-incremental-semantic-graph-and-cache.md) 增量语义仍保持 `Proposed`。RFC 0018 的公共日志 key rotation、gossip 与 proof freshness 属于后续生产运营加固。

### 6. 成立性判断

按 v0.1 的定位，Nomo 的设计是成立的：它没有试图在首个版本同时解决并发、异构计算、完整泛型约束和复杂借用系统，而是把范围压到一条可交付的编译链路。它的主要风险不在愿景，而在几个实现密集区是否被诚实拆分：

- `Array<T>` 的引用计数与写时复制不能只停留在口号，必须有运行时布局、释放点和早退路径测试。
- `mut` 借用必须明确存活期边界，否则会在“像 Rust 但没有 lifetime”的区域变得含糊。
- `?` 的错误类型转换如果没有最小方案，会削弱错误处理的人体工学。
- `Option`/`Result` 的标准库身份与编译器内建认知需要稳定锚点。

因此，v0.1 接下来的重点不是重复讨论已经落地的决议，而是保持 check/build/run 闭环、规格、测试、诊断文档和编辑器语义一致，并完成发布稳定化。

---

## English Summary

Nomo v0.1 is not an attempt to design a complete large language in one step. Its goal is to deliver an implementable, testable, and reviewable Stage 0 loop: `.nomo` source goes through frontend checks, type and mutability analysis, C99 transpilation, system C compilation, and execution.

This whitepaper is the repository-level overview for the `rfcs` repository. It describes the v0.1 boundary, engineering trade-offs, and implemented RFC decisions. The detailed executable baseline is maintained in the [Chinese specification baseline](zh-CN/SPEC-v0.1.md) and [English specification baseline](en/SPEC-v0.1.md); future evolution is tracked in each RFC's follow-up questions.

### 1. Design Goals

Nomo v0.1 optimizes for minimal completeness:

- The language core is expressive enough for real small programs: packages, imports, functions, structs, enums, generics, `match`, `Result`, `Option`, arrays, and strings.
- The compiler pipeline is real: `nomo check` performs static checks, `nomo build` emits readable C99, and `nomo run` builds and executes.
- Diagnostics are tool-friendly: stable JSON diagnostics are required alongside human-readable output.
- Design evolution is traceable: formal decisions live in RFCs instead of scattered temporary discussions.

v0.1 explicitly excludes coroutines, GPU targets, WebAssembly, bare metal, self-hosting, LLVM/Cranelift native backends, a full Rust-style trait/interface system, and a full lifetime system; the current model supports one static interface bound per type parameter. It first connects specification, implementation, standard library, examples, tests, and RFC decisions into one working loop.

### 2. Language Model

Nomo uses explicit packages and imports, and every symbol origin must be traceable. Bindings are immutable by default; `let mut` and call-site `mut` make mutability explicit. Functions support both tail-expression returns and explicit early `return`.

The v0.1 type system covers basic types, structs, enums, generic functions, and generic types. `Result<T, E>` represents business failure, `Option<T>` represents absence, and `panic` handles program defects. Exception unwinding is not part of v0.1.

`match` is exhaustive and keeps `_` wildcard arms disabled. `let else`, `if let`, and postfix `?` flatten common nesting. The core prelude permits unqualified `Some`/`None`/`Ok`/`Err`, while user enums remain qualified.

### 3. Compiler and Runtime

The v0.1 compiler targets C99:

```text
.nomo source
  -> Lexer
  -> Parser
  -> AST
  -> Name Resolution
  -> Type Check + Mutability Check
  -> HIR
  -> C99 Codegen
  -> cc / clang / gcc
  -> Executable
```

C99 lowers Stage 0 risk: C compilers are widely available, generated code is inspectable, and runtime layouts can be tested through C structs and tagged unions. LLVM, Cranelift, or other backends should come after the v0.1 semantics settle.

The user-facing memory model is value semantics. Pure values use C value passing; `string` and `Array<T>` are standard-library-managed values. `string` is immutable, while `Array<T>` writes must coordinate reference counting, copy-on-write, and mutable-borrow checks. This is one of the highest-risk implementation areas and is therefore constrained by RFC 0003 and RFC 0004.

### 4. Standard Library Boundary

The v0.1 standard library started with the closed-loop minimum and now covers:

- `std.io`, `std.fs`, `std.env`: I/O, filesystem, and process environment.
- `std.result` / `std.option`: failure and absence modeling.
- `std.array` / `std.string` / `std.collections`: managed containers and strings.
- `std.path`, `std.process`, `std.time`, `std.math`, `std.num`: system and numeric helpers.
- `std.json`, `std.net`, `std.http`, `std.regex`, `std.hash`, `std.crypto`: data, network, and common runtime capabilities.
- `std.testing`, `std.debug`, `std.log`, `std.ffi`: testing, diagnostics, logging, and native boundaries.

The standard library is not a dumping ground for syntax sugar. `Option`, `Result`, `Array`, and `string` affect type checking, exhaustiveness, C codegen, and runtime layout. `Option`/`Result` currently use compiler-owned carrier identities while `std.option`/`std.result` remain public module contracts; v0.1 does not depend on a `#[lang]` attribute or independently compiled standard-library source layer.

### 5. Accepted RFC Decisions

All thirteen RFCs now record accepted decisions reflected by the implementation baseline:

| RFC | Topic | Accepted decision |
| --- | --- | --- |
| [0001](en/rfcs/0001-error-propagation-and-conversion.md) | Error propagation and conversion | `?` preserves the carrier; cross-layer conversion uses explicit `map_err(named_converter)?`. |
| [0002](en/rfcs/0002-match-wildcard-and-nesting.md) | `match` wildcard and nesting | Keep `_` disabled and provide `let else`, `if let`, and Option `?`. |
| [0003](en/rfcs/0003-arc-cow-runtime-cost.md) | ARC/COW cost | Immutable RC for `string`; non-atomic RC+COW for `Array<T>`. |
| [0004](en/rfcs/0004-mutable-borrow-uniqueness.md) | Mutable-borrow uniqueness | One-call-expression borrows with path-conflict checks and no lifetimes. |
| [0005](en/rfcs/0005-newline-sensitivity-and-dot-resolution.md) | Newlines and dot resolution | Significant newlines, continuation anchors, and name-resolved uniform dot chains. |
| [0006](en/rfcs/0006-option-result-lang-items.md) | `Option`/`Result` identities | Compiler-owned carriers with public `std.*` module contracts. |
| [0007](en/rfcs/0007-unqualified-variant-access.md) | Unqualified enum variants | Only the four core variants enter the prelude; local names win and qualified forms remain compatible. |
| [0008](en/rfcs/0008-canonical-package-identity-and-aliases.md) | Package identity and aliases | Separate canonical ids, package-local import aliases, and physical sources. |
| [0009](en/rfcs/0009-reproducible-workspace-and-package-graphs.md) | Reproducible dependency graphs | Three typed graph layers, root lockfiles, checksums, and offline/vendor contracts. |
| [0010](en/rfcs/0010-constrained-generics-and-static-interface-dispatch.md) | Constrained generics | One interface bound, explicit concrete type arguments, and static dispatch. |
| [0011](en/rfcs/0011-c-ffi-safety-and-link-boundary.md) | C FFI boundary | Call-site unsafe, CString/Opaque, and package linker metadata. |
| [0012](en/rfcs/0012-shared-semantic-identities-and-verified-rename.md) | Shared semantic queries | Compiler-owned declaration/member identity and rechecked rename. |
| [0013](en/rfcs/0013-registry-protocol-and-package-integrity.md) | Registry protocol | Exact versions, metadata/checksums, authentication, yank, and verified HTTPS. |

These RFCs do not replace the specification baseline. They record the original problem, alternatives, final decision, implementation status, and follow-up questions; the specification baseline states the current public contract.

Among the follow-up implementation RFCs, [0014](en/rfcs/0014-semver-resolution-and-conflict-explanations.md) version solving, [0015](en/rfcs/0015-source-defined-standard-library-and-intrinsics.md) source-defined standard library, [0017](en/rfcs/0017-target-triples-and-cross-compilation.md) conditional dependencies and real cross-builds, [0018](en/rfcs/0018-package-signing-provenance-and-transparency.md) package signing and transparency verification, and [0019](en/rfcs/0019-typed-ffi-handles-callbacks-and-bindings.md) typed FFI have met their acceptance gates. [0016](en/rfcs/0016-incremental-semantic-graph-and-cache.md) incremental semantics remains `Proposed`. RFC 0018 public-log key rotation, gossip, and proof freshness remain production-operations hardening work.

### 6. Viability

Given the v0.1 positioning, the Nomo design is viable. It does not try to solve concurrency, heterogeneous computing, full generic constraints, and complex borrowing in the first version. Instead, it narrows the scope to a deliverable compiler loop. The main risk is not the vision itself, but whether the implementation-heavy areas are split honestly:

- `Array<T>` reference counting and copy-on-write need runtime layout, release points, and early-return tests.
- `mut` borrowing needs a precise lifetime boundary, otherwise the design becomes vague in the area that resembles Rust without exposing lifetimes.
- `?` needs a minimal error-conversion story, or its ergonomics will be weak in real layered code.
- `Option`/`Result` need a stable anchor between standard-library identity and compiler awareness.

The next v0.1 priority is not to reopen decisions already implemented, but to keep the check/build/run loop, specification, tests, diagnostic docs, and editor semantics aligned while completing release stabilization.
