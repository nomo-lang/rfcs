# RFC 0012：共享语义身份与类型检查后的 Rename

> 语言 / Language: 中文 | [English](../../en/rfcs/0012-shared-semantic-identities-and-verified-rename.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0012 |
| 标题 | 共享语义身份与类型检查后的 Rename |
| 状态 | Accepted（已接受） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 已落地：compiler semantic API、声明感知 reference、receiver/member owner、workspace reference、dependency definition、rename edit 后重检均有 compiler/LSP 测试 |
| 关联主题 | semantic API、LSP、definition、references、rename、receiver type |
| 关联 RFC | [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md)、[RFC 0010](./0010-constrained-generics-and-static-interface-dispatch.md) |

---

## 1. 摘要

编辑器不得重新实现 Nomo 名称解析。definition、reference、hover 和 rename 统一使用 compiler 的 semantic API，以声明源码、range、symbol kind 与 member owner 标识符号。rename 先在内存中应用 edits，再对结果 module graph 类型检查，通过后才返回。

## 2. 动机

纯文本同名匹配会错误跨越 shadow、receiver type、interface owner 和 package 边界。若 VS Code、Zed、IntelliJ 与 LSP 各自猜测，工具行为必然与编译器分叉。

## 3. 声明身份

- local parameter、`let`、pattern 和 `for` binding 按词法作用域绑定。
- field、struct literal label 与 method call 按 receiver 的已检查 nominal type 解析。
- 不同类型的同名 member 有不同 owner；受约束泛型的方法归属声明 interface。
- dependency public symbol 可以成为 definition target，但 private symbol不可见。

## 4. Reference 与 Rename

- project/workspace reference 查询以 declaration identity 为键，而非仅以文本为键。
- open-buffer overlay 参与当前查询，未保存源码不应退回陈旧磁盘内容。
- rename 只修改当前可编辑 package/module graph；dependency source 不被批量改写。
- 若原程序可通过检查，工具必须对 edits 后的 overlay graph 再次检查；失败则拒绝 rename。

## 5. 备选方案

| 方案 | 问题 | 决议 |
| --- | --- | --- |
| client 端正则/词法匹配 | shadow 与 member owner 错误 | 拒绝 |
| LSP 自建语义模型 | 与 compiler 重复且易漂移 | 拒绝 |
| compiler 共享 semantic API | 单一事实源，可复用类型信息 | 接受 |

## 6. 缺点与风险

- semantic API 成为跨 crate/仓库兼容面。
- workspace 查询成本需要缓存和增量化。
- edits 后全图重检比文本 rename 更昂贵，但优先保证正确性。

## 7. 对 v0.1 范围的影响

LSP completion、hover、symbols、definition、references、rename、code actions、semantic tokens 与 inlay hints应尽量复用 compiler facts。E1300-E1399 保留给 semantic/LSP 诊断。

## 8. 决议

接受 compiler-owned declaration identity、receiver-aware member owner、workspace semantic query 和类型检查后的 rename。

## 9. 后续问题

- 增量 semantic graph 与跨 workspace cache。
- dependency rename 的显式 opt-in 协议。
- 跨 package move/refactor 与 source map 稳定身份。

## 10. 参考

- `nomo_lsp_bridge` semantic types、compiler `semantic` API、receiver-aware navigation 与 workspace reference tests。
- [RFC 0010](./0010-constrained-generics-and-static-interface-dispatch.md)。
