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
6. `nomo fmt` 对项目和单文件的 v0.1 源码进行规范格式化。
7. `nomo test` 发现并运行项目或 workspace 中的 `#[test]` 函数。
8. `nomo doc` 从 doc comment 生成项目或 workspace 文档。

v0.1 不追求功能面最大化，而追求规格、实现、测试和 RFC 决策闭环。

---

## 1. v0.1 交付边界

### 1.1 必须交付

| 模块 | 交付内容 | 验收方式 |
| --- | --- | --- |
| 工程工具 | `nomo new`、`nomo check`、`nomo build`、`nomo run`、`nomo fmt`、`nomo test`、`nomo doc` | 示例项目可创建、检查、构建、运行、格式化、测试和生成文档 |
| 编译器前端 | Lexer、Parser、AST、语法诊断 | golden tests 稳定 |
| 名称解析 | 包、导入、类型、函数、字段、枚举变体解析 | 成功/失败样例覆盖 |
| 类型检查 | 基础类型、函数、结构体、枚举、泛型、`Result`、`Option` | 类型检查测试通过 |
| 可变性检查 | `let mut`、调用处 `mut`、可变借用唯一性 | Mutability tests 覆盖 |
| C99 后端 | HIR/C IR 到可读 C99 | 生成 C 可由 `clang` 或 `gcc` 编译 |
| 最小标准库 | `std.io`、`std.fs`、`std.env`、`std.result`、`std.option`、`std.array`、`std.string`、`std.char`、`std.os`、`std.time`、`std.process`、`std.testing`、`std.debug`、`std.log`、`std.path`、`std.math`、`std.num`、`std.hash`、`std.crypto`、`std.json`、`std.net`、`std.http`、`std.regex`、`std.collections` | 示例程序可用 |
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

### 2.5 数值操作符

当前 preview build 支持二元数值运算，并按标准优先级解析：

```rust
let value: i64 = a - b * c / d % e
let ratio: f64 = total / count
let grouped: i64 = -(a + b) * c
let ready: bool = !failed && connected || cached
let mut masked: i64 = value & mask &^ clear << 1 >> shift | extra ^ flags
masked &^= clear
masked++
masked--
```

- `+`、`-`、`*`、`/` 需要两个匹配的数值操作数，并返回同类型结果。
- 括号分组表达式会覆盖默认优先级。
- 一元 `-` 需要 `i32`、`i64` 或 `f64` 操作数，并返回同类型结果。
- `%` 需要两个匹配的整数操作数，并返回同整数类型结果。
- `&&` 与 `||` 需要两个 `bool` 操作数，返回 `bool`，并按从左到右短路求值。
- `!` 需要一个 `bool` 操作数，并返回 `bool`。
- `&`、`|`、`^`、`&^` 需要两个匹配的整数操作数，并返回同整数类型结果。
- `<<` 与 `>>` 需要整数左操作数和整数 shift 数量，并返回左操作数类型。
- 相等与大小比较返回 `bool`。
- 语句级复合赋值支持 `+=`、`-=`、`*=`、`/=`、`%=`、`<<=`、`>>=`、`&=`、
  `^=`、`|=` 与 `&^=`，可用于可变变量和可变结构体字段。每种形式按
  `target = target op value` 进行类型检查。
- 语句级 postfix 更新支持 `target++` 与 `target--`，可用于可变变量和可变结构体字段。
  它们按 `target += 1` 与 `target -= 1` 类型检查，不是表达式，也不产生值。
- 除零、有符号 `i32`/`i64` 算术溢出和非法 shift 数量会在运行时 panic。
  有符号右移定义为算术右移：负数补 `1` bit，非负数补 `0` bit。

### 2.6 函数

```rust
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
```

- 函数参数默认不可变。
- 最后一个表达式作为返回值。
- 允许显式 `return expr`，主要用于提前返回。
- `void` 返回函数可以省略尾表达式。

### 2.7 结构体与方法

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

v0.1 支持最小 `interface` 声明和 `impl Interface for Type` 静态方法实现：

```rust
pub interface Display {
    fn to_string(self) -> string
}

impl Display for User {
    fn to_string(self) -> string {
        return self.name
    }
}
```

编译器会静态检查 `impl Interface for Type`：interface 必须已声明或作为
public API 导入，impl 必须提供每个必需方法，并且方法 type parameter、
参数数量、参数 mutability、参数类型与返回类型在把 `Self` 替换为具体 impl
目标类型后必须一致。

当前 interface MVP 不支持 trait object、associated type、blanket impl、动态分派或
`fn print<T: Display>(value: T)` 形式的泛型约束；这类完整约束系统仍不属于 v0.1。
高阶类型和泛型特化也不属于 v0.1。

### 2.9 C FFI 与 `unsafe`

v0.1 支持最小 C FFI 入口：

```rust
extern "C" {
    fn puts(message: string) -> i32
    fn abs(value: i32) -> i32
}

fn main() -> void {
    unsafe {
        let value: i32 = abs(-7)
    }
}
```

`extern "C"` 声明只描述 C 函数签名；调用 extern 函数必须写在 `unsafe { ... }`
block 中。当前 MVP 支持将 Nomo `string` 传给 C `puts`，codegen 传递底层
NUL-terminated byte buffer。其他 extern 调用支持 primitive integer、float、
bool、char 参数和返回值，以及 `void` 返回。

项目 manifest 可以声明 native linker metadata：

```toml
[ffi]
libraries = ["sqlite3"]
library_paths = ["native/lib"]
frameworks = ["Security"]
link_args = ["-Wl,-rpath,@loader_path"]
```

`libraries` 会转换为 `-l<name>`，`library_paths` 会转换为 `-L<path>`，
`frameworks` 会转换为 macOS `-framework <name>` 参数，`link_args` 会作为
raw 参数传给系统 C compiler。相对 `library_paths` 按声明它的 package root
解析。项目 build 和 test 会聚合 root package 与源码依赖中的 `[ffi]`
metadata。Standalone script mode 不读取 manifest，因此不使用 link metadata。

任意裸指针、C struct 自动布局、header 绑定生成和多语句 unsafe block 留待后续切片。

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
- `Option.Some(value)` 求值为 `value`。
- `Option.None` 使当前函数提前返回 `Option.None`。
- 当前函数返回类型必须是兼容的 carrier：对 `Result` 值使用 `expr?` 时，当前函数必须返回兼容的 `Result`；对 `Option` 值使用 `expr?` 时，当前函数必须返回兼容的 `Option`。

v0.1 不引入 `try` 关键字或语句语法；错误与缺值传播统一使用后缀 `?`。

v0.1 不自动合并错误类型。跨层错误转换使用显式 `std.result.map_err(named_converter)?`，见已接受的 [RFC 0001](./rfcs/0001-error-propagation-and-conversion.md)。

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
- `Array.pop` 和 `Array.remove` 返回 `Option<T>`；空数组或越界时返回 `None`。
- `Array.set` 和 `Array.insert` 越界触发 `panic`。
- `Array.iter` 返回可被 `for ... in` 消费的快照值；完整 iterator 类型推迟到 trait/interface 之后。

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

### 5.3 包身份与依赖别名

Nomo v0.1 采用 namespace-first package model。包的稳定身份是
`owner/package`，例如 `nomo-lang/json`；Git URL、registry、branch、rev、local
path 都只是依赖 source，不作为源码 import 的语言身份。

`nomo.toml` 基础结构：

```toml
[package]
namespace = "fynn"
name = "hello"
version = "0.1.0"
edition = "2026"

[dependencies]
json = { package = "nomo-lang/json", version = "0.1.0" }
local_utils = { package = "fynn/utils", path = "../utils" }
http = { package = "nomo-lang/http", git = "https://github.com/nomo-lang/http.git", rev = "2a4b8c1" }
cli = { package = "nomo-lang/cli", git = "https://github.com/nomo-lang/cli.git", branch = "stable" }
fmt = { package = "nomo-lang/fmt", git = "https://github.com/nomo-lang/fmt.git", tag = "v0.1.0" }
```

`nomo.toml` 使用标准 TOML 解析。注释、字符串转义、inline table，以及
`[dependencies.local_utils]` 这类 dependency subtable 都是合法 TOML 输入，不应再用逐行手写 parser 重新实现。

workspace root 可以共享 package 默认值和 dependency 声明：

```toml
[workspace]
members = ["apps/*", "packages/*"]
default-members = ["apps/cli"]
resolver = "1"

[workspace.package]
namespace = "fynn"
edition = "2026"

[workspace.dependencies]
json = { package = "nomo-lang/json", version = "0.1.0" }
core = { package = "fynn/core", path = "packages/core" }
```

workspace member 通过 TOML dotted key 显式继承字段：

```toml
[package]
name = "cli"
version = "0.1.0"
namespace.workspace = true
edition.workspace = true

[dependencies]
json.workspace = true
core.workspace = true
```

源码 import 使用依赖 alias：

```rust
package app.main

import json.parser
import local_utils.path
import http.client
```

v0.1 必须校验：

- `[package]` 的 namespace、name、version、edition。
- dependency alias 使用 Nomo 标识符规则。
- dependency `package` 使用 `owner/package` canonical id。
- `std`、`nomo`、`core` namespace 为语言和标准工具链保留，不可作为 package owner。
- `std` 是内置保留 import root。用户 manifest 不需要声明 `std` 依赖，普通依赖不可使用
  `std` 作为 alias，`std` 也不作为普通 package entry 写入 `nomo.lock`。
- dependency source 在 `path`、`git`、`version` 三类中必须且只能声明一种。
- 仍写有 `std = "0.1.0"` 或
  `std = { package = "nomo-lang/std", version = "0.1.0" }` 的旧 manifest
  可以作为兼容输入接受，但该声明会被忽略，不进入普通依赖图。
- registry/version source 在 v0.1 作为 lockfile 叶子节点记录；可选 `registry`
  endpoint 可作为 source 元数据写入。`nomo add` 与 `nomo remove` 会编辑
  `nomo.toml` 中的 registry dependency entry；没有显式 endpoint 的 registry dependency
  仍作为 leaf entry。`file://` 或 `http://` registry endpoint 使用
  `/api/v1/packages/<owner>/<package>/<version>/download` 路径解析；下载到的
  `.nomo-package` archive 会解包到 `.nomo/cache/registry/`，并可向项目构建提供
  imported public API。`nomo publish --dry-run` 会校验本地 package 并准备确定性的
  package archive；`nomo publish --registry <url>` 会用
  `PUT /api/v1/packages/<owner>/<package>/<version>` 把 archive 上传到 `http://`
  registry endpoint。`nomo search <query> --registry <url>` 会向 `http://`
  registry endpoint 查询 `GET /api/v1/packages?query=<encoded>`，并期望得到由
  object 组成的 JSON array；object 包含 `package`，以及可选的 `version` 和
  `description`。`nomo yank <owner/package> <version> --registry <url>` 会用
  `POST /api/v1/packages/<owner>/<package>/<version>/yank` 将已发布版本标记为
  yanked；yanked version 仍可从既有 lockfile 构建。`nomo login --registry
  <url> --token <token>` 会把 bearer token 写入
  `$NOMO_HOME/credentials.toml`；未设置 `NOMO_HOME` 时写入
  `$HOME/.nomo/credentials.toml`。后续访问同一 endpoint 的 HTTP registry
  download、publish 与 yank 请求会附带 `Authorization: Bearer <token>`。
  `nomo owner add <owner/package> <user> --registry <url>` 会用
  `PUT /api/v1/packages/<owner>/<package>/owners/<user>` 添加 package owner，
  并在已有登录 token 时复用同一个 Bearer token。`nomo owner remove
  <owner/package> <user> --registry <url>` 会用
  `DELETE /api/v1/packages/<owner>/<package>/owners/<user>` 移除 package owner。
- `nomo.lock` 使用标准 TOML。package entry 以 `[[package]]` table 存储，包含
  `id`、`alias`、`source`、可选 source metadata、`checksum` 和 dependency edge
  字符串。workspace lockfile 额外使用 `[[root]]` table，把每个 member package id
  映射到它的直接 dependency edge。非法 TOML、未知 package 字段和字段类型不匹配都会被拒绝。
- workspace member manifest 可以用 `<field>.workspace = true` 从
  `[workspace.package]` 继承 `namespace`、`name`、`version`、`edition`。
- workspace member dependency 可以用 `<alias>.workspace = true` 继承
  `[workspace.dependencies]` 中同名 dependency；workspace dependency 的 `path`
  source 按 workspace root 解释，并在 member package 解析时重新基准化。
- 只有 `[workspace]` 而没有 `[package]` 的 manifest 是 workspace root，不是 package
  manifest。当前 member 级项目命令仍作用于选中的 member package；对 member 执行
  `nomo deps resolve` 时 lockfile 写在 workspace root。`nomo check --workspace`、
  `nomo build --workspace`、`nomo test --workspace`、`nomo doc --workspace`、
  `nomo deps resolve --workspace` 与 `nomo deps tree --workspace` 会发现 workspace
  root，展开 `members` 并排除 `exclude`，按稳定路径顺序访问每个 member package。
- `path` source 需要读取目标包的 `nomo.toml`，并递归纳入 `nomo.lock` 与 `nomo deps tree`。
- `git` source 使用项目本地 `.nomo/deps/git/` 缓存，cache key 基于 canonical package
  id 与 source URL。cache miss 时 clone repository；cache hit 时先执行
  `git fetch --tags --prune origin` 再 checkout。如声明 `branch`、`tag` 或 `rev`
  则 checkout 到对应位置；branch source 还会执行 `git pull --ff-only`。读取目标包
  manifest 校验 canonical package id；lockfile 写入实际 `HEAD` rev。manifest 中同一
  git 依赖只能声明一个 checkout selector：`branch`、`tag` 或 `rev`。
- `nomo deps clean-cache [path]` 删除项目或 workspace 的 `.nomo/deps/git` 缓存，
  不删除 `nomo.lock`、source files 或 build artifacts；该命令可重复执行。
- `nomo deps update [path] [alias-or-package]` 按当前 manifest source 刷新 lockfile。
  不带 target 时更新全部依赖；带 alias 或 canonical package id 时先校验该 target 是
  direct dependency，再重写 lockfile。当前实现会重写完整 lockfile。`--precise <version-or-rev>`
  要求显式 target，并且只改变本次生成 lockfile 时使用的 source，不写回 `nomo.toml`：
  registry dependency 将该值作为 `version`，git dependency 将该值作为 `rev` 并清除
  branch/tag selector，path dependency 会被拒绝。
- `nomo add <alias>@<owner>/<package>:<version> [path] [--registry <url>]`
  向选中的 package manifest 添加 registry dependency entry。它不拉取 package archive，
  也不重写 `nomo.lock`；需要刷新 lockfile 时由调用者再执行 `nomo deps resolve`。
- `nomo remove <alias> [path]` 从选中的 package manifest 删除 dependency entry。
  它不重写 `nomo.lock`。
- `nomo search <query> --registry <url>` 使用
  `GET /api/v1/packages?query=<encoded>` 查询 `http://` registry package index，
  并按 registry 返回字段逐行输出 `owner/package`、`owner/package version` 或
  `owner/package version - description`。
- `nomo login --registry <url> --token <token>` 为 `http://` registry endpoint
  写入本地 bearer token。后续访问该 endpoint 的 HTTP registry download、
  publish 与 yank 请求会使用此 token。
- `nomo owner add <owner/package> <user> --registry <url>` 使用
  `PUT /api/v1/packages/<owner>/<package>/owners/<user>` 为 package 添加 owner。
  如果此前通过 `nomo login` 写入 token，请求会附带
  `Authorization: Bearer <token>`。
- `nomo owner remove <owner/package> <user> --registry <url>` 使用
  `DELETE /api/v1/packages/<owner>/<package>/owners/<user>` 从 package 移除
  owner。如果此前通过 `nomo login` 写入 token，请求会附带
  `Authorization: Bearer <token>`。
- `nomo yank <owner/package> <version> --registry <url>` 使用
  `POST /api/v1/packages/<owner>/<package>/<version>/yank` 将已发布 registry
  version 标记为 yanked。Yank 不删除 package archive，lockfile 仍可继续构建该
  exact version。
- `nomo publish [path] (--dry-run | --registry <url>) [--output <dir>] [--json-errors]`
  使用项目检查校验选中的 package，将 `nomo.toml` 与 `src/` 打成确定性的
  `.nomo-package` archive，并输出 archive path、`sha256:` checksum 与 byte size。
  `--dry-run` 在准备 archive 后停止；`--registry <url>` 会用
  `PUT /api/v1/packages/<owner>/<package>/<version>` 上传到 `http://` registry
  endpoint。v0.1 会拒绝既没有 `--dry-run` 也没有 `--registry` 的 publish 命令。
- `nomo deps vendor [path] [--workspace] [--dir vendor] [--sync]` 确保 lockfile
  存在后，把 locked `path`、`git` 与已缓存 registry dependency source 复制到 vendor
  目录，并写入 `nomo-vendor.toml`。`--sync` 会先删除 vendor 目录再复制。没有 cached
  archive 的 registry leaf 会记录为 skipped。locked/offline 的项目模块加载在原 locked
  path source、git cache checkout 或 registry cache entry 缺失时，会回退到默认 `vendor/` 目录。
- 已解析的 `path`、`git` 与已 fetch 的 registry package 需要在 lockfile 中写入
  `sha256:` checksum；checksum 覆盖目标包 `nomo.toml` 与 `src/` 内容。没有 fetch 的
  registry leaf 不写 checksum。
- `nomo deps tree` 在存在 `nomo.lock` 时读取锁定依赖图，并对仍可访问的 locked
  `path` source 与匹配的 git cache checkout 校验 checksum；没有 lockfile 时再解析当前
  manifest source。缺失的 `path` source 与 git cache entry 可作为离线锁定条目继续展示。
- `nomo build`、`nomo deps resolve` 与 `nomo deps tree` 接受 `--locked`；该模式要求
  现有 lockfile，若缺失或 direct dependency 与 manifest 不一致则报错，且不重写
  `nomo.lock`。
- `--offline` 禁止 git fetch/clone，只使用现有 lockfile 或 git cache checkout；没有
  lockfile 时，未缓存的 git dependency 会报错而不是访问网络。`--frozen` 等价于
  `--locked --offline`。
- 同一 canonical package id 若解析到不同 source 或 version，v0.1 直接报错。
- 项目级 `nomo check/build/run` 使用 `nomo.toml` 中声明的 dependency alias 校验源码 import；
  本地项目模块使用 Flat+Dir 查找：`import app.util` 优先解析 `src/util.nomo`，然后回退到
  `src/util/main.nomo`；`import app.main` 解析 `src/main.nomo`。已 import 的 `path`
  与 `git` dependency module 在依赖包 `src/` 下使用同样的查找规则。已 import 的本地模块与依赖模块会把 public API
  纳入当前 v0.1 编译单元，包括 public function、const、struct、enum 与 public method；private
  item 不导出。`nomoc` 作为单文件编译器不读取 manifest，仍只接受内建 `std.*` import。
- `nomo-lsp` 诊断路径应与项目级 `nomo check` 保持一致：对项目文件读取最近的
  `nomo.toml` dependency alias；对无 manifest 的单文件保留 `nomoc` 行为。
- `nomo run <source.nomo>` 支持直接运行项目 manifest 外的 standalone source file。
  文件仍使用普通 `package` 声明和普通 import。若文件没有显式 `fn main`，则所有声明之后的
  top-level script statements 会被编译为合成的 `main() -> void`。声明必须出现在
  top-level script statements 之前；显式 `main` 不能与 top-level script statements 混用。
  项目级 `check/build/run` 与 `nomoc check/build` 不启用该 script entry mode。
- `nomo fmt [path] [--check] [--json-errors]` 是 v0.1 源码的 AST-based formatter。
  无 path 或 path 为 project 目录时，先发现项目 manifest，再按稳定路径顺序格式化
  `src/**/*.nomo`。path 为 workspace root 时，格式化各 member 的 `src/**/*.nomo`。
  path 为无 `nomo.toml` 的 loose source directory 时，递归格式化其中的 `.nomo` 文件。
  path 为直接 `.nomo` 文件时，只格式化该文件，不要求 manifest。
  `--check` 只输出 `would format <path>`，不写文件；只要存在差异就以失败退出。
  formatter 输出规范空白、缩进以及 package/import/item 间距，同时保留 Rust 风格
  行注释（`//`、`///`、`//!`）和可嵌套块注释（`/* */`、`/** */`、`/*! */`），
  并将它们作为前置或行尾 trivia 绑定到附近的声明和语句。
  `nomoc` 在 v0.1 不新增 formatter 命令。
- `nomo test [path] [--workspace] [--package <package>] [--filter <text>] [--json] [--locked] [--offline] [--frozen]`
  发现项目 `src/**/*.nomo` 中的顶层 `#[test]` 函数并逐个运行。测试函数必须无泛型、无参数、
  返回 `void`，且不能命名为 `main`。每个测试都复用项目模块 resolver 与 dependency resolver，
  编译临时 runner `main() -> void` 调用该测试函数；已有项目 `main` 不作为测试入口执行。
  `--filter` 按完整测试名子串过滤，`--workspace` 运行 workspace members，`--package` 选择
  package id 或 member name，`--json` 输出稳定测试报告。
- `nomo doc [path] [--workspace] [--package <package>] [--std] [--open] [--json] [--output <dir>]`
  从 Rust 风格 doc comment（`//!`、`///`、`/*! */`、`/** */`）提取 module 与 item 文档，
  并结合 parser AST 输出 package/module、function、extern function、struct、enum、
  interface、method、const 的签名、可见性和 source 位置。struct field、
  enum variant 与 interface method 会作为子文档项输出，并进入 search index。
  默认写入 `build/doc/index.html`、
  package/module HTML 页面与 `search-index.json`；`--json` 只输出机器可读文档模型，
  不写文件。`--workspace` 生成 workspace members 文档，`--package`
  选择 package id 或 member name，`--std` 生成当前内置标准库 module 索引，
  `--open` 打开生成的 `index.html`。`--open` 不能与 `--json` 同用。

HTTPS/TLS registry archive fetching、交互式 auth flow 和复杂版本求解仍作为独立
registry 切片推进；v0.1 遇到同一 canonical package id 的多版本冲突可以直接报错。

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
std.char
std.os
std.time
std.process
std.testing
std.debug
std.log
std.path
std.math
std.num
std.hash
std.crypto
std.json
std.regex
std.collections
```

### 6.1 `std.io`

```rust
pub struct IoError {
    pub message: string
}

io.print("hello")
io.println("hello")
io.eprint("error")
io.eprintln("error")
io.read_line() -> Result<string, IoError>
```

### 6.2 `std.fs`

```rust
pub struct FsError {
    pub message: string
}

pub struct FileMetadata {
    pub is_file: bool
    pub is_dir: bool
    pub size: u64
}

pub struct File

fn read_to_string(path: string) -> Result<string, FsError>
fn write_string(path: string, content: string) -> Result<void, FsError>
fn read_bytes(path: string) -> Result<Array<u32>, FsError>
fn write_bytes(path: string, bytes: Array<u32>) -> Result<void, FsError>
fn exists(path: string) -> bool
fn metadata(path: string) -> Result<FileMetadata, FsError>
fn create_dir(path: string) -> Result<void, FsError>
fn remove_dir(path: string) -> Result<void, FsError>
fn read_dir(path: string) -> Result<Array<string>, FsError>
fn open(path: string) -> Result<File, FsError>

impl File {
    fn read_to_string(self) -> Result<string, FsError>
    fn write_string(self, content: string) -> Result<void, FsError>
    fn close(self) -> void
}
```

`metadata` 返回文件类型标志和字节大小。目录大小为平台定义。
`open` 打开已存在文件用于读写。`File.read_to_string` 从文件开头读取完整内容；
`File.write_string` 从文件开头写入并 flush。
`read_dir` 返回目录项名称，不返回完整路径，并跳过 `.` 和 `..`。
`remove_dir` 只删除空目录。

### 6.3 `std.env`

`env.set` 修改当前进程环境变量，平台调用失败时 panic。`env.cwd` 在无法读取
当前目录时 panic。`env.temp_dir` 依次读取 `TMPDIR`、`TEMP`、`TMP`，
没有命中时回退到 `/tmp`。

```rust
env.args() -> Array<string>
env.get(name: string) -> Option<string>
env.set(name: string, value: string) -> void
env.cwd() -> string
env.home_dir() -> Option<string>
env.temp_dir() -> string
```

### 6.4 `std.array`

```rust
Array.new<T>() -> Array<T>
Array.len(self) -> u64
Array.push(mut self, value: T)
Array.get(self, index: u64) -> Option<T>
Array.pop(mut self) -> Option<T>
Array.remove(mut self, index: u64) -> Option<T>
Array.set(mut self, index: u64, value: T) -> void
Array.insert(mut self, index: u64, value: T) -> void
Array.clear(mut self) -> void
Array.iter(self) -> Array<T>
```

### 6.5 `std.result`

`std.result` helper 同时支持 module function、具体导入和 value method 三种用法。
`map`、`map_err` 与 `and_then` 在 v0.1 中接收具名、非限定、非泛型
converter 函数；闭包不属于 v0.1 范围。`and_then` 要求 converter 返回
错误类型相同的 `Result<U, E>`。

```rust
result.is_ok(value: Result<T, E>) -> bool
result.is_err(value: Result<T, E>) -> bool
result.unwrap_or(value: Result<T, E>, default: T) -> T
result.map(value: Result<T, E>, converter: fn(T) -> U) -> Result<U, E>
result.map_err(value: Result<T, E1>, converter: fn(E1) -> E2) -> Result<T, E2>
result.and_then(value: Result<T, E>, converter: fn(T) -> Result<U, E>) -> Result<U, E>
```

### 6.6 `std.option`

`std.option` helper 同时支持 module function、具体导入和 value method 三种用法。
`map` 与 `and_then` 在 v0.1 中接收具名、非限定、非泛型 converter 函数；闭包
不属于 v0.1 范围。

```rust
option.is_some(value: Option<T>) -> bool
option.is_none(value: Option<T>) -> bool
option.unwrap_or(value: Option<T>, default: T) -> T
option.map(value: Option<T>, converter: fn(T) -> U) -> Option<U>
option.and_then(value: Option<T>, converter: fn(T) -> Option<U>) -> Option<U>
```

### 6.7 `std.string`

`std.string` helper 在 v0.1 中按 UTF-8 字节字符串工作。`trim` 与大小写转换
使用 ASCII 字符类，不提供 Unicode grapheme 或 locale 规则。
`string.split(value, separator)` 在 `separator` 为空时 panic。

```rust
string.len(self) -> u64
string.concat(self, other: string) -> string
string.is_empty(self) -> bool
string.contains(self, needle: string) -> bool
string.starts_with(self, prefix: string) -> bool
string.ends_with(self, suffix: string) -> bool
string.split(self, separator: string) -> Array<string>
string.trim(self) -> string
string.to_lower(self) -> string
string.to_upper(self) -> string
```

### 6.8 `std.char`

`std.char` 字符分类 helper 在 v0.1 中使用 ASCII 字符类。`char.to_string`
把 Nomo `char` 标量编码为 UTF-8 字符串。

```rust
char.is_digit(value: char) -> bool
char.is_alpha(value: char) -> bool
char.is_whitespace(value: char) -> bool
char.to_string(value: char) -> string
```

### 6.9 `std.os`

`std.os` helper 报告生成程序所使用 C compiler target 的属性。

```rust
os.platform() -> string
os.arch() -> string
os.path_separator() -> string
os.line_ending() -> string
```

`os.platform()` 返回 `windows`、`macos`、`linux`、`freebsd` 或 `unknown`。
`os.arch()` 返回 `aarch64`、`x86_64`、`x86`、`arm` 或 `unknown`。

### 6.10 `std.time`

`std.time` 提供基础 wall clock、monotonic clock、duration、format 与 sleep helper。
`time.now_millis()` 返回 Unix epoch 毫秒。`time.monotonic_millis()` 适合在
单个进程内测量耗时，不能与 wall-clock 时间戳比较。`Duration` 保存有符号毫秒数。
`time.format_duration` 使用稳定的 v0.1 格式 `<millis>ms`，例如 `1500ms`。
`time.duration_seconds` 在秒转换为毫秒会溢出 `i64` 时 panic。`time.sleep` 与
`time.sleep_millis` 在 duration 为负数或平台 sleep 调用失败时 panic。

```rust
struct Duration {
    millis: i64
}

time.now_millis() -> i64
time.monotonic_millis() -> i64
time.duration_millis(millis: i64) -> Duration
time.duration_seconds(seconds: i64) -> Duration
time.duration_as_millis(duration: Duration) -> i64
time.format_duration(duration: Duration) -> string
time.sleep(duration: Duration) -> void
time.sleep_millis(duration: i64) -> void
```

### 6.11 `std.process`

```rust
pub struct ProcessError {
    pub message: string
}

pub struct ProcessOutput {
    pub status: i32
    pub stdout: string
    pub stderr: string
}
```

`std.process` 提供同步进程 helper。`process.spawn` 启动 shell 命令并等待
结束，不捕获 stdout/stderr，返回命令退出码。`process.status` 具有相同的
退出码行为，保留为只关心最终状态时的描述性 helper。`process.exec` 捕获
stdout，并在启动、读取、关闭或非零退出状态时返回 `Err`。`process.output`
分别捕获 stdout/stderr；即使命令以非零状态退出，也返回
`Ok(ProcessOutput)`，调用者读取 `status`。v0.1 不暴露异步 process handle。

```rust
process.exit(code: i64) -> void
process.spawn(command: string) -> Result<i32, ProcessError>
process.status(command: string) -> Result<i32, ProcessError>
process.exec(command: string) -> Result<string, ProcessError>
process.output(command: string) -> Result<ProcessOutput, ProcessError>
```

### 6.12 `std.path`

`std.path` 提供纯字符串路径 helper。v0.1 使用 POSIX 风格 `/` 分隔符，
不查询宿主文件系统，也不解析符号链接。

```rust
path.join(left: string, right: string) -> string
path.basename(path: string) -> string
path.dirname(path: string) -> string
path.extension(path: string) -> string
path.normalize(path: string) -> string
path.is_absolute(path: string) -> bool
```

### 6.13 `std.math`

`std.math` 提供基础数值 helper。`abs`、`min`、`max` 保留输入数值类型，
并要求操作数类型匹配；其余 helper 当前为 `f64` 函数。

```rust
math.abs(value: number) -> same number type
math.min(left: number, right: same number type) -> same number type
math.max(left: number, right: same number type) -> same number type
math.floor(value: f64) -> f64
math.ceil(value: f64) -> f64
math.round(value: f64) -> f64
math.sqrt(value: f64) -> f64
math.pow(base: f64, exponent: f64) -> f64
math.sin(value: f64) -> f64
math.cos(value: f64) -> f64
```

### 6.14 `std.num`

`std.num` 提供数值转换 helper。parse helper 返回 `Result<T, NumError>`，
预期与 `?` 操作符组合使用。checked 整数 helper 返回 `Option<T>`；
wrapping 整数 helper 返回相同整数类型并使用 wraparound 语义。v0.1 中
`num.to_string` 保持模块限定调用，避免与 `char.to_string` 的裸导入产生
名称冲突。

```rust
pub struct NumError {
    pub message: string
}

num.parse_i64(value: string) -> Result<i64, NumError>
num.parse_u64(value: string) -> Result<u64, NumError>
num.parse_f64(value: string) -> Result<f64, NumError>
num.to_string(value: i64 | i32 | u32 | u64 | f64) -> string
num.checked_add(left: integer, right: same integer type) -> Option<same integer type>
num.checked_sub(left: integer, right: same integer type) -> Option<same integer type>
num.checked_mul(left: integer, right: same integer type) -> Option<same integer type>
num.wrapping_add(left: integer, right: same integer type) -> same integer type
num.wrapping_sub(left: integer, right: same integer type) -> same integer type
num.wrapping_mul(left: integer, right: same integer type) -> same integer type
```

### 6.15 `std.hash`

`std.hash` 提供稳定的非加密 FNV-1a 64-bit 字符串与 `Array<u32>` byte array
hash helper。`HashState` 以值语义保存增量 hash 状态，因此调用者可以用多个
字符串或 byte chunk 构造与一次性 hash 相同的结果，而不需要可变引用。
byte array 使用与 `std.fs` byte helper、`std.crypto.random_bytes` 相同的
`0..255` 元素约定。加密摘要属于 `std.crypto`，不属于 `std.hash`。

```rust
pub struct HashState {
    pub value: u64
}

hash.string(value: string) -> u64
hash.bytes(value: Array<u32>) -> u64
hash.new() -> HashState
hash.write_string(state: HashState, value: string) -> HashState
hash.write_bytes(state: HashState, value: Array<u32>) -> HashState
hash.finish(state: HashState) -> u64
```

### 6.16 `std.crypto`

`std.crypto` 提供加密 helper。摘要 helper 把 string 输入按 UTF-8 字节计算
hash，并返回小写十六进制字符串。`random_bytes` 返回由操作系统生成的随机
字节，并在 v0.1 中用 `Array<u32>` 表示，每个元素都在 `0..255` 范围内；
专用 byte array 类型留到后续版本。

```rust
crypto.sha256(value: string) -> string
crypto.sha512(value: string) -> string
crypto.random_bytes(count: u64) -> Array<u32>
```

### 6.17 `std.json`

`std.json` 提供 v0.1 JSON 校验与序列化边界。`JsonValue` 保存已经通过
语法校验的原始 JSON 文本。`json.parse` 校验 JSON 语法并返回
`Result<JsonValue, JsonError>`；`json.stringify` 返回保存的 JSON 文本。
结构化字段/索引访问留给后续切片。

```rust
pub struct JsonValue {
    pub raw: string
}

pub struct JsonError {
    pub message: string
}

json.parse(value: string) -> Result<JsonValue, JsonError>
json.stringify(value: JsonValue) -> string
```

### 6.18 `std.net`

`std.net` 在当前切片提供阻塞 TCP 与 UDP helper。`net.connect` 连接 host
和 port。`net.listen` 绑定阻塞 `TcpListener`；`TcpListener.accept` 返回下一条
`TcpStream`，`TcpListener.close` 关闭 listener socket。`TcpStream.write_string`
向 peer 写入字符串，`TcpStream.read_to_string` 读取直到 peer 关闭写端，
`TcpStream.close` 关闭 stream socket。`net.udp_bind` 绑定阻塞 `UdpSocket`；
`UdpSocket.recv_from_string` 接收 datagram 并返回包含 `data`、`host`、`port`
的 `UdpDatagram`，`UdpSocket.send_to_string` 发送 datagram，`UdpSocket.close`
关闭 socket。listener 地址查询、backlog 配置与 nonblocking handle 留给后续
`std.net` 切片。

```rust
pub struct NetError {
    pub message: string
}

pub struct TcpStream

pub struct TcpListener

pub struct UdpDatagram {
    pub data: string
    pub host: string
    pub port: i64
}

pub struct UdpSocket

net.connect(host: string, port: i64) -> Result<TcpStream, NetError>
net.listen(host: string, port: i64) -> Result<TcpListener, NetError>
net.udp_bind(host: string, port: i64) -> Result<UdpSocket, NetError>

impl TcpListener {
    fn accept(self) -> Result<TcpStream, NetError>
    fn close(self) -> void
}

impl TcpStream {
    fn write_string(self, content: string) -> Result<void, NetError>
    fn read_to_string(self) -> Result<string, NetError>
    fn close(self) -> void
}

impl UdpSocket {
    fn recv_from_string(self, max_bytes: i64) -> Result<UdpDatagram, NetError>
    fn send_to_string(self, content: string, host: string, port: i64) -> Result<void, NetError>
    fn close(self) -> void
}
```

### 6.19 `std.http`

`std.http` 在当前切片提供阻塞 plain-HTTP client helper 与基础 server
helper。`http.get` 请求 `http://` URL。`http.post` 向 `http://` URL 发送
string body。响应暴露数字 HTTP status 与 response body。`http.listen` 创建
阻塞 server socket，`http.accept` 接受一个 request exchange，
`http.respond_string` 写入 string response。程序应使用
`defer http.close_exchange(exchange)` 和 `defer http.close_server(server)` 关闭
handle，使正常返回与 `?` 早退都会清理资源。TLS、自定义 header、redirect、
chunked transfer 解码、streaming body、routing 与并发 server helper 留给后续
`std.http` 切片。

```rust
pub struct HttpError {
    pub message: string
}

pub struct HttpResponse {
    pub status: i64
    pub body: string
}

pub struct HttpServer {
}

pub struct HttpExchange {
    pub method: string
    pub path: string
    pub body: string
}

http.get(url: string) -> Result<HttpResponse, HttpError>
http.post(url: string, body: string) -> Result<HttpResponse, HttpError>
http.listen(host: string, port: i64) -> Result<HttpServer, HttpError>
http.accept(server: HttpServer) -> Result<HttpExchange, HttpError>
http.respond_string(exchange: HttpExchange, status: i64, body: string) -> Result<void, HttpError>
http.close_server(server: HttpServer) -> void
http.close_exchange(exchange: HttpExchange) -> void
```

### 6.20 `std.regex`

`std.regex` 提供 v0.1 正则表达式 helper。`Regex` 保存经过
`regex.compile` 校验后的源 pattern。编译失败通过
`Result.Err(RegexError)` 报告，因此调用方使用 postfix `?` 做传播。
`regex.captures` 无匹配时返回 `None`；匹配成功时返回
`Some(Array<string>)`，内容为完整匹配和后续 capture groups。

```rust
pub struct Regex {
    pub pattern: string
}

pub struct RegexError {
    pub message: string
}

regex.compile(pattern: string) -> Result<Regex, RegexError>
regex.is_match(regex: Regex, value: string) -> bool
regex.captures(regex: Regex, value: string) -> Option<Array<string>>
```

### 6.21 `std.collections`

`std.collections` 提供 v0.1 字符串专用集合。`StringMap` 存储 string key
和 string value；`StringSet` 存储去重 string。更新 helper 返回更新后的集合
值；泛型 `HashMap` 等 interface/trait constrained generics 可用后再补齐。

```rust
pub struct StringMap {
    pub keys: Array<string>
    pub values: Array<string>
}

pub struct StringSet {
    pub values: Array<string>
}

collections.map_new() -> StringMap
collections.map_len(map: StringMap) -> u64
collections.map_get(map: StringMap, key: string) -> Option<string>
collections.map_contains(map: StringMap, key: string) -> bool
collections.map_set(map: StringMap, key: string, value: string) -> StringMap
collections.map_remove(map: StringMap, key: string) -> StringMap

collections.set_new() -> StringSet
collections.set_len(set: StringSet) -> u64
collections.set_contains(set: StringSet, value: string) -> bool
collections.set_insert(set: StringSet, value: string) -> StringSet
collections.set_remove(set: StringSet, value: string) -> StringSet
```

### 6.22 `std.testing`

`std.testing` 提供面向 `#[test]` 函数的 assertion helper。断言失败时会
panic，因此当前测试会在 `nomo test` 下失败。`testing.assert_equal` 支持
string，以及类型一致的 bool、char、整数和 `f64` primitive 值。
`testing.assert_error` 接受任意 `Result<T, E>`，仅在值为 `Err` 时通过。

```rust
testing.assert(condition: bool, message: string) -> void
testing.assert_equal<T: primitive-or-string>(left: T, right: T) -> void
testing.assert_error<T, E>(result: Result<T, E>) -> void
```

### 6.23 `std.debug`

`std.debug` 提供轻量调试 helper。print helper 写入 stderr。`debug.panic`
复用语言内建 `panic` 的执行路径。`debug.backtrace` 在 v0.1 返回稳定占位
字符串；这样代码可以先依赖 API，真实 stack capture 后续再接入。

```rust
debug.print(message: string) -> void
debug.println(message: string) -> void
debug.panic(message: string) -> void
debug.backtrace() -> string
```

### 6.24 `std.log`

`std.log` 提供轻量分级日志 helper。日志消息以 `[level] message` 行写入
stderr。`NOMO_LOG` 控制最低启用级别；可接受值为 `debug`、`info`、`warn`、
`error` 和 `off`。未设置或无法识别时默认使用 `info` 阈值。

```rust
log.debug(message: string) -> void
log.info(message: string) -> void
log.warn(message: string) -> void
log.error(message: string) -> void
log.enabled(level: string) -> bool
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
- 包路径参与符号混淆，避免命名冲突。v0.1 生成 C 的 function 与 nominal type symbol
  使用每个 item 的源码 package path，因此 dependency API 不会被生成为 root application
  package 的符号。
- 标准库运行时以 C 源文件链接。
- `Result`、`Option`、`Array` 等布局必须有测试覆盖。

---

## 8. 诊断规范

诊断必须同时支持人类可读输出和 JSON 输出。

错误码范围：

| 范围 | 类别 |
| --- | --- |
| `E0100-E0199` | 词法错误 |
| `E0200-E0299` | 语法错误 |
| `E0300-E0399` | 名称解析 |
| `E0400-E0499` | 类型检查 |
| `E0500-E0599` | 借用与可变性 |
| `E0600-E0699` | 模块与包 |
| `E0700-E0799` | C 后端 |
| `E0800-E0899` | 标准库与运行时 API |
| `E0900-E0999` | manifest、lockfile 与依赖解析 |
| `E1000-E1099` | workspace |
| `E1100-E1199` | test runner |
| `E1200-E1299` | doc generator |
| `E1300-E1399` | LSP semantic API |
| `E1400-E1499` | registry 与 publish |
| `E1500-E1599` | FFI 与 unsafe |

JSON 诊断至少包含：

```json
{
  "status": "error",
  "error_code": "E0203",
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

诊断文档放在 `docs/diagnostics/`。LSP diagnostic 的 `codeDescription`
应指向对应错误码文档，例如 `E0404.md`。

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
- `nomo fmt --check` 在已提交的 `.nomo` examples 与 fixtures 上通过。
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
