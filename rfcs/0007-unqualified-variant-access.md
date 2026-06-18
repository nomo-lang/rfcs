# RFC 0007：限定式变体访问是否可简化为非限定形式

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0007 |
| 标题 | `Enum.Variant` 是否可/应简化为非限定的 `Variant` |
| 状态 | Draft（待决） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-06-18 |
| 关联主题 | 枚举变体、prelude、名称解析、`Option`、`Result`、人体工学 |
| 关联 RFC | [RFC 0002](./0002-match-wildcard-and-nesting.md)（match 可读性）、[RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md)（`.` 消解）、[RFC 0006](./0006-option-result-lang-items.md)（lang item） |

---

## 1. 摘要

当前语言设计统一使用限定式变体访问 `EnumName.Variant`（`Option.Some`、`Option.None`、`Result.Ok`、`Result.Err`、`Color.Red`），无论是在构造还是 `match` 模式中。本 RFC 评估是否应允许非限定形式 `Some`、`None`、`Ok`、`Err`。结论先行：**部分必要**——倾向于「仅对 prelude 中的 `Option`/`Result` 等核心 lang item 变体允许非限定形式，用户自定义枚举一律保持限定」。理由是：核心类型变体（`Some/None/Ok/Err`）出现频率极高且名称在生态内事实唯一，非限定化收益大、冲突风险低；而对一般枚举全局放开非限定会引入命名冲突、削弱穷尽性可读性，并与“避免同一语义多种写法”和“不支持通配符导入”相冲突。保持 Draft。

---

## 2. 动机（Motivation）

`Option`/`Result` 是 v0.1 错误处理与可选值的主干，几乎每个函数都会写 `Result.Ok(...)` / `Result.Err(...)` / `Option.Some(...)` / `Option.None`。限定前缀在这些高频处显得冗长，尤其在 `match` 二重嵌套（数组交换示例）里反复出现 `Option.Some`/`Option.None`，可读性与书写成本都受影响。是否简化、简化到什么范围，直接关系到日常人体工学与 AI 生成体验，值得用 RFC 定夺。

---

## 3. 现状

当前规格**全文统一**使用限定形式，构造与模式两处皆然：

- 构造与 `match`：`Color.Red`、`Option.Some(T)` / `Option.None`。
- `Result` 构造与文件读取示例：`Result.Ok(text)`、`Result.Err(AppError.ReadFailed(err.message))`，`match` 中 `Result.Ok(text) => ...`。
- `?` 语义：`?` 语义以 `Result.Ok`/`Result.Err` 描述。
- 数组交换示例：二重 `match` 中四次出现 `Option.Some` / `Option.None`。

导入方面，当前模块系统支持 `import std.result.Result`（导入**类型**），但当前规格**未**展示导入单个变体（如 `import std.result.Ok`），也明确「不支持通配符导入」。因此当前模型下，变体只能经由其类型名限定访问。

---

## 4. 简化方案选项

### 4.1 方案 (a)：允许变体导入（类 Rust `use Enum::*` 的显式版）

- **做法**：允许 `import std.option.{Some, None}` 或 `import std.result.{Ok, Err}`，导入后可写非限定 `Some(x)` / `match` 中 `None => ...`。
- **优点**：来源可追踪（符合 3.1「所有符号来源必须可追踪」），按需引入，冲突可控（同名冲突在导入处即报错）。
- **缺点**：每个文件都要写一行导入；与“不支持通配符导入”需划清界限（这是**具名**导入，不是通配，故不违背）。

### 4.2 方案 (b)：核心类型变体全局预导入（prelude，倾向）

- **做法**：编译器为每个包隐式预导入一组 prelude 符号，包含 `Option` 的 `Some`/`None` 与 `Result` 的 `Ok`/`Err`（依赖 [RFC 0006](./0006-option-result-lang-items.md) 把它们设为 lang item）。用户无需导入即可写：

```rust
fn read_config(path: string) -> Result<string, AppError> {
    match fs.read_to_string(path) {
        Ok(text) => Ok(text)
        Err(err) => Err(AppError.ReadFailed(err.message))
    }
}
```

- **优点**：消除最高频的前缀冗余；名称（`Some/None/Ok/Err`）在生态内事实唯一，冲突概率极低；与 [RFC 0002](./0002-match-wildcard-and-nesting.md) 的嵌套减负叠加效果好。
- **缺点**：引入「隐式可见符号」，与「来源可追踪」有一定张力（但 prelude 是固定、可文档化的小集合，类似语言内建，可接受）；需要明确 prelude 清单与覆盖规则（用户若自定义同名 `Ok` 如何处理）。

### 4.3 方案 (c)：`match` 上下文按被匹配值类型推断变体（省略限定）

- **做法**：在 `match x { ... }` 中，已知 `x: Option<i32>`，则分支模式可省略限定写 `Some(n)` / `None`，编译器按 `x` 的类型解析变体；构造处仍需限定或类型已知时推断。
- **优点**：仅在类型确定的上下文放开，冲突几乎不存在；穷尽性检查不受影响（仍按该枚举全部变体校验）。
- **缺点**：构造处（`return Ok(...)`）不一定有足够类型上下文，简化不彻底；规则「何时能省略」对用户与 AI 不如 prelude 直观；名称解析需引入「期望类型驱动的变体查找」。

### 4.4 方案 (d)：维持现状（全限定）

- **做法**：不变，全部 `Enum.Variant`。
- **优点**：零歧义、来源最显式、与显式来源原则最契合、名称解析最简单（[RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md) 的 `.` 规则足够）。
- **缺点**：高频前缀冗余，11.4 这类嵌套尤其啰嗦。

---

## 5. 必要性评估

### 5.1 是否必要：结论

**部分必要**。对 `Option`/`Result` 的变体（`Some/None/Ok/Err`）非限定化是**有较强收益且低风险**的，值得做；对**用户自定义枚举**的全局非限定化**不必要**，应保持限定或仅经显式具名导入开启。

### 5.2 权衡分析

- **命名冲突风险**：多个枚举可能有同名变体（如多个枚举都叫 `Red`/`Pending`）。全局非限定会让裸 `Red` 产生歧义，需要消解规则或报冲突。`Some/None/Ok/Err` 则在实践中近乎专属，冲突风险极低——这是把简化**限定在核心类型**的关键理由。
- **穷尽性与可读性**：穷尽性检查基于「被匹配值的类型」枚举其全部变体，与变体是否限定**无关**，因此非限定不会削弱穷尽性（[RFC 0002](./0002-match-wildcard-and-nesting.md)）。可读性上，限定形式让「这是哪个枚举的分支」一目了然；但对 `Ok/Err/Some/None` 这种全民皆知的类型，前缀反而是噪音。结论：核心类型去前缀提升可读性，自定义枚举保留前缀维持清晰。
- **对 parser / 名称解析的影响（编译器架构）**：
  - 维持现状（d）：名称解析按 [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md) 的 `.` 规则即可，最简单。
  - prelude（b）/导入（a）：名称解析需支持「裸标识符 → 变体」的查找路径，并定义其与变量/函数名的优先级（建议局部绑定 > prelude 变体，避免遮蔽用户变量）。
  - 类型推断（c）：需引入期望类型驱动的变体解析，最复杂。
- **AI 友好性（避免同一语义多种写法）**：这是**最大的反对理由**。若同时允许 `Result.Ok` 与 `Ok`，就出现「同一语义两种写法」，违背 2.2。缓解办法：**只保留一种推荐写法**——对核心类型统一推荐非限定（`Ok`/`Err`/`Some`/`None`），并由格式化器/lint 收敛；对自定义枚举统一限定。即「分域单写法」，而非「全域双写法」。
- **与“不支持通配符导入”的一致性**：方案 (a) 是**具名**导入，不是 `*` 通配，不违背 3.1；方案 (b) prelude 是语言内建的固定集合，类似关键字级可见，也不属于通配符导入。两者均与 3.1 兼容；真正要避免的是「`import std.option.*` 式通配」。

---

## 6. 详细设计（倾向方案：prelude-only）

- **语法**：`Some`/`None`/`Ok`/`Err` 可非限定使用于构造与 `match` 模式；其余枚举变体保持 `Enum.Variant`。
- **语义/名称解析（编译器架构）**：
  - 预导入集合（prelude）= `Result.{Ok, Err}` + `Option.{Some, None}`，依赖 [RFC 0006](./0006-option-result-lang-items.md) 的 lang item 识别。
  - 解析裸标识符顺序：局部绑定/参数 > 当前包符号 > prelude 变体。若用户定义了同名符号，**遮蔽** prelude（并发 lint 提示），保证不破坏现有代码。
  - 穷尽性、codegen 与限定形式完全等价（同一变体）。
- **诊断**：
  - `N0340` 裸变体名歧义（仅当未来扩大 prelude 导致冲突时）。
  - lint：检测到对核心类型使用限定形式（`Result.Ok`）时，建议改为非限定（统一风格，落实「分域单写法」）。
- **C 后端**：无影响，消解后与限定形式生成相同代码。
- **与 (a) 的关系**：可同时保留方案 (a) 的具名变体导入作为「自定义枚举想去前缀」的显式出口，但 v0.1 可先只做 prelude，(a) 留作 v0.2。

---

## 7. 对 v0.1 范围的影响

- **建议 v0.1 落地**：方案 (b) 的最小形态——仅 `Option`/`Result` 四个变体 prelude 非限定，遮蔽规则 + 风格 lint。依赖 [RFC 0006](./0006-option-result-lang-items.md) 的 lang item 先行。
- **建议当前规格处理**：示例可逐步改用非限定核心变体（如文件读取与数组交换示例），但需与「分域单写法」原则一致地全局统一，避免新旧混写。
- **推迟**：方案 (a) 具名变体导入、方案 (c) 类型推断式省略，留作 v0.2。
- **验收影响**：验收测试矩阵名称解析测试需覆盖「裸 `Ok`/`None` 正确解析」「用户同名符号遮蔽 prelude」「自定义枚举裸变体仍报未解析」。

---

## 8. 倾向性建议（保持 Draft，不拍板）

倾向：**仅对 prelude 中的 `Option`/`Result` 变体允许非限定形式（`Some`/`None`/`Ok`/`Err`），其余枚举保持限定**，并通过格式化器/lint 落实「每个域内只有一种推荐写法」，从而既拿到高频去前缀的收益，又不违背 2.2 与 3.1。保持 Draft。

---

## 9. 未决问题

- prelude 的精确清单是否仅限 `Option`/`Result`，还是未来纳入更多核心类型。
- 用户同名符号遮蔽 prelude 时，是 warning 还是必须显式标注。
- 是否在 v0.1 同时提供方案 (a) 的具名变体导入，还是严格只做 prelude。
- 当前示例是否在本 RFC 接受后统一改写为非限定核心变体。

---

## 10. 参考

- 当前 AI 友好原则、模块导入规则、枚举设计、`Result` 语义、名称解析、文件读取与数组交换示例。
- [RFC 0002](./0002-match-wildcard-and-nesting.md)（match 嵌套可读性）、[RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md)（`.` 消解与裸标识符解析）、[RFC 0006](./0006-option-result-lang-items.md)（lang item 作为 prelude 基础）。
