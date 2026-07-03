# RFC 0006：`Option`/`Result` 标准库与编译器内建认知的循环依赖

> 语言 / Language: 中文 | [English](../../en/rfcs/0006-option-result-lang-items.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0006 |
| 标题 | `Option`/`Result` 是纯库还是编译器 lang item |
| 状态 | Draft（待决） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-06-18 |
| 关联主题 | lang item、`Option`、`Result`、标准库边界、C 后端 |
| 关联 RFC | [RFC 0001](./0001-error-propagation-and-conversion.md)（`?` 传播）、[RFC 0002](./0002-match-wildcard-and-nesting.md)（match 穷尽性）、[RFC 0007](./0007-unqualified-variant-access.md)（变体访问） |

---

## 1. 摘要

`std.option`、`std.result` 在当前规格中被列为标准库包（标准库设计），但它们同时是语言核心机制的载体：`?` 传播依赖 `Result` 的 `Ok`/`Err` 结构，`match` 穷尽性和 C 后端的 `Result_T_E` 布局也需要编译器「认得」这两个类型。当前规格没有点明这层耦合——既要它们是普通库，又要编译器对它们有内建认知，形成循环依赖。本 RFC 讨论应将它们设为编译器「已知 lang item」还是纯库，倾向于「把 `Option`/`Result` 声明为 lang item：定义仍写在 `std.option`/`std.result`，但编译器通过属性/约定识别它们以支撑 `?`、穷尽性与 codegen」，保持 Draft。

---

## 2. 动机（Motivation）

交付边界同时要求「`Result<T,E>`、`Option<T>`、后缀 `?`」（语言能力）与「`std.result`、`std.option`」（标准库包）。这两件事在当前规格里是分开列的，但实现上它们指的是同一个类型。问题是：编译器要支持

- `?`：必须知道「什么是 `Ok`、什么是 `Err`、如何从 `Result` 提取/早退」。
- `match` 穷尽性：对 `Option`/`Result` 也按普通枚举做穷尽即可，但 codegen 的 `Result_T_E`是**专门**为它设计的布局。
- 变体构造 `Result.Ok` / `Option.Some`：名称解析要能定位到 `std.result.Result` 的变体。

如果把它们当成「编译器一无所知的普通库类型」，`?` 和 4.4 的专用布局就无从谈起；如果当成「编译器内建类型」，又与标准库设计「它们是标准库包」矛盾。不澄清这点，会导致 编译器架构（名称解析、类型检查、codegen）在实现时反复纠结「该不该特判这两个类型」。

---

## 3. 现状与问题

### 3.1 当前规格现状

- 枚举示例：`Option<T>` 作为带载荷枚举示例给出（`Some(T)` / `None`）。
- `Result` 定义：`Result<T,E>` 定义在 `package std.result` 中（`Ok(T)` / `Err(E)`）。
- `?` 语义：`?` 的语义直接以 `Result.Ok`/`Result.Err` 表述。
- C 后端：C 后端给出**专用**的 `Result_T_E`（`bool is_ok; union {ok; err;}`）。
- 标准库设计：`std.option`、`std.result` 列为 v0.1 标准库包。
- 示例（文件读取与数组交换示例）通过 `import std.result.Result` / `import std.option.Option` 引入。

### 3.2 问题分析

- **循环依赖**：标准库定义类型 → 编译器要内建认知该类型 → 才能编译标准库自身（`std.result` 里 `Result` 的定义本身、以及任何用到 `?` 的库代码）。
- **`?` 必须有锚点**：`expr?` 的展开规则必须绑定到某个「已知的 `Result`」，否则用户随便定义一个同名 `Result` 也能 `?`？还是只有 `std.result.Result` 能 `?`？当前规格未答。
- **codegen 专用布局**：4.4 的 `Result_T_E` 说明 codegen 对 `Result` 不是「泛化枚举布局」而是**特例**，这等于已经把它当 lang item 了，只是没明说。
- **`Option` 的内建程度**：`Option` 没有 `?`（4.3 只提 `Result`），但 `Array.get`（8.4）、`std.env.get`（8.3）都返回 `Option`，且 [RFC 0002](./0002-match-wildcard-and-nesting.md) 可能给 `Option` 加 `?` 风格早退；其内建程度需与 `Result` 一并定。

---

## 4. 详细设计

### 4.1 方案 A：纯库（编译器无特判）

- **做法**：`Option`/`Result` 就是普通泛型枚举；`?` 改为「对任意满足某结构的枚举生效」或干脆要求标准模式匹配。
- **优点**：编译器最干净，无特殊类型。
- **缺点**：`?`失去明确锚点；专用 C 布局失去依据（要么所有枚举都用该布局，要么放弃专用布局）；难以保证「`?` 只对错误传播语义生效」。基本无法兑现当前规格既有承诺。

### 4.2 方案 B：完全内建（编译器内置类型，库只做转发）

- **做法**：`Option`/`Result` 由编译器内建定义，`std.option`/`std.result` 仅 re-export。
- **优点**：`?`、穷尽性、codegen 全部有稳定锚点。
- **缺点**：与标准库设计「它们是标准库包」字面冲突；用户阅读标准库源码时看不到真正定义，违背“稳定锚点”可读性。

### 4.3 方案 C：lang item（倾向）

- **做法**：类型**定义仍写在** `std.option`/`std.result` 源码里（保留标准库设计「是标准库包」的事实），但通过 **lang item 标注**让编译器识别它们，例如内部属性：

```rust
package std.result

#[lang = "result"]
pub enum Result<T, E> {
    Ok(T)
    Err(E)
}
```

```rust
package std.option

#[lang = "option"]
pub enum Option<T> {
    Some(T)
    None
}
```

- **语义**：
  - `?`只对被标注为 `lang = "result"` 的类型生效，锚点明确。
  - `match` 穷尽性对它们与普通枚举一致处理（无需特判），但 codegen 可识别 lang item 应用专用 `Result_T_E` 布局。
  - 名称解析把 `Result.Ok`/`Option.Some` 当普通枚举变体处理（与 [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md) 一致），[RFC 0007](./0007-unqualified-variant-access.md) 的 prelude/非限定变体也作用于这两个 lang item。
- **解决循环依赖**：编译 `std.result` 自身时，lang item 注册先于使用；标准库可分两层——纯定义层（不依赖 `?`）先编译，依赖 `?` 的库代码后编译。
- **C 后端**：codegen 见到 lang item `result` 即套用 4.4 布局；`option` 用类似的 `Option_T`（`bool is_some; union{...}`）。
- **诊断**：
  - `N0330` 找不到 `result`/`option` lang item（标准库缺失或未标注）。
  - `?` 用在非 `result` lang item 上 → 类型检查报错（N04xx）。
- **属性语法依赖**：需要一个最小的内部属性机制（`#[lang = "..."]`）。该属性可设为**仅编译器/标准库内部可用**，不开放给用户，避免提前引入完整属性系统。

---

## 5. 备选方案（Alternatives）

| 方案 | 做法 | 优点 | 缺点 |
| --- | --- | --- | --- |
| A 纯库 | 无特判 | 编译器最干净 | `?`/4.4 失去锚点，无法兑现当前规格 |
| B 完全内建 | 编译器内置，库转发 | 锚点最稳 | 与「是标准库包」冲突、源码不可读 |
| C lang item（倾向） | 定义在库，编译器按标注识别 | 兼顾「库」与「内建认知」、可读、锚点明确 | 需最小内部属性机制 |

---

## 6. 缺点与风险

- 方案 C 需要引入内部属性 `#[lang = "..."]`。必须明确它**不是**面向用户的通用属性系统（那是后续 RFC），仅供标准库/编译器内部使用，否则会扩大 v0.1 语法表面积。
- 标准库分层编译（先定义层、后 `?` 使用层）需要在构建顺序中体现，避免自举式循环。
- `Option` 与 `Result` 内建程度需对齐：两者都设为 lang item，v0.1 的 `?` 同时作用于 `Result` 与 `Option`，并按 carrier 执行对应早退。

---

## 7. 对 v0.1 范围的影响

- **建议 v0.1 落地**：方案 C。把 `Option`/`Result` 声明为 lang item，定义保留在 `std.option`/`std.result`；编译器据此支撑 `?`、codegen 专用布局与（未来的）prelude。
- **建议当前规格补充**：在标准库设计或编译器架构新增一节，点明「`Option`/`Result` 是 lang item：既是标准库包，又被编译器识别」，消除当前的隐含耦合。
- **验收影响**：验收测试矩阵需新增「缺少/未标注 lang item 时报 `N0330`」「`?` 仅对已识别的 `Result`/`Option` carrier 生效」测试；codegen 测试确认 lang item 套用 4.4 布局。

---

## 8. 倾向性建议（保持 Draft，不拍板）

倾向 **方案 C（lang item）**：用最小的内部 `#[lang = "..."]` 标注把「标准库包」与「编译器内建认知」统一起来，既保住标准库设计的事实，又给 `?`（[RFC 0001](./0001-error-propagation-and-conversion.md)）、穷尽性（[RFC 0002](./0002-match-wildcard-and-nesting.md)）、codegen、变体简化（[RFC 0007](./0007-unqualified-variant-access.md)）提供稳定锚点。保持 Draft。

---

## 9. 未决问题

- 内部属性 `#[lang]` 的确切语法与可见性（是否对用户隐藏）。
- `Option`/`Result` 之外，是否还要为 `string`/`Array`（[RFC 0003](./0003-arc-cow-runtime-cost.md)）也设 lang item 以支撑专用运行时？
- 标准库分层编译顺序如何在 `nomo build` 与 编译器管线中固化。

---

## 10. 参考

- 当前 `Option`/`Result` 枚举设计、`?` 传播、C 后端表示、标准库边界、编译器架构、文件读取与数组交换示例。
- [RFC 0001](./0001-error-propagation-and-conversion.md)（`?` 锚点）、[RFC 0002](./0002-match-wildcard-and-nesting.md)（穷尽性）、[RFC 0007](./0007-unqualified-variant-access.md)（变体简化的 prelude 作用域）。
