# Nomo RFC 流程

> 语言 / Language: 中文 | [English](../en/README.md)

本目录收录 Nomo 编程语言的 RFC（Request for Comments，征求意见稿）。RFC 用于对**需要正式决策的语言、编译器、标准库与工具链问题**进行公开讨论与留痕。

RFC 文档应自包含：说明当前设计现状、问题、备选方案、倾向建议与对 v0.1 交付范围的影响。RFC 之间可以互相引用，但不依赖其它说明文档作为索引入口。

---

## 1. 规格基线

当前 v0.1 规格基线见 [`SPEC-v0.1.md`](SPEC-v0.1.md)。它描述 RFC 讨论所依据的语言、标准库、编译器与验收范围。

RFC 的职责是讨论并修改这份规格基线中的待决问题；RFC 被 `Accepted` 后，应同步更新规格基线与实现。

---

## 2. 状态字段定义

每篇 RFC 在元信息中标注 `状态` 字段，取值如下：

| 状态 | 含义 |
| --- | --- |
| `Draft`（待决） | 草案。问题已成形、备选已列出，但尚未做出决策。当前目录下所有 RFC 均为此状态。 |
| `Proposed`（已提案） | 草案已完成、进入正式评审，等待接受或拒绝。 |
| `Accepted`（已接受） | 已被采纳，应据此更新语言规格与实现。 |
| `Rejected`（已拒绝） | 经讨论后不采纳，保留记录与理由。 |
| `Deferred`（已推迟） | 方向认可，但推迟到后续版本（如 v0.2+）再处理。 |

状态流转典型路径：`Draft → Proposed → Accepted / Rejected / Deferred`。

---

## 3. 编号规则

- RFC 文件名格式：`NNNN-短横线英文标题.md`，其中 `NNNN` 为四位零填充编号。
- 编号从 `0001` 顺序递增，一经分配不再复用（即使被 `Rejected`）。
- `0000-template.md` 为模板，不是一篇真正的 RFC。
- 新 RFC 取当前最大编号 +1。

---

## 4. 提交流程

1. 复制 [`0000-template.md`](0000-template.md) 为 `rfcs/NNNN-你的标题.md`，填写所有小节。
2. 在元信息中标注关联主题，并用 Markdown 链接引用相关 RFC。
3. 初始状态设为 `Draft（待决）`。
4. 在本 README 第 6 节「目录索引」表中登记该 RFC（保持表格与实际文件一致）。
5. 进入评审后，按第 2 节的状态流转更新 `状态` 字段。
6. 一篇 RFC 被 `Accepted` 后，应同步发起语言规格与实现的更新。

> 约束：本目录只放 RFC 相关 markdown 文件，不修改其它目录。

---

## 5. 模板

见 [`0000-template.md`](0000-template.md)。模板包含：元信息（编号、标题、状态、作者、创建日期、关联主题、关联 RFC）、摘要、动机、现状与问题、详细设计（语法/语义/C 后端影响/诊断影响）、备选方案、缺点与风险、对 v0.1 范围的影响、未决问题、参考。

---

## 6. 目录索引

| 编号 | 标题 | 状态 | 关联主题 | 一句话结论/倾向 |
| --- | --- | --- | --- | --- |
| [0001](./rfcs/0001-error-propagation-and-conversion.md) | `?` 传播与缺少自动错误转换的体验矛盾 | Draft（待决） | 错误处理、`Result`、`?` 传播、C 后端 | 倾向 v0.1 先提供显式 `std.result.map_err`（让 `?` 可用），把 `From` 风格自动转换留作 v0.2。 |
| [0002](./rfcs/0002-match-wildcard-and-nesting.md) | `match` 缺少 `_` 通配分支与嵌套解构 | Draft（待决） | 模式匹配、穷尽性、嵌套解构 | 倾向 `match` 继续禁用 `_`（守穷尽性），改用 `let else`/`if let` 压平嵌套样板。 |
| [0003](./rfcs/0003-arc-cow-runtime-cost.md) | 值语义 + ARC + COW 的运行时实现成本 | Draft（待决） | 内存模型、`string`、`Array<T>`、运行时 | 倾向「分而治之」：`string` 仅引用计数（不可变免 COW），`Array<T>` 用非原子 RC+COW，纯拷贝作为应急回退。 |
| [0004](./rfcs/0004-mutable-borrow-uniqueness.md) | 可变借用唯一性检查的真实难度 | Draft（待决） | 可变借用、别名检查、逃逸检查 | 倾向把借用存活期限定为「单调用表达式」，做调用点别名 + 逃逸兜底（L1），不引入 lifetime。 |
| [0005](./rfcs/0005-newline-sensitivity-and-dot-resolution.md) | 显著换行分隔与 `.` 命名空间消解 | Draft（待决） | 词法语法、换行规则、名称解析、`.` 消解 | 倾向显著换行 + 显式续行锚点；`.` 统一为后缀点访问，由名称解析按「值/模块/类型」分派。 |
| [0006](./rfcs/0006-option-result-lang-items.md) | `Option`/`Result` 与编译器内建认知的循环依赖 | Draft（待决） | lang item、`Option`、`Result`、标准库边界 | 倾向把 `Option`/`Result` 设为 lang item：定义留在标准库，编译器经 `#[lang]` 标注识别。 |
| [0007](./rfcs/0007-unqualified-variant-access.md) | `Enum.Variant` 是否可简化为非限定 `Variant` | Draft（待决） | 枚举变体、prelude、名称解析、人体工学 | 倾向仅对 prelude 的 `Option`/`Result` 变体（`Some/None/Ok/Err`）允许非限定，其余枚举保持限定。 |

> 注：`0000-template.md` 为模板，不计入上表。
