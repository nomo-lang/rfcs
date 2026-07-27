# Nomo 初始白皮书归档（2026-06-18）

> **状态：Superseded / 已被取代。**
>
> 本文是 2026-06-18 聚合工作区白皮书的原始历史快照，仅用于追溯早期设计，
> 不构成当前语言、标准库、Runtime 或发布承诺。当前非规范愿景总览见
> [`../WHITEPAPER-v0.1.md`](../WHITEPAPER-v0.1.md)；规范性语义见双语 SPEC 与已接受 RFC。

---

# 🚀 Nomo 编程语言语法与架构白皮书 (v0.1)

> **状态**：Stage 0 可交付规格草案
> **项目组织**：`github.com/nomo-lang`
> **工程管理器**：`nomo`
> **编译器**：`nomoc`
> **v0.1 目标**：用 Rust 实现一个最小但闭环的 Nomo 编译器，将 `.nomo` 源码编译为 C99，再调用系统 C 编译器生成可执行文件。

---

## 0. 摘要

Nomo 是一门面向系统工具、命令行程序、小型服务与 AI 辅助开发的新语言。v0.1 不试图一次性完成所有愿景，而是交付一个可以验证的最小闭环：

1.  可以创建项目：`nomo new hello`
2.  可以编译运行：`nomo run`
3.  可以输出诊断：`nomoc build src/main.nomo --json-errors`
4.  可以通过 C99 后端生成原生可执行文件
5.  可以支持基础类型、函数、结构体、枚举、模式匹配、显式错误处理、模块导入和最小标准库

v0.1 的核心原则是：**先把语言最小语义闭环做实，再逐步扩展到并发、GPU、Wasm、裸机和自举。**

---

## 1. v0.1 交付边界

### 1.1 必须交付

v0.1 必须包含以下端到端能力：

| 模块 | v0.1 交付物 | 验收方式 |
| --- | --- | --- |
| 工程工具 | `nomo new`、`nomo build`、`nomo run`、`nomo check` | 在示例项目中生成、检查、构建、运行成功 |
| 编译器前端 | Lexer、Parser、AST、语法错误诊断 | 语法快照测试与错误定位测试通过 |
| 类型检查 | 基础类型、函数、结构体、枚举、泛型、可变性、可见性 | 类型检查单元测试通过 |
| 错误处理 | `Result<T, E>`、`Option<T>`、后缀 `?` | 错误传播示例能编译并按预期运行 |
| C99 后端 | 将核心语言特性转译为 C99 | 生成的 C 代码可由 `clang` 或 `gcc` 编译 |
| 最小标准库 | `std.io`、`std.fs`、`std.env`、`std.result`、`std.option`、`std.array`、`std.string` | 示例程序可读参、打印、读文件、处理错误 |
| JSON 诊断 | 机器可读错误输出 | 输出结构稳定、包含位置和修复建议 |

### 1.2 明确不属于 v0.1

以下内容保留为路线图，不作为 v0.1 交付承诺：

| 能力 | 推迟原因 | 目标阶段 |
| --- | --- | --- |
| `go` 协程、`chan<T>`、隐式 Context | 需要运行时调度器、取消语义、数据竞争模型 | v0.3+ |
| GPU Kernel、PTX、SPIR-V | 需要独立后端、内存空间模型、设备 ABI | v0.5+ |
| WebAssembly 后端 | 需要 ABI、导入导出、线性内存模型 | v0.4+ |
| 裸机 `no_std` | 需要无堆子集和目标平台抽象 | v0.4+ |
| GUI 标准库 | 生态跨度大，不适合核心语言 MVP | v0.6+ |
| 高性能 Tensor、BLAS、BigDecimal | 可先作为后续库生态验证 | v0.3+ |
| 自举编译器 | 依赖语言稳定性和标准库成熟度 | v1.0 路线 |
| 原生 LLVM/Cranelift 后端 | C99 后端稳定后再引入 | v0.5+ |

### 1.3 v0.1 成功定义

v0.1 不是“功能多”，而是“链路完整”。满足以下条件才算闭环：

```bash
nomo new hello
cd hello
nomo run

nomoc build src/main.nomo --emit-c --out build/main.c
cc build/main.c -o build/hello
./build/hello

nomoc check src/main.nomo --json-errors
```

以上命令必须在 macOS 和 Linux 至少一个主流 C 编译器上通过。

---

## 2. 设计哲学

### 2.1 克制的系统语言

Nomo v0.1 采用“可预测优先”的设计：

- 无垃圾回收器，不引入停止世界式 GC。
- 所有可能失败的业务操作必须显式返回 `Result<T, E>`。
- 默认不可变，修改必须显式标记 `mut`。
- 禁止隐式数值转换。
- 默认私有，跨模块访问必须显式 `pub`。
- 先使用 C99 作为可审计后端，避免过早进入复杂机器码后端。

### 2.2 AI 友好但不牺牲语义

Nomo 面向 AI 编程辅助，但“AI 友好”不等于语义模糊。v0.1 通过以下方式降低生成和修复成本：

- 语法规则稳定，避免同一语义多种写法。
- 诊断输出包含错误代码、源码位置、期望类型、实际类型和建议修复。
- 标准库 API 保持小而一致。
- 示例和错误信息可作为 LLM 训练与自修复的稳定锚点。

### 2.3 对性能承诺保持可验证

v0.1 不承诺“全面接近 C/Rust”。可验证承诺如下：

- 整数、浮点、布尔、枚举标签等基础值按 C 值语义生成。
- 非捕获函数调用转译为 C 函数调用。
- 泛型通过单态化生成具体 C 函数。
- `Result` 在 C 后端采用显式结构体或标签联合体表示，不使用异常展开。
- 字符串和动态数组在标准库中实现引用计数与写时复制，性能以基准测试为准。

---

## 3. 语言核心

### 3.1 文件与模块

每个 `.nomo` 文件属于一个包。包路径由项目布局和 `nomo.toml` 决定。

```rust
package app.main

import std.io
import std.fs
```

v0.1 支持两种导入形式：

```rust
import std.io
import std.fs.read_to_string
```

不支持通配符导入。所有符号来源必须可追踪。

### 3.2 绑定与可变性

```rust
let name = "Nomo"        // 不可变绑定
let mut count = 0        // 可变绑定
count = count + 1
```

规则：

- `let` 默认不可变。
- `let mut` 允许重新赋值或修改内部状态。
- 不允许读取未初始化变量。
- 不允许变量遮蔽，除非后续版本引入显式 `shadow` 规则。

### 3.3 基础类型

v0.1 内置类型：

| 类型 | 说明 |
| --- | --- |
| `bool` | `true` / `false` |
| `i32`、`i64` | 有符号整数 |
| `u32`、`u64` | 无符号整数 |
| `f64` | 双精度浮点 |
| `char` | Unicode 标量值 |
| `string` | 标准库托管字符串，值语义，引用计数 + 写时复制 |
| `void` | 无返回值 |

暂不提供模糊的 `int` 别名。若未来引入 `int`，必须定义其位宽和平台语义。

### 3.4 显式类型转换

Nomo 禁止隐式数值转换：

```rust
let age: i32 = 18
let ratio: f64 = age as f64
```

非法示例：

```rust
let age: i32 = 18
let ratio: f64 = age  // 编译错误
```

### 3.5 函数

```rust
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
```

规则：

- 函数参数默认不可变。
- 函数体最后一个表达式作为返回值。
- 允许显式 `return expr`，但推荐仅用于提前返回。
- 返回类型为 `void` 时可以省略尾表达式。

### 3.6 可变借用参数

v0.1 用 `mut` 表达“调用者授权被修改”。声明处和调用处都必须出现 `mut`。

```rust
struct Point {
    x: i32
    y: i32
}

fn move_point(mut p: Point) {
    p.x = p.x + 10
}

fn main() {
    let mut pt = Point { x: 1, y: 2 }
    move_point(mut pt)
}
```

语义：

- `mut p: Point` 不是普通本地副本，而是当前调用栈内的可变借用。
- 可变借用不得逃逸出当前函数。
- 同一作用域内，一个值同时只能存在一个活动可变借用。
- v0.1 不暴露通用裸引用类型，避免在 MVP 阶段引入完整生命周期系统。

该模型足以支持原地修改示例，也避免把 Rust 的显式 lifetime 复杂度提前暴露给用户。

### 3.7 结构体

```rust
pub struct User {
    pub id: string
    email: string
}

impl User {
    pub fn new(id: string, email: string) -> User {
        User { id: id, email: email }
    }

    pub fn get_email(self) -> string {
        self.email
    }
}
```

规则：

- 结构体和字段默认私有。
- `pub` 字段可以跨模块访问。
- `impl` 只能为当前包内定义的类型添加方法。
- v0.1 不支持为外部类型扩展方法，避免孤儿规则和命名冲突。

### 3.8 枚举与模式匹配

```rust
pub enum Color {
    Red
    Green
    Blue
}

fn label(color: Color) -> string {
    match color {
        Color.Red => "red"
        Color.Green => "green"
        Color.Blue => "blue"
    }
}
```

带载荷枚举：

```rust
pub enum Option<T> {
    Some(T)
    None
}
```

`match` 必须穷尽所有分支。v0.1 暂不支持 `_` 通配分支，优先让诊断覆盖所有缺失分支。

### 3.9 泛型

v0.1 支持单态化泛型：

```rust
pub fn identity<T>(value: T) -> T {
    value
}
```

限制：

- 支持泛型函数、泛型结构体、泛型枚举。
- 不支持 trait/interface 约束。
- 不支持泛型特化。
- 不支持高阶类型。

### 3.10 可见性

默认私有：

```rust
fn helper() -> i32 { 1 }      // 包内可见
pub fn api() -> i32 { 2 }     // 包外可见
```

v0.1 只有两级可见性：

- 私有：当前包内可见。
- `pub`：依赖该包的外部包可见。

---

## 4. 错误处理

### 4.1 双轨制

Nomo 区分两类失败：

| 类型 | 机制 | 示例 |
| --- | --- | --- |
| 程序缺陷 | `panic` | 越界、不可达分支、内部编译器错误 |
| 业务失败 | `Result<T, E>` | 文件不存在、解析失败、网络失败 |

v0.1 不实现异常展开。业务失败必须体现在函数签名中。

### 4.2 `Result<T, E>`

```rust
package std.result

pub enum Result<T, E> {
    Ok(T)
    Err(E)
}
```

使用示例：

```rust
import std.fs
import std.result.Result

pub enum AppError {
    ReadFailed(string)
}

fn read_config(path: string) -> Result<string, AppError> {
    match fs.read_to_string(path) {
        Result.Ok(text) => Result.Ok(text)
        Result.Err(err) => Result.Err(AppError.ReadFailed(err.message))
    }
}
```

### 4.3 `?` 传播

表达式 `expr?` 的规则：

- 若 `expr` 为 `Result.Ok(value)`，表达式结果为 `value`。
- 若 `expr` 为 `Result.Err(error)`，当前函数立即返回 `Result.Err(error)`。
- 当前函数返回类型必须也是兼容的 `Result`。

v0.1 不提供匿名错误联合体，不自动合并错误类型。跨层错误转换必须显式完成：

```rust
fn load_user(path: string) -> Result<string, AppError> {
    match fs.read_to_string(path) {
        Result.Ok(text) => Result.Ok(text)
        Result.Err(err) => Result.Err(AppError.ReadFailed(err.message))
    }
}
```

自动错误联合体可作为后续 RFC，不进入 v0.1。

### 4.4 C 后端表示

v0.1 的 `Result` 在 C99 中使用明确的数据结构表示，例如：

```c
typedef struct {
    bool is_ok;
    union {
        T ok;
        E err;
    } payload;
} Result_T_E;
```

这不是隐式异常机制，也不承诺特殊寄存器优化，而是可审计、可移植、便于调试的 MVP 表示。后续版本可以在稳定 ABI 后优化布局。

---

## 5. 内存模型

### 5.1 v0.1 内存策略

v0.1 采用三类值：

| 类别 | 示例 | 管理方式 |
| --- | --- | --- |
| 纯值 | `bool`、整数、浮点、枚举标签、小结构体 | 栈值或 C 值传递 |
| 标准库托管值 | `string`、`Array<T>` | 引用计数 + 写时复制 |
| 显式堆对象 | 后续版本的 `Box<T>` / `Rc<T>` | v0.1 暂不开放通用 API |

v0.1 不承诺“消灭一切循环引用”。由于通用引用类型暂不开放，核心语言层面不会产生用户可构造的引用环；但未来一旦加入闭包、通道、共享对象或图结构，必须引入弱引用或循环规避策略。

### 5.2 字符串

`string` 是不可变值语义类型：

```rust
let a = "hello"
let b = a
```

实现策略：

- 赋值增加引用计数。
- 字符串内容不可原地修改。
- 拼接生成新字符串。
- C 后端通过标准库运行时函数管理引用计数。

### 5.3 动态数组

v0.1 提供 `Array<T>`，不使用 `[]T` 作为核心语法糖。

```rust
import std.array.Array

let mut nums = Array.new<i32>()
nums.push(3)
nums.push(1)
nums.push(2)
```

规则：

- `Array<T>` 是值语义托管容器。
- 读操作共享底层存储。
- 写操作在引用计数大于 1 时触发写时复制。
- 通过 `mut` 授权修改。

切片语法、借用切片和 `[]T` 可作为 v0.2 RFC。

### 5.4 `defer`

v0.1 支持 `defer`，用于作用域退出清理：

```rust
fn main() -> Result<void, FsError> {
    let file = fs.open("config.toml")?
    defer file.close()
    Result.Ok(void)
}
```

规则：

- `defer` 在当前作用域退出时逆序执行。
- 正常返回和 `?` 提前返回都会执行 `defer`。
- v0.1 不支持 panic 展开期间的复杂恢复语义。

---

## 6. 控制流

### 6.1 `if`

```rust
let label = if score >= 60 {
    "pass"
} else {
    "fail"
}
```

`if` 作为表达式时，所有分支类型必须一致。

### 6.2 `match`

```rust
fn describe(value: Option<i32>) -> string {
    match value {
        Option.Some(n) => "some"
        Option.None => "none"
    }
}
```

### 6.3 `for`

v0.1 提供三种 `for`：

```rust
for {
    break
}

for i < 10 {
    i = i + 1
}

for item in items {
    io.println(item)
}
```

v0.1 支持 `break` 和 `continue`，因此它们必须列入关键字集合。

---

## 7. 关键字与保留字

### 7.1 v0.1 关键字

```text
package import pub fn struct enum impl let mut const
if else match for in return defer break continue
panic as
```

### 7.2 保留但暂不启用

以下词汇为后续版本保留，v0.1 中不可作为标识符，但不提供完整语义：

```text
interface unsafe extern export go chan
```

### 7.3 字面量与特殊名称

```text
true false null self void
```

说明：

- v0.1 使用 `Option<T>` 表达可选值，不提供通用 nullable 类型。
- `null` 仅为后续 FFI 或裸指针 RFC 保留，v0.1 用户代码不应使用。

---

## 8. 标准库 v0.1

v0.1 标准库保持最小：

```text
std.io
std.fs
std.env
std.result
std.option
std.array
std.string
```

### 8.1 `std.io`

```rust
io.println("hello")
io.eprintln("error")
```

### 8.2 `std.fs`

```rust
pub struct FsError {
    pub message: string
}

fn read_to_string(path: string) -> Result<string, FsError>
fn write_string(path: string, content: string) -> Result<void, FsError>
fn open(path: string) -> Result<File, FsError>
File.close(self) -> void
```

### 8.3 `std.env`

```rust
fn args() -> Array<string>
fn get(name: string) -> Option<string>
```

### 8.4 `std.array`

```rust
Array.new<T>() -> Array<T>
Array.len(self) -> u64
Array.push(mut self, value: T)
Array.get(self, index: u64) -> Option<T>
Array.set(mut self, index: u64, value: T) -> void
```

`Array.get` 用 `Option<T>` 表达可能越界；`Array.set` 越界视为程序缺陷并触发 `panic`。

### 8.5 `std.string`

```rust
string.len(self) -> u64
string.concat(self, other: string) -> string
```

---

## 9. 工程管理

### 9.1 单项目布局

```text
my_app/
├── nomo.toml
└── src/
    └── main.nomo
```

`nomo.toml`：

```toml
[package]
name = "my_app"
version = "0.1.0"

[dependencies]
std = "0.1.0"
```

### 9.2 命令

```bash
nomo new my_app
nomo check
nomo build
nomo run
nomo clean
```

### 9.3 编译产物

```text
build/
├── c/
│   └── main.c
├── obj/
└── bin/
    └── my_app
```

### 9.4 工作空间

工作空间保留为 v0.2 目标。v0.1 的 `nomo.toml` 可预留字段，但工具无需实现 monorepo 拓扑构建。

---

## 10. 诊断规范

### 10.1 人类可读诊断

```text
error[N0203]: type mismatch
  --> src/main.nomo:4:18
   |
 4 | let ratio: f64 = age
   |                  ^^^ expected f64, found i32
help: use an explicit cast: age as f64
```

### 10.2 JSON 诊断

```json
{
  "status": "error",
  "error_code": "N0203",
  "severity": "error",
  "message": "type mismatch: expected f64, found i32",
  "source": {
    "file": "src/main.nomo",
    "line": 4,
    "column": 18,
    "length": 3,
    "text": "let ratio: f64 = age"
  },
  "expected": "f64",
  "found": "i32",
  "suggestions": [
    {
      "action": "replace_text",
      "range": {
        "line": 4,
        "column": 18,
        "length": 3
      },
      "text": "age as f64",
      "description": "cast i32 to f64 explicitly"
    }
  ]
}
```

### 10.3 错误码范围

| 范围 | 类别 |
| --- | --- |
| `N0100-N0199` | 词法错误 |
| `N0200-N0299` | 语法错误 |
| `N0300-N0399` | 名称解析 |
| `N0400-N0499` | 类型检查 |
| `N0500-N0599` | 借用与可变性 |
| `N0600-N0699` | 模块与包 |
| `N0700-N0799` | C 后端 |

---

## 11. 示例

### 11.1 Hello World

```rust
package app.main

import std.io

fn main() -> void {
    io.println("Hello, Nomo")
}
```

### 11.2 文件读取与错误处理

```rust
package app.main

import std.fs
import std.io
import std.result.Result

pub enum AppError {
    ReadFailed(string)
}

fn read_config(path: string) -> Result<string, AppError> {
    match fs.read_to_string(path) {
        Result.Ok(text) => Result.Ok(text)
        Result.Err(err) => Result.Err(AppError.ReadFailed(err.message))
    }
}

fn main() -> Result<void, AppError> {
    let text = read_config("nomo.toml")?
    io.println(text)
    Result.Ok(void)
}
```

### 11.3 原地修改

```rust
package app.main

import std.io

struct Counter {
    value: i32
}

fn inc(mut counter: Counter) {
    counter.value = counter.value + 1
}

fn main() -> void {
    let mut counter = Counter { value: 0 }
    inc(mut counter)
    io.println("done")
}
```

### 11.4 数组排序示例

v0.1 不引入切片语法，因此排序基于 `Array<T>` 标准库 API：

```rust
package app.main

import std.array.Array
import std.io
import std.option.Option

fn swap(mut items: Array<i32>, i: u64, j: u64) {
    let a = items.get(i)
    let b = items.get(j)

    match a {
        Option.Some(av) => {
            match b {
                Option.Some(bv) => {
                    items.set(i, bv)
                    items.set(j, av)
                }
                Option.None => panic("index out of bounds")
            }
        }
        Option.None => panic("index out of bounds")
    }
}
```

完整快速排序可作为标准库测试用例，不要求写入语言白皮书主体。

---

## 12. 编译器架构

### 12.1 Stage 0 管线

```text
.nomo source
   │
   ▼
Lexer
   │
   ▼
Parser
   │
   ▼
AST
   │
   ▼
Name Resolution
   │
   ▼
Type Check + Mutability Check
   │
   ▼
HIR
   │
   ▼
C99 Codegen
   │
   ▼
cc / clang / gcc
   │
   ▼
Executable
```

### 12.2 内部表示

v0.1 推荐实现三个层级：

| 层级 | 作用 |
| --- | --- |
| AST | 保留源码结构，用于诊断 |
| HIR | 名称解析和类型检查后的核心表示 |
| C IR | 面向 C99 输出的简化表示 |

### 12.3 C 后端原则

- 生成可读 C，而不是难以调试的宏黑盒。
- 所有生成符号使用包路径混淆，避免命名冲突。
- 每个 Nomo 包生成独立 `.c` / `.h`。
- 标准库运行时以 C 源文件形式链接。

---

## 13. v0.1 验收测试矩阵

### 13.1 编译器测试

| 测试 | 要求 |
| --- | --- |
| Lexer golden tests | token 序列稳定 |
| Parser golden tests | AST 快照稳定 |
| Type checker tests | 类型错误和成功样例覆盖 |
| Mutability tests | 非法修改、重复可变借用被拒绝 |
| Codegen tests | 生成 C 与预期结构一致 |
| Runtime smoke tests | 示例程序编译运行成功 |

### 13.2 语言样例

`examples/` 至少包含：

```text
examples/
├── hello/
├── args/
├── read_file/
├── result_chain/
├── struct_methods/
└── array_basic/
```

每个示例必须能被以下命令验证：

```bash
nomo check examples/hello
nomo run examples/hello
```

### 13.3 发布门槛

v0.1 发布前必须满足：

- `cargo test` 通过。
- `cargo fmt --check` 通过。
- 所有 `examples/*` 能 `nomo check`。
- 至少 `hello`、`read_file`、`result_chain` 能 `nomo run`。
- JSON 诊断样例通过快照测试。
- README 能从零创建并运行第一个项目。

---

## 14. 路线图

### 14.1 v0.2：语言可用性

- 工作空间与路径依赖。
- 切片语法与范围表达式。
- 更完整的 `match` 模式。
- `interface` / trait 约束。
- 包发布与锁文件。

### 14.2 v0.3：并发与运行时

- 明确 runtime 边界。
- `go` fiber 调度器。
- `chan<T>`。
- 显式 Context 传递，再评估是否支持隐式传播。
- 数据竞争规则和线程安全容器。

### 14.3 v0.4：Wasm 与 no_std

- `wasm32-wasi`。
- 最小 `no_std` 子集。
- FFI ABI。
- 可选堆分配策略。

### 14.4 v0.5：优化后端

- LLVM 或 Cranelift 后端。
- Result 布局优化。
- 内联与逃逸分析。
- 更精细的 ARC 消除。

### 14.5 v1.0：稳定语言

- 自举编译器。
- 稳定包管理。
- 稳定 ABI。
- 标准库兼容性承诺。

---

## 15. 需要 RFC 决策的问题

以下问题不应在白皮书中用宣传语掩盖，必须通过 RFC 决策：

1.  `mut p: T` 是否长期作为可变借用语法，还是改为更明确的 `borrow mut p: T`。
2.  是否允许变量遮蔽。
3.  `string` 是否按 Unicode 标量长度、字节长度，还是同时提供两套 API。
4.  `panic` 在 v0.1 中是终止进程、终止当前任务，还是调用用户 hook。
5.  `Result` 错误转换是否引入 `From` 风格 trait。
6.  闭包是否使用 fat pointer 表示，以及如何与 ARC 交互。
7.  未来并发模型是否默认单线程 fiber，还是直接支持多线程 work stealing。

---

## 16. 一句话定位

Nomo v0.1 的定位不是“立刻替代 Rust、Go、Swift 和 CUDA”，而是：

> **一门以可预测语义、显式错误、默认安全和 AI 友好诊断为核心的实验性系统语言；v0.1 先交付 Rust 编写的 C99 转译器和最小标准库，让真实程序可以从源码走到可执行文件。**
