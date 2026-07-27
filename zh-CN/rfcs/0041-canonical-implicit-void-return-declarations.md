# RFC 0041：Canonical 隐式 `void` 返回声明

> 语言 / Language: 中文 | [English](../../en/rfcs/0041-canonical-implicit-void-return-declarations.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0041 |
| 标题 | Canonical 隐式 `void` 返回声明 |
| 决策状态 | Proposed（已提案） |
| 实现状态 | Not implemented（未实现） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-27 |
| 关联主题 | function declaration、method、suspend function、interface、extern declaration、formatter、doc、LSP、grammar |
| 关联 RFC | [RFC 0010](./0010-constrained-generics-and-static-interface-dispatch.md)、[RFC 0011](./0011-c-ffi-safety-and-link-boundary.md)、[RFC 0012](./0012-shared-semantic-identities-and-verified-rename.md)、[RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md) |

## 1. 摘要

Nomo 把省略返回标注作为返回 `void` 的声明的 canonical 写法。该规则统一适用于普通
function、method、`suspend fn`、interface requirement 与 `extern` block 内的
function。

Parser 为源码兼容继续接受显式 `-> void`。Formatter、scaffolder、`nomo doc`、
compiler/LSP 共享 signature renderer、hover、signature help 与 canonical example
统一省略。本变更只收敛表示与语法，不删除 `void` 类型，也不改变 ABI、effect、
ownership 或 control-flow 语义。

Callable type 必须始终写完整返回类型；`task fn(string) -> void` 不能缩写。
`Result<void, E>`、`Ok(void)` 等 type argument 与 value 保持不变。

## 2. 动机

当前源码在几乎每个入口、helper、method、async operation、interface requirement 与
无结果 FFI call 上重复 `-> void`。当省略返回标注只有一个明确含义时，这些字符不会
增加信息，只会制造视觉噪声。

但删除所有 `-> void` 同样错误：callable type 需要完整 input/output shape，`void`
仍是用于 generic argument 与 value 的真实类型。因此收敛规则必须仅作用于 declaration
context，并由所有 renderer 共享。

如果没有 RFC 级契约，formatter 可能省略标注，而 doc 或 editor 又重新插入，造成
永久 churn 与互相矛盾的示例。

## 3. Canonical 声明语法

### 3.1 源码形式

Canonical declaration 省略 `-> void`：

```nomo
fn log(message: string) {
    io.println(message)
}

impl Buffer {
    pub fn clear(mut self) {
        self.bytes.clear()
    }
}

suspend fn yield_once() {
    task.yield_now()
}

pub interface Close {
    fn close(self)
}

extern "C" {
    fn release(handle: Owned<Handle>)
}
```

返回非 `void` 的 declaration 仍需写 result type：

```nomo
fn length(value: string) -> u64 {
    return value.byte_length()
}
```

兼容形式继续可解析：

```nomo
fn log(message: string) -> void {
    io.println(message)
}
```

两种形式生成同一个 typed declaration。是否写出 `-> void` 不构成 overload 或 semantic
identity 差异。

### 3.2 Context 边界

省略只适用于 declaration return annotation：

- free/exported `fn`；
- method 与 interface implementation；
- `suspend fn`；
- interface function requirement；
- `extern` block 中的 function。

Callable type 与 type/value position 不适用：

```nomo
let worker: task fn(string) -> void = print_message
let completed: Result<void, TaskError> = Ok(void)
```

`task fn(string)` 不是 `task fn(string) -> void` 的同义形式。Callable type 保持语法
完整，让高阶 signature、ABI description 与 diagnostic 始终显示 result。

### 3.3 Parser 与 AST

Declaration return grammar 继续可选。省略时 parser 构造与显式 `-> void` 相同的
semantic `void` result。AST 可以为格式诊断保留 source-range 信息，但 type checking
与 symbol identity 只能观察到一个 result type。

Parser 必须继续接受显式 `-> void`；本 RFC 不设置移除 snapshot。非 `void` result
annotation 仍是必需的。

Tree-sitter 当前已把 return type 建模为可选，不应增加第二套 production。Regression
corpus 必须覆盖每个 declaration position，并证明 callable type 仍要求 arrow/result。

## 4. Canonical 渲染与迁移

以下 producer 必须使用同一 declaration-signature renderer，并省略 semantic `void`
result：

- `nomo fmt`；
- `nomo new` 与仓库 project template；
- `nomo doc`，包括 interface 与 extern item；
- compiler-owned、与 `nomo-lsp` 共享的 signature data；
- LSP hover、signature help、symbol、completion detail 与 code action；
- Playground example 与展示 signature；
- 人工维护的 standard-library、example、benchmark 与 editor fixture。

Formatter 把显式 declaration `-> void` 改成省略形式，并保持幂等。它不得修改：

```nomo
Result<void, E>
Option<Result<void, E>>
Ok(void)
task fn(string) -> void
```

TextMate 与 IntelliJ fallback lexer 必须 tokenize 两种源码形式，不能假定 declaration
一定包含 `->`。Tree-sitter、Zed 与 VS Code corpus/example 使用 canonical form，同时
保留一个显式兼容 fixture。

## 5. 类型检查、控制流与诊断

省略 declaration result 与 `void` 完全相同：

- fallthrough 与现有 `return` 规则不变；
- 所有既有 no-result validation 继续适用；
- interface conformance 把省略与显式形式视为相同；
- extern ABI lowering 继续使用既有 C `void` result；
- `suspend fn` effect checking 与 result 拼写相互独立。

不需要新增 type error。打印 declaration 的 diagnostic 使用 canonical 省略形式。
引用用户源码的 diagnostic 可以保留原 token range，但建议替换与生成 snippet 省略
`-> void`。

Callable type 省略返回类型时，parser 继续产生现有 missing-return-type syntax error，
不能推断为 `void`。

## 6. Backend 与 Runtime 影响

C99 与 WASM backend 接收到的 typed `void` result 不变。Symbol mangling、C
prototype、return lowering、coroutine frame layout、extern ABI 与 runtime
representation 都不改变。

本 RFC 不修改 RFC 0031–0040 的 async 语义。`suspend fn main()` 仍是
suspend/effectful declaration；只收敛其 result annotation。

## 7. 兼容性

本变更对解析与行为保持源码兼容：

- 旧的显式 declaration 继续编译；
- canonical formatting 会产生源码 diff；
- 消费 compiler semantic data 的工具仍看到相同 `void` type；
- callable/type/value use 的含义逐字节保持。

各仓库必须在一次协调变更中迁移，避免 formatter output、doc、LSP、grammar、editor
example、standard library、test 与 Playground 来回震荡。刻意测试显式兼容的 fixture
必须命名，并从 canonical-source gate 排除。

## 8. 备选方案

| 方案 | 结果 | 决议 |
| --- | --- | --- |
| 保持显式 `-> void` 为 canonical | 一致但冗长，不增加 declaration 信息 | 拒绝 |
| 删除 `void` 并在所有位置推断 | 破坏 generic result、value、callable type 与 ABI description | 拒绝 |
| 只允许普通 function 省略 | method、interface、suspend、extern、doc 与 LSP 继续不一致 | 拒绝 |
| 只在 declaration context canonical 省略 | 声明简洁，同时保持 callable 与 generic type 完整 | 已提案 |

## 9. 风险

- 如果 signature rendering 不共享，独立 renderer 会漂移。
- 基于文本的机械替换可能破坏 callable type 或 `Result<void, E>`，必须语法感知。
- Editor fallback lexer 可能错误假设参数之后一定有 arrow。
- 全仓格式迁移会形成很大但语义风险较低的 diff，必须与 async 行为变更分离。

## 10. 验收门禁

受保护 CI 必须证明：

1. 普通、method、`suspend`、interface、extern declaration 的省略/显式 parser parity；
2. formatter 在所有 declaration position 省略且幂等；
3. 保留 `Result<void, E>`、嵌套 type argument、`Ok(void)` 与
   `task fn(string) -> void`；
4. C99 prototype/行为与 WASM 行为不变；
5. `nomo doc`、LSP hover、signature help、symbol、completion detail 与 code action
   使用 canonical 展示；
6. scaffolder、standard library、example、fixture、benchmark probe、`nomo-hello`、
   Playground、VS Code、IntelliJ、Tree-sitter 与 Zed example 均 canonical；
7. grammar/editor regression 覆盖省略声明与显式兼容；
8. 文档门禁拒绝 named compatibility fixture 之外的 declaration `-> void`，但允许
   callable/type/value use。

## 11. 决策与实现证据门禁

本 RFC 首次合并时保持 `Proposed` 与 `Implementation Status: Not implemented`，
不得仅凭文档声明让实现分支假定已经 Accepted。

实现及所有适用受保护 CI 合并后，独立证据 PR 才可把决策改为 `Accepted`、实现改为
`Implemented`。证据 PR 记录 compiler 与生态 merged commit 及精确验证命令，且不得
把内部测试覆盖等同于 production readiness。
