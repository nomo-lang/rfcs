# RFC 0002：`match` 不支持 `_` 通配分支带来的嵌套啰嗦

> 语言 / Language: 中文 | [English](../../en/rfcs/0002-match-wildcard-and-nesting.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0002 |
| 标题 | `match` 缺少 `_` 通配分支与嵌套解构的人体工学 |
| 状态 | Draft（待决） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-06-18 |
| 关联主题 | 模式匹配、穷尽性、嵌套解构、`Option` |
| 关联 RFC | [RFC 0001](./0001-error-propagation-and-conversion.md)（`?` 传播）、[RFC 0007](./0007-unqualified-variant-access.md)（变体访问简化） |

---

## 1. 摘要

当前模式匹配规格 为「强制穷尽性 + 让诊断覆盖所有缺失分支」而禁用 `_` 通配分支。这在简单枚举上是合理的，但对嵌套 `Option`/`Result`（见数组交换示例的二重 `match`）会产生大量样板，每个 `None`/`Err` 都要重复写出。本 RFC 给出四类缓解方案（维持禁用、有条件允许 `_`、引入 `if let`/`let else`、引入 Option 解构的 `?` 风格），倾向于「v0.1 维持 `_` 禁用以保住穷尽性诊断，同时引入 `if let` / `let else` 作为嵌套场景的减负工具」，保持 Draft。

---

## 2. 动机（Motivation）

穷尽性是 Nomo 的安全卖点：所有分支必须显式覆盖，诊断逐一报告缺失分支。但「禁用 `_`」与「值经常嵌套」叠加时，会逼出深层嵌套的金字塔代码。数组交换示例的 `swap` 仅仅是「取两个元素、都存在才交换」，却写了二重 `match` 和两处重复的 `panic("index out of bounds")`。这类代码：

- 难写、难读、易错（两个 `None` 分支必须各写一遍）。
- AI 生成时容易漏分支或写错嵌套层级。
- 与 2.2「降低生成和修复成本」的目标相悖。

---

## 3. 现状与问题

### 3.1 当前规格现状

当前模式匹配规格：

> `match` 必须穷尽所有分支。v0.1 暂不支持 `_` 通配分支，优先让诊断覆盖所有缺失分支。

数组交换示例 体现了嵌套代价：

```rust
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

### 3.2 问题分析

- **重复**：`Option.None => panic(...)` 出现两次；逻辑上「任一越界即 panic」，却被迫分散到两层。
- **嵌套深度随被匹配值数量线性增长**：两个 `Option` 已是二层，三个值就是三层。
- **`_` 的双刃性**：`_` 能消除啰嗦，但也会吞掉「新增变体后未处理」的诊断——这正是 3.8 想避免的。直接放开 `_` 会牺牲穷尽性红利。

核心张力：**穷尽性诊断（要全列）** 与 **嵌套人体工学（想省略）** 难以兼得，需要在「省略机制」与「穷尽性保护」之间找平衡点。

---

## 4. 详细设计

### 4.1 方案 A：维持禁用 `_`（现状）

- **语义**：不变。
- **优点**：穷尽性诊断最强，语义最简单。
- **缺点**：嵌套样板无解。

### 4.2 方案 B：有条件允许 `_`

- **语法**：允许 `_ => ...`，但仅当其覆盖的剩余变体数 ≥ 2 时合法；若 `_` 实际只剩 1 个变体可覆盖，编译器提示「用具名变体更清晰」。
- **语义**：`_` 之后不得再有分支；引入「`_` 掩盖了新增变体」的 lint（warning 级），在枚举新增变体时仍能提醒。
- **诊断**：新增名称解析/类型检查侧的 warning，例如 `N0410`（`_` 掩盖了可枚举的剩余变体）。
- **缺点**：放开后 AI/用户会倾向「一律 `_`」，逐步侵蚀穷尽性文化。

### 4.3 方案 C：引入 `if let` / `let else`（倾向）

- **语法**：

```rust
fn swap(mut items: Array<i32>, i: u64, j: u64) {
    let Option.Some(av) = items.get(i) else { panic("index out of bounds") }
    let Option.Some(bv) = items.get(j) else { panic("index out of bounds") }
    items.set(i, bv)
    items.set(j, av)
}
```

- **语义**：`let PATTERN = expr else { ... }`，匹配失败走 `else`（`else` 必须发散：`panic`/`return`/`break`）。`if let PATTERN = expr { ... }` 用于「只关心一个分支」。
- **C 后端**：展开为单臂判断 + 失败分支，等价于 `match` 的子集，无新增运行时。
- **诊断**：保持 `match` 的穷尽性不变（`match` 仍禁用 `_`）；`if let`/`let else` 本就语义上是「非穷尽提取」，不影响 `match` 的全覆盖红利。
- **优点**：在不放开 `_` 的前提下，把「单分支提取 + 早退」这一最常见的嵌套来源消掉，且发散式 `else` 不会悄悄吞掉变体。

### 4.4 方案 D：Option 解构的 `?` 风格

- **语法**：在返回 `Option` 的函数里允许 `let av = items.get(i)?`，`None` 时早退 `None`。
- **语义**：与 [RFC 0001](./0001-error-propagation-and-conversion.md) 的 `?` 同源，但作用于 `Option`，要求当前函数返回 `Option`。
- **缺点**：`swap` 返回 `void`/会 `panic`，不返回 `Option`，故对该例不直接适用；适用面比 C 窄。

---

## 5. 备选方案（Alternatives）

| 方案 | 做法 | 优点 | 缺点 |
| --- | --- | --- | --- |
| A 维持禁用 | 不变 | 穷尽性最强、最简单 | 嵌套样板无解 |
| B 有条件 `_` | 受限通配 + lint | 直接减负 | 侵蚀穷尽性文化、需额外 lint |
| C `if let`/`let else`（倾向） | 单分支提取 + 发散 else | 保住 `match` 穷尽性、消除主要嵌套源 | 新增语法表面积 |
| D Option `?` | 对 `Option` 早退 | 与 `?` 一致 | 仅适用于返回 `Option` 的函数 |

---

## 6. 缺点与风险

- 方案 C 增加语法点，需在关键字/语法规则中明确 `let ... else` 的解析（`else` 块必须发散），并与 `if` 表达式语义区分。
- 若同时引入 C 和 D，需协调与 [RFC 0001](./0001-error-propagation-and-conversion.md) `?` 的一致性，避免出现三种「早退」写法相互重叠，违反 2.2。
- 方案 B 的「剩余变体计数」依赖名称解析阶段已知枚举全部变体，实现上与穷尽性检查共用同一信息，成本可控但语义边界需写清。

---

## 7. 对 v0.1 范围的影响

- **建议 v0.1 落地**：方案 C 的 `let else`（发散式），优先解决数组交换这类「提取或 panic」；`if let` 可同批或紧随其后。
- **保持不变**：`match` 继续禁用 `_`（方案 A），守住穷尽性诊断。
- **推迟**：方案 B（受限 `_`）与方案 D（Option `?`）留作 v0.2 讨论，避免一次引入过多省略机制。
- **验收影响**：验收测试矩阵 Parser/Type checker 测试需新增 `let else` 的成功/失败样例（`else` 不发散应报错）。

---

## 8. 倾向性建议（保持 Draft，不拍板）

倾向 **A + C 组合**：`match` 保持禁用 `_`（守穷尽性），并引入 `let else`（必要时再加 `if let`）来消化嵌套 `Option`/`Result` 的主要样板来源。这样既不牺牲诊断红利，又把数组交换示例的二重 `match` 压平为线性早退。保持 Draft。

---

## 9. 未决问题

- `let else` 的 `else` 块发散性如何在类型检查中判定（是否复用「永不返回」分析）？
- 是否在 v0.1 同时提供 `if let`，还是仅 `let else`？
- 若将来仍要引入 `_`，是「全局放开」还是「仅顶层 `match`」？

---

## 10. 参考

- 当前模式匹配规格 枚举与模式匹配、6.2 `match`、数组交换示例。
- [RFC 0001](./0001-error-propagation-and-conversion.md)（`?` 传播与早退一致性）、[RFC 0007](./0007-unqualified-variant-access.md)（变体访问简化对 `match` 可读性的影响）。
