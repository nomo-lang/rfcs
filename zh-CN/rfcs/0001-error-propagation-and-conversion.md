# RFC 0001：`?` 传播与缺少自动错误转换的体验矛盾

> 语言 / Language: 中文 | [English](../../en/rfcs/0001-error-propagation-and-conversion.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0001 |
| 标题 | `?` 传播与缺少自动错误转换的体验矛盾 |
| 状态 | Accepted（已接受） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-06-18 |
| 实现状态 | 已落地：`Result`/`Option` 后缀 `?`、同 carrier 早退及 `std.result.map_err(named_converter)?` 均有编译器与运行测试覆盖 |
| 关联主题 | 错误处理、`Result`、`?` 传播、错误转换、C 后端 |
| 关联 RFC | [RFC 0006](./0006-option-result-lang-items.md)（Option/Result 的编译器内建身份） |

---

## 1. 摘要

当前错误处理规格明确规定 v0.1 不提供匿名错误联合体，也不自动合并错误类型。因此跨层错误转换需要在传播前显式完成。本 RFC 接受 `std.result.map_err(converter)?` 作为 v0.1 答案：`?` 保持为唯一传播语法，`map_err` 负责具名函数错误转换，`From`/`Into` 风格自动转换与匿名错误联合体推迟到 v0.1 之后。

---

## 2. 动机（Motivation）

`?` 是 v0.1 错误处理的核心人体工学卖点（见交付边界「后缀 `?`」列为必交付项）。但若 `?` 只能在「函数错误类型与被调用错误类型完全一致」时使用，它的适用面会被严重压缩：

- 多数业务函数返回自定义错误（如文件读取示例中的 `AppError`）。
- 多数底层调用返回库错误（如 `FsError`）。
- 两者类型不同，`?` 直接报类型不兼容，开发者只能写 `match` 手动转换。

结果是：当前规格文件读取示例中的 `read_config` **根本无法使用 `?`**——它必须写成 `match fs.read_to_string(path) { ... }`，把 `FsError` 转换成 `AppError.ReadFailed`。这说明 `?` 在当前规格自己的旗舰示例里就用不上，这是一个需要正视的体验缺口。

---

## 3. 现状与问题

### 3.1 当前规格现状

当前错误处理规格规定 `expr?` 的语义：

- `Result.Ok(value)` → 求值为 `value`；
- `Result.Err(error)` → 当前函数立即 `return Result.Err(error)`；
- 「当前函数返回类型必须也是兼容的 `Result`」。

同时强调：

> v0.1 不提供匿名错误联合体，不自动合并错误类型。跨层错误转换必须显式完成。
> 自动错误联合体可作为后续 RFC，不进入 v0.1。

早期错误转换议题还提出过「`Result` 错误转换是否引入 `From` 风格 trait」；本 RFC 将其明确推迟到后续版本。

### 3.2 问题分析

「兼容的 `Result`」在当前规格中未定义到底是「`E` 类型严格相等」还是「`E` 可转换」。从“不自动合并错误类型”的规则推断，只能是**严格相等**。于是：

```rust
fn read_config(path: string) -> Result<string, AppError> {
    // 想这样写，但 fs.read_to_string 返回 Result<string, FsError>，E 不等于 AppError
    let text = fs.read_to_string(path)?   // ❌ 类型不兼容：期望 AppError，实际 FsError
    Result.Ok(text)
}
```

只能退回显式 `match` 转换写法：

```rust
fn read_config(path: string) -> Result<string, AppError> {
    match fs.read_to_string(path) {
        Result.Ok(text) => Result.Ok(text)
        Result.Err(err) => Result.Err(AppError.ReadFailed(err.message))
    }
}
```

矛盾点：**`?` 的价值在于跨层传播，而跨层几乎必然伴随错误类型变化**。禁止自动转换 = `?` 仅在「错误类型一路不变」的少数场景（例如同一模块内、错误类型已统一）可用。这会让用户和 AI 生成的代码倾向于「能不用 `?` 就不用」，削弱“避免同一语义多种写法”的设计目标。

---

## 4. 详细设计

下面三种方案均围绕「如何把 `FsError` 变成 `AppError` 后再传播」展开。

### 4.1 方案 A：引入 `From`/`Into` 风格错误转换 trait

- **语法**：`?` 在 `Err` 分支自动调用 `AppError::from(err)`（具体语法待定；v0.1 的最小 interface 约束不包含 associated/static conversion lookup）。例如：

```rust
impl AppError {
    fn from_fs(err: FsError) -> AppError {
        AppError.ReadFailed(err.message)
    }
}
// 编译器在 ? 的 Err 分支隐式插入 from 转换
```

- **语义**：`expr?` 当 `Err(e)` 时，若当前函数错误类型 `E2 != E1`，查找已注册的 `E1 -> E2` 转换并应用；找不到则报错。
- **C 后端**：在 `?` 展开点插入一次转换函数调用，再 `return` 包装后的 `Result_T_E2`。
- **诊断**：新增「找不到错误转换」错误码（E0400-E0499 类型检查区间，例如 `E0461`）。
- **代价**：v0.1 仅支持单个 `T: Interface` 的静态约束，不支持 associated function、blanket impl 或隐式转换查找；引入 `From` 风格机制仍需扩展 interface 系统或增加特例化的「转换注册」子系统。

### 4.2 方案 B：标准库 `.map_err()` 显式方法（已接受）

- **语法**：保持 `?` 语义不变，提供 `std.result` 上的 `map_err`：

```rust
fn read_config(path: string) -> Result<string, AppError> {
    let raw: Result<string, FsError> = fs.read_to_string(path)
    let text: string = raw.map_err(app_error_from_fs)?
    Result.Ok(text)
}
```

- **语义**：`map_err` 把 `Result<T, E1>` 映射为 `Result<T, E2>`，之后 `?` 在类型相等前提下传播。无需任何隐式转换或 trait。
- **C 后端**：`map_err` 单态化为普通 helper，接收具名、非限定、非泛型 converter 函数。闭包与匿名函数值不进入 v0.1。
- **诊断**：无新增穷尽性/转换错误码；类型不匹配仍走既有 N04xx。
- **依赖**：v0.1 要求传具名 `fn`：`.map_err(app_error_from_fs)?`。

### 4.3 方案 C：匿名错误联合体（隐式合并）

- **语法**：函数声明 `-> Result<T, FsError | ParseError>`，`?` 自动把子错误装入联合体。
- **语义**：编译器在 `?` 处把 `E1` 注入联合体 `E1 | E2 | ...`。
- **C 后端**：联合体需运行期标签，布局复杂，且与 4.4 的固定 `Result_T_E` 结构相比要引入「错误类型标签 + 多臂 union」。
- **代价**：当前错误处理规格已点名这是「后续 RFC，不进入 v0.1」；类型推断与诊断复杂度高。

---

## 5. 备选方案（Alternatives）

| 方案 | 做法 | 优点 | 缺点 |
| --- | --- | --- | --- |
| A `From` trait | `?` 隐式调用错误转换 | 体验最接近 Rust，样板最少 | 需提前引入 trait/转换注册，违反 3.9 MVP 边界；隐式性降低可读性 |
| B `.map_err()`（已接受） | 显式映射后再 `?` | 不破坏 `?` 语义、无隐式魔法、契合「显式优先」；v0.1 可用具名 converter 函数实现 | 仍有少量样板；闭包式内联 converter 推迟 |
| C 匿名联合体 | `Result<T, A \| B>` 自动合并 | 无需手写转换 | 4.4 固定布局被打破、类型推断/诊断复杂，明确超出 v0.1 |

---

## 6. 缺点与风险

- v0.1 的 `map_err` 接收具名 converter 函数，内联转换仍比闭包形态冗长。
- 「兼容的 `Result`」固定为：显式转换后 `Ok` payload 匹配，错误类型严格相等。
- 若未来加入 `From` 风格机制，需要迁移叙事，避免 `map_err(...)?` 与隐式转换成为两套同等推荐写法。

---

## 7. 对 v0.1 范围的影响

- **v0.1 落地**：方案 B 的 `std.result.map_err`，先支持具名 converter 函数，并把 `.map_err(...)?` 记录为跨层转换后的推荐传播方式。
- **明确推迟**：方案 A（`From` 风格）与方案 C（匿名联合体）留作 v0.2+ 的独立 RFC。
- **验收影响**：验收矩阵包含 `map_err` + `?` 跨层传播示例与测试。

---

## 8. 决议

接受 **方案 B**。v0.1 使用后缀 `?` 作为唯一传播语法，并使用显式 `std.result.map_err(named_converter)?` 完成跨层错误转换。`try` 语法、隐式 `From` 转换与匿名错误联合体均不属于 v0.1。

---

## 9. 未决问题

- 后续闭包语法是否应允许 `map_err` 内联 converter。
- 后续 `From` 风格转换机制应与显式 `map_err(...)?` 共存，还是取代它。
- 是否同时提供 `map`（针对 `Ok`）以保持 API 对称。

---

## 10. 参考

- 当前错误处理、`Result<T, E>`、`?` 传播、C 后端表示、文件读取示例。
- 后续错误转换议题（`From` 风格 trait）。
- [RFC 0006](./0006-option-result-lang-items.md)（`Option`/`Result` 的编译器内建身份）。
