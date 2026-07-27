# Nomo Design Constitution

> Language / 语言: English and 中文

This document is the long-lived decision filter for Nomo language, compiler,
standard library, package tooling, and RFC work.

It is not an implementation-status ledger. RFC decision status, implementation
status, and release readiness remain separate evidence questions.

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
11. Nomo keeps package identity, dependency aliases, and source module roots
    explicit and non-overlapping.
12. Nomo makes Runtime work bounded, owner-aware, and zero-cost when unused
    before claiming concurrency scale.

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
11. Nomo 明确分离 package identity、dependency alias 与源码 module root。
12. Nomo 先证明 Runtime 有界、owner-aware 且不用时零成本，再讨论并发规模。

## Decision Questions

Every new feature proposal should answer:

1. Does this make the language smaller and clearer, or larger and more complex?
2. Does it introduce implicit behavior?
3. Does it weaken the no-null, no-exception, immutable-by-default baseline?
4. Does it add C99 backend or diagnostic complexity?
5. Can it be accepted with examples and tests?
6. Could it prevent the v0.1 loop from shipping?
7. Are resource, ownership, compatibility, and removal boundaries explicit?
8. What executable evidence is required before the decision or release claim
   changes status?

If the answers are unclear, the proposal belongs in `Draft`, `Rejected`, or
`Deferred` rather than direct implementation.
