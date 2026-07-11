# RFC 0006：`Option`/`Result` 标准库与编译器内建认知的循环依赖

> 语言 / Language: 中文 | [English](../../en/rfcs/0006-option-result-lang-items.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0006 |
| 标题 | `Option`/`Result` 是纯库类型还是编译器内建 carrier |
| 状态 | Accepted（已接受） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-06-18 |
| 实现状态 | 已落地：编译器内建 `Option`/`Result` carrier 身份、变体集合、`?` 语义与 C 布局；`std.option`/`std.result` 是稳定公共模块契约，不依赖 `#[lang]` 属性 |
| 关联主题 | 编译器内建身份、lang-item 迁移、`Option`、`Result`、标准库边界、C 后端 |
| 关联 RFC | [RFC 0001](./0001-error-propagation-and-conversion.md)（`?` 传播）、[RFC 0002](./0002-match-wildcard-and-nesting.md)（match 穷尽性）、[RFC 0007](./0007-unqualified-variant-access.md)（变体访问） |

---

## 1. 摘要

`Option`/`Result` 同时是公共标准库 API 和语言核心 carrier。当前实现采用编译器内建身份：编译器直接提供它们的泛型枚举形状、`?` 语义、核心 prelude 变体和 C 布局；`std.option`/`std.result` 则是用户可导入的稳定模块契约。v0.1 不解析或编译一份带 `#[lang]` 的 Nomo 标准库源码，因此不引入尚未实现的内部属性机制或标准库自举顺序。

---

## 2. 动机（Motivation）

交付边界同时要求「`Result<T,E>`、`Option<T>`、后缀 `?`」（语言能力）与「`std.result`、`std.option`」（标准库包）。这两件事在当前规格里是分开列的，但实现上它们指的是同一个类型。问题是：编译器要支持

- `?`：必须知道「什么是 `Ok`、什么是 `Err`、如何从 `Result` 提取/早退」。
- `match` 穷尽性：对 `Option`/`Result` 也按普通枚举做穷尽即可，但 codegen 的 `Result_T_E`是**专门**为它设计的布局。
- 变体构造 `Result.Ok` / `Option.Some`：名称解析要能定位到 `std.result.Result` 的变体。

如果把它们当成「编译器一无所知的普通库类型」，`?` 和 4.4 的专用布局就无从谈起；如果当成「编译器内建类型」，又与标准库设计「它们是标准库包」矛盾。不澄清这点，会导致 编译器架构（名称解析、类型检查、codegen）在实现时反复纠结「该不该特判这两个类型」。

---

## 3. 现状与问题

### 3.1 当前实现现状

- 枚举示例：`Option<T>` 作为带载荷枚举示例给出（`Some(T)` / `None`）。
- `Result`/`Option` 的公共身份分别通过 `std.result` 与 `std.option` 暴露；编译器按标准类型需求注入对应枚举定义。
- `?` 语义：`?` 的语义直接以 `Result.Ok`/`Result.Err` 表述。
- C 后端：C 后端给出**专用**的 `Result_T_E`（`bool is_ok; union {ok; err;}`）。
- 标准库设计：`std.option`、`std.result` 列为 v0.1 标准库包。
- 示例可显式导入 `std.result.Result` / `std.option.Option`；使用核心 prelude 变体时，编译器也会注入所需 carrier。

### 3.2 问题分析

- **循环依赖已消除**：v0.1 标准库由编译器内建 API 与 C runtime 组成，不先编译一份 Nomo 标准库源码，因此无需分层自举。
- **`?` 有明确锚点**：类型检查只接受编译器识别的 `Result<T,E>` 与 `Option<T>` carrier；普通用户枚举即使同名也不能替代标准类型。
- **codegen 专用布局**：C 后端按已检查的 carrier 类型生成 `Result`/`Option` 专用布局与早退路径。
- **内建程度对齐**：`Option` 与 `Result` 采用同一类编译器身份，并共同支撑标准库返回值、`?` 和核心 prelude。

---

## 4. 详细设计

### 4.1 方案 A：纯库（编译器无特判）

- **做法**：`Option`/`Result` 就是普通泛型枚举；`?` 改为「对任意满足某结构的枚举生效」或干脆要求标准模式匹配。
- **优点**：编译器最干净，无特殊类型。
- **缺点**：`?`失去明确锚点；专用 C 布局失去依据（要么所有枚举都用该布局，要么放弃专用布局）；难以保证「`?` 只对错误传播语义生效」。基本无法兑现当前规格既有承诺。

### 4.2 方案 B：编译器内建身份 + 标准模块契约（已接受）

- **做法**：`Option`/`Result` 的泛型枚举形状与 carrier 语义由编译器内建；`std.option`/`std.result` 作为导入、文档和标准 helper 的公共模块契约。编译器根据 import、类型使用、标准库 API 返回值和核心 prelude 使用情况注入需要的标准类型。
- **优点**：`?`、穷尽性、codegen 全部有稳定锚点。
- **缺点**：类型的规范定义目前位于编译器与规格，而不是可独立编译的 Nomo 标准库源码；未来外置标准库时需要迁移方案。

### 4.3 方案 C：源码 `#[lang]` 标注（v0.1 不采用）

- **候选做法**：类型定义写在 `std.option`/`std.result` 源码里，通过 lang-item 属性让编译器识别，例如：

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

- **若未来采用，其语义为**：
  - `?`只对被标注为 `lang = "result"` 的类型生效，锚点明确。
  - `match` 穷尽性对它们与普通枚举一致处理（无需特判），但 codegen 可识别 lang item 应用专用 `Result_T_E` 布局。
  - 名称解析把 `Result.Ok`/`Option.Some` 当普通枚举变体处理（与 [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md) 一致），[RFC 0007](./0007-unqualified-variant-access.md) 的 prelude/非限定变体也作用于这两个 lang item。
- **迁移要求**：需要先具备可编译的标准库源码、受控内部属性和清晰的引导顺序。
- **C 后端（若未来采用）**：codegen 将根据受控 lang item 身份套用 `Result`/`Option` 布局。
- **诊断（若未来采用）**：需要覆盖标准 carrier 缺失、重复或标注错误，以及 `?` 用在非 carrier 类型上的情况；具体错误码由迁移 RFC 分配。
- **属性语法依赖**：需要一个最小的内部属性机制（`#[lang = "..."]`）。当前 parser 只开放受支持的用户属性，因此该机制不能在 v0.1 文档中假定已经存在。

---

## 5. 备选方案（Alternatives）

| 方案 | 做法 | 优点 | 缺点 |
| --- | --- | --- | --- |
| A 纯库 | 无特判 | 编译器最干净 | `?`/4.4 失去锚点，无法兑现当前规格 |
| B 编译器内建身份（已接受） | 编译器提供 carrier，`std.*` 提供公共模块契约 | 与当前 runtime/类型检查一致，无自举循环 | 标准类型定义暂不在可编译的 Nomo 源码中 |
| C 源码 lang item | 定义在库，编译器按标注识别 | 兼顾「库」与「内建认知」、可读、锚点明确 | 当前没有该属性机制或标准库自举管线 |

---

## 6. 缺点与风险

- 方案 B 让编译器成为标准 carrier 形状的事实源；规格、诊断文档和内建定义必须同步更新。
- 将来若外置标准库源码，不得仅按短名称识别用户类型；需要受控的包身份或内部标注迁移方案。
- `Option` 与 `Result` 的内建程度必须保持对齐，`?` 按 carrier 执行各自的早退规则。

---

## 7. 对 v0.1 范围的影响

- **已在 v0.1 落地**：方案 B。编译器内建 `Option`/`Result` carrier，`std.option`/`std.result` 保持公共模块/API 身份。
- **规格处理**：明确当前内建边界，不宣称存在 `#[lang]` 属性或可独立编译的标准库定义层。
- **验收覆盖**：`?` 仅接受兼容 carrier，用户同名类型冲突会被拒绝，codegen 与生命周期测试覆盖 `Result`/`Option` 的专用表示和早退路径。

---

## 8. 决议

接受 **方案 B（编译器内建身份 + 标准模块契约）**。这是当前代码的真实架构：`Option`/`Result` 由编译器注入并被类型检查、`?`、prelude 与 C 后端共同识别；`std.option`/`std.result` 提供稳定的用户侧模块身份。v0.1 不引入未实现的 `#[lang]` 属性。未来若标准库改为 Nomo 源码，可用新 RFC 迁移到受控 lang-item 机制。

---

## 9. 后续问题

- 若标准库未来迁移为 Nomo 源码，内部身份采用包路径、受控属性还是生成清单。
- `string`/`Array` 等其它编译器/runtime 特殊类型是否需要统一的内部身份模型。
- 如何在迁移时保持现有 `std.option`/`std.result` API、诊断码和生成 C ABI 兼容。

---

## 10. 参考

- 当前 `Option`/`Result` 枚举设计、`?` 传播、C 后端表示、标准库边界、编译器架构、文件读取与数组交换示例。
- [RFC 0001](./0001-error-propagation-and-conversion.md)（`?` 锚点）、[RFC 0002](./0002-match-wildcard-and-nesting.md)（穷尽性）、[RFC 0007](./0007-unqualified-variant-access.md)（变体简化的 prelude 作用域）。
