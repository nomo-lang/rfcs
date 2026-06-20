# Nomo v0.1 Whitepaper

> Languages: English summary and Chinese summary in one repository-level document.

---

## 中文摘要

Nomo v0.1 的目标不是一次性设计一门完整的大语言，而是交付一条可以被实现、测试和讨论持续校正的 Stage 0 闭环：从 `.nomo` 源码出发，经前端检查、类型与可变性分析、C99 转译、系统 C 编译器链接，最终运行可执行程序。

这份白皮书是 `rfcs` 仓库内的总览文档。它说明 v0.1 的设计边界、工程取舍和 RFC 决策轴；详细的可执行规格以 [中文规格基线](zh-CN/SPEC-v0.1.md) 和 [English specification baseline](en/SPEC-v0.1.md) 为准，具体待决问题以各 RFC 为准。

### 1. 设计目标

Nomo v0.1 追求的是“最小完整性”：

- 语言核心足够表达真实的小程序：包、导入、函数、结构体、枚举、泛型、`match`、`Result`、`Option`、数组、字符串。
- 编译链路足够真实：`nomo check` 做静态检查，`nomo build` 生成可读 C99，`nomo run` 构建并运行。
- 错误与诊断可被工具消费：除人类可读输出外，诊断还应有稳定 JSON 结构。
- 设计演进可追踪：所有需要正式决策的争议进入 RFC，而不是散落在临时讨论里。

v0.1 明确不做协程、GPU、WebAssembly、裸机、自举、LLVM/Cranelift 原生后端、完整 trait/interface 约束系统或完整 lifetime 系统。它先把“语言规格、编译器实现、标准库、示例、测试、RFC 决策”串成一条能跑通的线。

### 2. 语言模型

Nomo 采用显式包与导入模型，符号来源必须可追踪；变量默认不可变，通过 `let mut` 和调用处 `mut` 明确表达可变性。函数允许尾表达式返回，也允许显式 `return` 做早退。

类型系统在 v0.1 覆盖基础类型、结构体、枚举、泛型函数与泛型类型。`Result<T, E>` 表达业务失败，`Option<T>` 表达可能缺值；程序缺陷由 `panic` 处理，不引入异常展开。

`match` 默认要求穷尽所有枚举变体，通配分支、嵌套解构、非限定变体等人体工学问题由 RFC 分层讨论，避免在 v0.1 初期把便利性和可解释性混在一起。

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

v0.1 标准库只覆盖闭环必需能力：

- `std.io`：输出。
- `std.fs`：最小文件读写与错误类型。
- `std.env`：环境变量读取。
- `std.result` / `std.option`：错误与缺值建模。
- `std.array`：动态数组。
- `std.string`：字符串基础操作。

标准库不是“语法糖堆放处”。`Option`、`Result`、`Array`、`string` 这类类型同时影响类型检查、穷尽性、C 后端和运行时布局，因此哪些内容保持普通库类型、哪些内容成为编译器可识别的 lang item，需要由 RFC 明确。

### 5. RFC 决策轴

当前 v0.1 的核心待决问题集中在七条线上：

| RFC | 主题 | 决策轴 |
| --- | --- | --- |
| [0001](zh-CN/rfcs/0001-error-propagation-and-conversion.md) | 错误传播与转换 | `?` 是否需要显式 `map_err` 或后续自动转换机制 |
| [0002](zh-CN/rfcs/0002-match-wildcard-and-nesting.md) | `match` 通配与嵌套 | 穷尽性与人体工学如何平衡 |
| [0003](zh-CN/rfcs/0003-arc-cow-runtime-cost.md) | ARC/COW 成本 | `string` 与 `Array<T>` 的运行时策略如何收敛 |
| [0004](zh-CN/rfcs/0004-mutable-borrow-uniqueness.md) | 可变借用唯一性 | 不引入 lifetime 的前提下做到多强的别名检查 |
| [0005](zh-CN/rfcs/0005-newline-sensitivity-and-dot-resolution.md) | 换行与点消解 | 显著换行和 `.` 统一访问如何落地 |
| [0006](zh-CN/rfcs/0006-option-result-lang-items.md) | `Option`/`Result` lang item | 标准库定义与编译器认知如何解耦又对齐 |
| [0007](zh-CN/rfcs/0007-unqualified-variant-access.md) | 非限定枚举变体 | `Ok`/`Err`/`Some`/`None` 是否进入 prelude |

这些 RFC 不替代规格基线。它们用于记录争议、备选方案、倾向建议和状态流转；一旦 RFC 被接受，对应变更应同步进入规格基线和实现。

### 6. 成立性判断

按 v0.1 的定位，Nomo 的设计是成立的：它没有试图在首个版本同时解决并发、异构计算、完整泛型约束和复杂借用系统，而是把范围压到一条可交付的编译链路。它的主要风险不在愿景，而在几个实现密集区是否被诚实拆分：

- `Array<T>` 的引用计数与写时复制不能只停留在口号，必须有运行时布局、释放点和早退路径测试。
- `mut` 借用必须明确存活期边界，否则会在“像 Rust 但没有 lifetime”的区域变得含糊。
- `?` 的错误类型转换如果没有最小方案，会削弱错误处理的人体工学。
- `Option`/`Result` 的标准库身份与编译器内建认知需要稳定锚点。

因此，v0.1 的合理推进方式是：先保住 check/build/run 闭环和规格-测试一致性，再逐个接受或推迟 RFC 中的争议点。只要 RFC 决策能持续回写规格与实现，这份架构可以作为一个小而真实的语言起点。

---

## English Summary

Nomo v0.1 is not an attempt to design a complete large language in one step. Its goal is to deliver an implementable, testable, and reviewable Stage 0 loop: `.nomo` source goes through frontend checks, type and mutability analysis, C99 transpilation, system C compilation, and execution.

This whitepaper is the repository-level overview for the `rfcs` repository. It describes the v0.1 boundary, engineering trade-offs, and RFC decision axes. The detailed executable baseline is maintained in the [Chinese specification baseline](zh-CN/SPEC-v0.1.md) and [English specification baseline](en/SPEC-v0.1.md); each pending design decision is tracked by its RFC.

### 1. Design Goals

Nomo v0.1 optimizes for minimal completeness:

- The language core is expressive enough for real small programs: packages, imports, functions, structs, enums, generics, `match`, `Result`, `Option`, arrays, and strings.
- The compiler pipeline is real: `nomo check` performs static checks, `nomo build` emits readable C99, and `nomo run` builds and executes.
- Diagnostics are tool-friendly: stable JSON diagnostics are required alongside human-readable output.
- Design evolution is traceable: formal decisions live in RFCs instead of scattered temporary discussions.

v0.1 explicitly excludes coroutines, GPU targets, WebAssembly, bare metal, self-hosting, LLVM/Cranelift native backends, a full trait/interface constraint system, and a full lifetime system. It first connects specification, implementation, standard library, examples, tests, and RFC decisions into one working loop.

### 2. Language Model

Nomo uses explicit packages and imports, and every symbol origin must be traceable. Bindings are immutable by default; `let mut` and call-site `mut` make mutability explicit. Functions support both tail-expression returns and explicit early `return`.

The v0.1 type system covers basic types, structs, enums, generic functions, and generic types. `Result<T, E>` represents business failure, `Option<T>` represents absence, and `panic` handles program defects. Exception unwinding is not part of v0.1.

`match` is exhaustive by default. Wildcard arms, nested destructuring, and unqualified variants are discussed separately through RFCs so that ergonomics and explainability remain distinguishable.

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

The v0.1 standard library only covers what the closed loop needs:

- `std.io`: output.
- `std.fs`: minimal file I/O and error types.
- `std.env`: environment variable access.
- `std.result` / `std.option`: failure and absence modeling.
- `std.array`: dynamic arrays.
- `std.string`: basic string operations.

The standard library is not a dumping ground for syntax sugar. Types such as `Option`, `Result`, `Array`, and `string` also affect type checking, exhaustiveness, C codegen, and runtime layout. RFCs decide which parts remain ordinary library definitions and which parts become compiler-recognized lang items.

### 5. RFC Decision Axes

The current v0.1 open decisions concentrate around seven tracks:

| RFC | Topic | Decision axis |
| --- | --- | --- |
| [0001](en/rfcs/0001-error-propagation-and-conversion.md) | Error propagation and conversion | Whether `?` needs explicit `map_err` or later automatic conversion |
| [0002](en/rfcs/0002-match-wildcard-and-nesting.md) | `match` wildcard and nesting | How to balance exhaustiveness and ergonomics |
| [0003](en/rfcs/0003-arc-cow-runtime-cost.md) | ARC/COW cost | How to narrow the runtime strategy for `string` and `Array<T>` |
| [0004](en/rfcs/0004-mutable-borrow-uniqueness.md) | Mutable-borrow uniqueness | How much alias checking is possible without lifetimes |
| [0005](en/rfcs/0005-newline-sensitivity-and-dot-resolution.md) | Newlines and dot resolution | How significant newlines and unified `.` access land |
| [0006](en/rfcs/0006-option-result-lang-items.md) | `Option`/`Result` lang items | How standard-library definitions and compiler awareness align |
| [0007](en/rfcs/0007-unqualified-variant-access.md) | Unqualified enum variants | Whether `Ok`/`Err`/`Some`/`None` enter the prelude |

These RFCs do not replace the specification baseline. They record disputes, alternatives, recommendations, and status transitions. Once an RFC is accepted, the corresponding change should be reflected in both the specification baseline and the implementation.

### 6. Viability

Given the v0.1 positioning, the Nomo design is viable. It does not try to solve concurrency, heterogeneous computing, full generic constraints, and complex borrowing in the first version. Instead, it narrows the scope to a deliverable compiler loop. The main risk is not the vision itself, but whether the implementation-heavy areas are split honestly:

- `Array<T>` reference counting and copy-on-write need runtime layout, release points, and early-return tests.
- `mut` borrowing needs a precise lifetime boundary, otherwise the design becomes vague in the area that resembles Rust without exposing lifetimes.
- `?` needs a minimal error-conversion story, or its ergonomics will be weak in real layered code.
- `Option`/`Result` need a stable anchor between standard-library identity and compiler awareness.

The right way to advance v0.1 is to preserve the check/build/run loop and specification-test consistency, then accept or defer the RFC decisions one by one. As long as accepted RFCs are reflected back into the specification and implementation, this architecture is a sound small starting point for the language.
