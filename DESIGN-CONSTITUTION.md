# Nomo Design Constitution

> Language / 语言: English and 中文

This document is the long-lived decision filter for Nomo language, compiler,
standard library, package tooling, and RFC work.

## English

1. Nomo is small before it is powerful.
2. Nomo favors explicitness over magic.
3. Nomo has no null and no exceptions.
4. Nomo uses `Result` for recoverable errors and `panic` for defects.
5. Nomo is immutable by default.
6. Nomo compiles to inspectable native code.
7. Nomo prioritizes diagnostics, tooling, and readable generated output.
8. Nomo avoids exposing complex lifetime machinery in early versions.
9. Nomo grows through RFCs, examples, and tests.
10. Nomo rejects features that make the v0.1 loop impossible to finish.

## 中文

1. Nomo 先小而完整，再强大。
2. Nomo 选择显式，不选择魔法。
3. Nomo 没有 null，也没有异常。
4. Nomo 用 `Result` 表达可恢复错误，用 `panic` 表达程序缺陷。
5. Nomo 默认不可变。
6. Nomo 编译为可检查的原生代码。
7. Nomo 优先保证诊断、工具链和生成代码可读性。
8. Nomo 不在早期暴露复杂 lifetime 机制。
9. Nomo 通过 RFC、示例和测试演进。
10. Nomo 拒绝会拖垮 v0.1 闭环的功能。

## Decision Questions

Every new feature proposal should answer:

1. Does this make the language smaller and clearer, or larger and more complex?
2. Does it introduce implicit behavior?
3. Does it weaken the no-null, no-exception, immutable-by-default baseline?
4. Does it add C99 backend or diagnostic complexity?
5. Can it be accepted with examples and tests?
6. Could it prevent the v0.1 loop from shipping?

If the answers are unclear, the proposal belongs in `Draft`, `Rejected`, or
`Deferred` rather than direct implementation.
