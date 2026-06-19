# Nomo v0.1 规格基线

> 语言 / Language: 中文 | [English](../en/SPEC-v0.1.md)

> **状态**：Draft baseline
> **用途**：作为本 RFC 仓库内所有 RFC 的共同讨论基线。
> **原则**：先定义可实现、可测试、可交付的 v0.1 闭环，再通过 RFC 演进语言能力。

---

## 0. 摘要

Nomo v0.1 的目标是交付一个最小但完整的 Stage 0 编译链路：

1. `nomo new` 创建项目。
2. `nomo check` 完成语法、名称解析、类型与可变性检查。
3. `nomo build` 调用 `nomoc`，将 `.nomo` 源码转译为 C99。
4. 系统 C 编译器生成可执行文件。
5. `nomo run` 构建并运行示例程序。

v0.1 不追求功能面最大化，而追求规格、实现、测试和 RFC 决策闭环。

---

## 1. v0.1 交付边界

### 1.1 必须交付

| 模块 | 交付内容 | 验收方式 |
| --- | --- | --- |
| 工程工具 | `nomo new`、`nomo check`、`nomo build`、`nomo run` | 示例项目可创建、检查、构建、运行 |
| 编译器前端 | Lexer、Parser、AST、语法诊断 | golden tests 稳定 |
| 名称解析 | 包、导入、类型、函数、字段、枚举变体解析 | 成功/失败样例覆盖 |
| 类型检查 | 基础类型、函数、结构体、枚举、泛型、`Result`、`Option` | 类型检查测试通过 |
| 可变性检查 | `let mut`、调用处 `mut`、可变借用唯一性 | Mutability tests 覆盖 |
| C99 后端 | HIR/C IR 到可读 C99 | 生成 C 可由 `clang` 或 `gcc` 编译 |
| 最小标准库 | `std.io`、`std.fs`、`std.env`、`std.result`、`std.option`、`std.array`、`std.string` | 示例程序可用 |
| JSON 诊断 | 稳定机器可读错误结构 | 快照测试覆盖 |

### 1.2 明确不属于 v0.1

- `go` 协程、`chan<T>`、隐式 Context。
- GPU Kernel、PTX、SPIR-V。
- WebAssembly、裸机、GUI。
- 完整 Tensor、BigDecimal、包发布生态。
- 自举编译器。
- LLVM / Cranelift 原生后端。
- 完整 trait/interface 约束系统。
- 完整 lifetime/区域借用系统。

---

## 2. 语言核心

### 2.1 文件、包与导入

每个 `.nomo` 文件属于一个包：

```rust
package app.main

import std.io
import std.fs
import std.result.Result
```

v0.1 支持导入包或具体类型/函数。不支持通配符导入。所有符号来源必须可追踪。

### 2.2 绑定与可变性

```rust
let name = "Nomo"
let mut count = 0
count = count + 1
```

- `let` 默认不可变。
- `let mut` 允许重新赋值或修改内部状态。
- 不允许读取未初始化变量。
- v0.1 不允许变量遮蔽。

### 2.3 基础类型

v0.1 内置：

```text
bool i32 i64 u32 u64 f64 char string void
```

`int` 暂不作为别名引入，避免平台位宽歧义。

### 2.4 显式转换

禁止隐式数值转换：

```rust
let age: i32 = 18
let ratio: f64 = age as f64
```

### 2.5 函数

```rust
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
```

- 函数参数默认不可变。
- 最后一个表达式作为返回值。
- 允许显式 `return expr`，主要用于提前返回。
- `void` 返回函数可以省略尾表达式。

### 2.6 结构体与方法

```rust
pub struct User {
    pub id: string
    email: string
}

impl User {
    pub fn get_email(self) -> string {
        self.email
    }
}
```

- 类型、字段、函数、方法默认私有。
- `pub` 表示包外可见。
- v0.1 只允许为当前包内定义的类型添加 `impl` 方法。

### 2.7 枚举与 `match`

```rust
pub enum Option<T> {
    Some(T)
    None
}
```

```rust
fn label(value: Option<i32>) -> string {
    match value {
        Option.Some(n) => "some"
        Option.None => "none"
    }
}
```

- `match` 必须穷尽所有变体。
- v0.1 暂不支持 `_` 通配分支。
- `Option` / `Result` 是否允许非限定变体由 [RFC 0007](./rfcs/0007-unqualified-variant-access.md) 讨论。

### 2.8 泛型

v0.1 支持泛型函数、结构体、枚举，并通过单态化生成具体 C 代码：

```rust
pub fn identity<T>(value: T) -> T {
    value
}
```

v0.1 不支持 trait/interface 约束、高阶类型或泛型特化。

---

## 3. 错误处理

### 3.1 双轨制

| 类型 | 机制 | 示例 |
| --- | --- | --- |
| 程序缺陷 | `panic` | 越界、不可达分支、内部错误 |
| 业务失败 | `Result<T, E>` | 文件不存在、解析失败、网络失败 |

v0.1 不实现异常展开。业务失败必须体现在函数签名中。

### 3.2 `Result<T, E>`

```rust
package std.result

pub enum Result<T, E> {
    Ok(T)
    Err(E)
}
```

### 3.3 `?` 传播

`expr?` 的规则：

- `Result.Ok(value)` 求值为 `value`。
- `Result.Err(error)` 使当前函数提前返回 `Result.Err(error)`。
- 当前函数返回类型必须是兼容的 `Result`。

v0.1 不自动合并错误类型。跨层错误转换由 [RFC 0001](./rfcs/0001-error-propagation-and-conversion.md) 讨论。

### 3.4 `Option` / `Result` 的编译器认知

`Option` 和 `Result` 既是标准库类型，又被 `?`、穷尽性检查和 C 后端布局使用。是否以 lang item 形式固定由 [RFC 0006](./rfcs/0006-option-result-lang-items.md) 讨论。

---

## 4. 内存模型

v0.1 采用三类值：

| 类别 | 示例 | 管理方式 |
| --- | --- | --- |
| 纯值 | `bool`、整数、浮点、小结构体 | C 值语义 |
| 标准库托管值 | `string`、`Array<T>` | 引用计数；数组写时复制 |
| 显式堆对象 | 后续版本的 `Box<T>` / `Rc<T>` | v0.1 暂不开放 |

### 4.1 `string`

`string` 是不可变值语义类型。赋值共享底层存储并增加引用计数；拼接生成新字符串。

### 4.2 `Array<T>`

`Array<T>` 是值语义托管容器：

```rust
import std.array.Array

let mut nums = Array.new<i32>()
nums.push(1)
```

- 读操作共享底层存储。
- 写操作在引用计数大于 1 时触发写时复制。
- `Array.get` 返回 `Option<T>`。
- `Array.set` 越界触发 `panic`。

ARC/COW 的运行时成本与退化策略由 [RFC 0003](./rfcs/0003-arc-cow-runtime-cost.md) 讨论。

### 4.3 可变借用

```rust
fn inc(mut counter: Counter) {
    counter.value = counter.value + 1
}

fn main() {
    let mut counter = Counter { value: 0 }
    inc(mut counter)
}
```

- 声明处和调用处都必须写 `mut`。
- `mut p: T` 表示当前调用栈内的可变借用，不是普通副本。
- 可变借用不得逃逸。
- 同一调用表达式内同一值不得被多次可变借用。

检查强度由 [RFC 0004](./rfcs/0004-mutable-borrow-uniqueness.md) 讨论。

---

## 5. 语法与名称解析

### 5.1 显著换行

v0.1 采用显著换行作为语句、字段、枚举变体和 `match` 分支的默认分隔符。不使用分号作为常规语句终止符。

换行规则和续行锚点由 [RFC 0005](./rfcs/0005-newline-sensitivity-and-dot-resolution.md) 固化。

### 5.2 点访问

`.` 统一作为后缀点访问：

```rust
std.io
Result.Ok
self.email
items.get(i)
```

Parser 产出未消解点链；名称解析根据左侧实体种类分派为模块路径、类型成员、枚举变体、字段或方法。

---

## 6. 标准库 v0.1

```text
std.io
std.fs
std.env
std.result
std.option
std.array
std.string
```

### 6.1 `std.io`

```rust
io.println("hello")
io.eprintln("error")
```

### 6.2 `std.fs`

```rust
pub struct FsError {
    pub message: string
}

fn read_to_string(path: string) -> Result<string, FsError>
fn write_string(path: string, content: string) -> Result<void, FsError>
```

### 6.3 `std.array`

```rust
Array.new<T>() -> Array<T>
Array.len(self) -> u64
Array.push(mut self, value: T)
Array.get(self, index: u64) -> Option<T>
Array.set(mut self, index: u64, value: T) -> void
```

### 6.4 `std.string`

```rust
string.len(self) -> u64
string.concat(self, other: string) -> string
```

---

## 7. 编译器架构

Stage 0 管线：

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

推荐内部表示：

| 层级 | 作用 |
| --- | --- |
| AST | 保留源码结构，用于诊断 |
| HIR | 名称解析、类型检查、可变性检查后的核心表示 |
| C IR | 面向 C99 输出的简化表示 |

C 后端原则：

- 生成可读 C。
- 包路径参与符号混淆，避免命名冲突。
- 标准库运行时以 C 源文件链接。
- `Result`、`Option`、`Array` 等布局必须有测试覆盖。

---

## 8. 诊断规范

诊断必须同时支持人类可读输出和 JSON 输出。

错误码范围：

| 范围 | 类别 |
| --- | --- |
| `N0100-N0199` | 词法错误 |
| `N0200-N0299` | 语法错误 |
| `N0300-N0399` | 名称解析 |
| `N0400-N0499` | 类型检查 |
| `N0500-N0599` | 借用与可变性 |
| `N0600-N0699` | 模块与包 |
| `N0700-N0799` | C 后端 |

JSON 诊断至少包含：

```json
{
  "status": "error",
  "error_code": "N0203",
  "severity": "error",
  "message": "type mismatch",
  "source": {
    "file": "src/main.nomo",
    "line": 4,
    "column": 18,
    "length": 3
  },
  "suggestions": []
}
```

---

## 9. 示例目录

v0.1 至少需要以下示例：

```text
examples/
├── hello/
├── args/
├── read_file/
├── result_chain/
├── struct_methods/
└── array_basic/
```

每个示例至少支持：

```bash
nomo check examples/hello
nomo run examples/hello
```

---

## 10. 验收矩阵

发布 v0.1 前必须满足：

- `cargo test` 通过。
- `cargo fmt --check` 通过。
- Lexer / Parser golden tests 稳定。
- 类型检查、名称解析、可变性测试覆盖成功与失败路径。
- C 后端生成代码可由至少一个主流 C 编译器编译。
- `hello`、`read_file`、`result_chain` 能 `nomo run`。
- JSON 诊断快照稳定。

---

## 11. RFC 索引入口

当前待决 RFC：

- [RFC 0001](./rfcs/0001-error-propagation-and-conversion.md)：错误传播与转换。
- [RFC 0002](./rfcs/0002-match-wildcard-and-nesting.md)：`match` 通配与嵌套解构。
- [RFC 0003](./rfcs/0003-arc-cow-runtime-cost.md)：ARC/COW 运行时成本。
- [RFC 0004](./rfcs/0004-mutable-borrow-uniqueness.md)：可变借用唯一性。
- [RFC 0005](./rfcs/0005-newline-sensitivity-and-dot-resolution.md)：换行敏感语法与 `.` 消解。
- [RFC 0006](./rfcs/0006-option-result-lang-items.md)：`Option`/`Result` lang item。
- [RFC 0007](./rfcs/0007-unqualified-variant-access.md)：非限定枚举变体。

