# RFC 0039：Loop-Carried Coroutine State 与 Suspension-Safe Mutation

> 语言 / Language: 中文 | [English](../../en/rfcs/0039-loop-carried-coroutine-state-and-suspension-safe-mutation.md)

## 元数据

| 字段 | 值 |
| --- | --- |
| 编号 | 0039 |
| 标题 | Loop-carried coroutine state 与 suspension-safe mutation |
| 状态 | Proposed（已提案） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-27 |
| 主题 | suspend function、loop、mutable local、liveness、ARC、C99、MCP |
| 相关 RFC | [RFC 0003](./0003-arc-cow-runtime-cost.md)、[RFC 0004](./0004-mutable-borrow-uniqueness.md)、[RFC 0028](./0028-bounded-json-rpc-and-newline-stdio-framing.md)、[RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md)、[RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md)、[RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md)、[RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md)、[RFC 0038](./0038-owner-affine-async-process-pipes-and-blocking-migration.md) |

## 1. 摘要

Nomo 在 RFC 0031 stackless-coroutine model 上增加一个受限的 v0.1 control-flow
切片：loop body 可以挂起，task-local owned mutable local 可以跨 suspension 与
loop backedge 携带状态；mutable borrow、guard、raw/FFI view 与 executor-affine
borrowed resource 仍不得跨挂起点。

C99 backend 会把 loop lowering 为现有 coroutine frame 中显式的 condition、
suspension、resume 与 backedge state。Assignment 继续使用普通 ARC/COW
move/drop 规则；cancellation 或 failure 会恰好一次 drop 当前已初始化的
loop-carried value。这样可以实现真实的增量 MCP stdio loop，而不引入 `await`、
普通值的 atomic RC、递归 coroutine frame 或 transport-specific runtime
intrinsic。

本 RFC 为 `Proposed`。只有 compiler、C99/browser path、diagnostic、跨平台 async
MCP fixture、lifecycle counter 与 RFC 0034 cost gate 全部通过后才能转为
`Accepted`。

## 2. 动机

RFC 0028 与 RFC 0038 已提供 Nomo-native MCP client 的两个可复用组件：bounded
JSON-RPC newline framing 与 owner-affine async process pipe。真实 client 仍无法
组合二者，因为 process output 可以任意分片、交错；decoder 与 completion flag
必须跨未知数量的 `process.next_event` 挂起点存活：

```nomo
suspend fn exchange(
    child: ProcessChild,
    decoder: JsonRpcDecoder
) -> Result<JsonRpcDecoder, McpError> {
    let mut state: JsonRpcDecoder = decoder
    let mut received: bool = false
    for !received {
        let next: Result<ProcessEvent, ProcessControlError> =
            process.next_event(child, 65536, 5000)
        // Resume 后的同步 match 更新 state 与 received。
    }
    return Ok(state)
}
```

当前实现会报告 E0876，因为第一版 lowering 只接受 immutable top-level local
与顺序挂起点。固定展开若干次 read 并不正确：pipe chunking 与 stderr
interleaving 取决于 platform 与 scheduling。保留 blocking MCP 示例会占住 async
worker；把 loop 藏进 MCP-specific C intrinsic 会降低 JSON-RPC、process
cancellation 与 error handling 的可组合性。

因此在 P2-PROC-E 能诚实声明 native async MCP loop 前，语言需要一个小型、经过
审计的 CFG/state-machine 扩展。

## 3. 现状与问题

RFC 0031 已要求 stackless C99 frame、liveness-derived storage、owner affinity 与
exactly-once cleanup。它明确允许 immutable owned value 跨 suspension，并禁止
mutable borrow 与 guard；但尚未定义 loop-carried mutable owned local，或 loop
内 suspension 的首个实现形态。

当前 compiler 会保守拒绝：

- suspend function 中的全部 mutable local；
- loop 或 branch 内的 suspension；
- recursive suspension；
- suspension 周围的大部分 `?`、`return`、`break`、`continue`、`defer` 与
  panic 形态。

这虽然安全，却无法支持 incremental stream、SSE、MCP stdio、长期 Agent event
loop 与 bounded retry loop。缺失的决策不是 mutable borrow 能否跨 suspension
——不能——而是 owned task-local value 如何跨 loop backedge 存储、覆盖与 drop。

## 4. 详细设计

### 4.1 源码语法与 v0.1 形态

不增加新语法；继续使用 `suspend fn` 与现有 `for condition { ... }`。

第一版可接受形态为：

- non-suspending Boolean loop condition；
- suspend function 中一个 non-nested loop；
- loop body 含一个或多个 direct suspend call，每个 call 是 standalone void
  call 或 immutable `let`-bound result；
- resume result 后允许同步 statement、`if` 与 `match`；
- loop 外声明的 task-local mutable local 可在 loop body 中 assignment；
- 正常 fallthrough 到 backedge，并在 loop 后正常 function return。

第一版继续拒绝 loop condition、initializer 或 update 中的 suspension、nested
suspending loop、conditional arm 内 suspension，以及会跨 loop suspension 的
`break`、`continue`、early `return`、`?`、`defer` 或 panic path。这些属于后续
CFG 切片，不能静默近似接受。

### 4.2 Suspension-safe mutable local

Mutable local 只有在满足以下全部条件时才能跨 suspension 存活：

1. local 拥有 value，而不是 borrow、guard、pointer、runtime buffer view 或
   borrowed FFI value；
2. 类型具有生成式 frame move/drop；
3. suspension 时没有由它派生的 borrow 或 guard 仍存活；
4. 除非经过 RFC 0033 显式 transfer boundary 消费，否则始终固定在同一 owner
   executor；
5. 每次 assignment 都在下一个 suspension 前完成。

这不会让 value 变成 `Send`、`Sync`、shared、locked 或 atomic RC。Frame 保持
task-local；`Array<T>`、有序 `Map<K,V>`、string 与其它 ARC/COW value 继续使用
普通 non-atomic backing。只有真实 mutation 观察到 alias 时才执行普通 COW
detach。

Mutable parameter 不属于第一版。Caller 可以把 owned value move 到 immutable
parameter，再由它初始化 mutable task-local frame slot。

### 4.3 求值与 assignment

Loop condition 在进入时以及每次 body 完成后重新求值。Suspend call 若 ready，
在同一 poll 中继续；若 pending，则记录 resume state 并返回 `PENDING`。

Managed loop-carried local 的 assignment 是一个事务：

1. 把 RHS 求值到 owned temporary storage；
2. 求值成功后，把新 value move/retain 到 frame slot；
3. 恰好一次 release 旧的 initialized value；
4. 更新 slot initialization/move bit；
5. 继续下一 statement 或 loop backedge。

若求值终止 task，旧 frame value 仍是唯一需要 drop 的 initialized value；不会
观察到 half-assigned state。

### 4.4 C99 state-machine lowering

每个支持的 loop 生成类似以下 private label：

```c
NOMO_STATE_LOOP_CONDITION
NOMO_STATE_LOOP_SUSPEND_0
NOMO_STATE_LOOP_RESUME_0
NOMO_STATE_LOOP_BACKEDGE
NOMO_STATE_AFTER_LOOP
```

具体编号属于 private ABI。Poll function 使用 switch 或等价 C99 control flow；
backedge 跳回 condition state，不递归调用 poll function，也不分配新 frame。

Frame layout 包含：

- 跨可能 suspension 存活的 mutable loop-carried local；
- 同样存活的 immutable parameter/result；
- 当前可达 suspension site 所需的 child frame 或 reactor registration；
- exactly-once cleanup 所需的 initialization/move bit。

Compiler 必须在 loop CFG 上做 liveness。为了先建立正确性，preview 可保守保留
更多 frame-safe local；但在参与 RFC 0034 性能声明前，稳定 frame 只能保留跨
可能 suspension 存活的 value。

### 4.5 Cleanup、cancellation 与 error

所有 exit 都汇入 RFC 0031 frame-drop plan。Cancellation、timeout、runtime
failure 或 panic 时：

- 先 cancel/drop active child operation；
- 每个 initialized loop-carried slot 恰好 release 一次；
- 被覆盖的旧 value 不会再次 release；
- owner-affine handle 仅由已规定的 cleanup owner close；
- termination 后不再执行 backedge 或同步 tail statement。

Suspended operation 返回普通 `Result.Err` 时，这是 ready value。Loop 中同步
代码可以存储它、设置 completion flag 或完成正常 iteration。围绕 loop
suspension 的通用 early `?` propagation 不属于第一版。

### 4.6 Diagnostic

现有 code 继续作为 compatibility boundary：

- E0873 报告跨 loop suspension 存活的 mutable borrow、guard、raw/FFI view 或
  borrowed runtime value；
- E0876 报告不支持的 suspending-loop shape，并指出已支持的
  direct-call/fallthrough 形态；
- 现有 Local/!Send diagnostic 继续拒绝 owner escape 或 publication。

当 span 可用时，diagnostic 必须同时指向 local/borrow origin 与 suspension 或
backedge；不得打印 process argument、JSON-RPC payload、token 或 child output。

### 4.7 标准库与 browser 影响

不增加 transport-specific intrinsic。`std.process` 与 `std.jsonrpc` 保持独立，
Nomo 示例通过 public API 组合二者。

Browser interpreter 在现有 fuel limit 下执行纯 supported loop。Browser 调用
`process.next_event` 仍在 operand evaluation 前由 process capability boundary
拒绝；本 RFC 不创建 browser subprocess capability。

## 5. 验收门禁

Implementation PR 必须提供：

1. zero、one 与 many iteration 的 compiler/C99 正向测试，覆盖两个 suspension
   site、mutable scalar 与 managed ARC/COW state；
2. mutable borrow、guard、FFI pointer/view 与 borrowed runtime buffer 跨 loop
   suspension 的 E0873 负向测试；
3. nested suspending loop、suspending condition、branch-nested suspension 与
   unsupported early exit 的 E0876 负向测试；
4. 显式 backedge、无 recursive poll call、frame slot 仅保留 live value 的
   generated-C 检查；
5. overwrite、ready completion、pending resume、error-valued completion、每个
   suspension site cancellation、timeout 与 panic cleanup 的 retain/release
   counter；
6. Nomo `mcp_stdio_async` 示例，通过 local fixture 处理 fragmented/coalesced
   JSON-RPC message 与 interleaved stderr；
7. 同一示例在 Linux epoll/`pidfd`、macOS kqueue/`EVFILT_PROC`、Windows IOCP
   上执行，并且 live frame/process/reactor/IOCP state 归零；
8. browser pure-loop parity 与 process-capability rejection；
9. RFC 0034 证据：未使用 async 时无新增成本、ready iteration 不分配/入队、
   pending loop 只使用既有 frame 与 operation registration。

适用门禁全部通过前，本 RFC 保持 `Proposed`。

## 6. 备选方案

| 方案 | 做法 | 优点 | 缺点 |
| --- | --- | --- | --- |
| Loop-carried frame state（提议） | 把 owned mutable local 与 loop backedge lowering 到既有 stackless frame | direct Nomo code，可复用于 MCP/SSE/retry，无额外 thread 或递归 frame | 需要 CFG liveness 与严谨 drop plan |
| Recursive suspend driver | 通过 recursive suspend function 传递 decoder state | source parameter 可保持 immutable | 需要动态大小/嵌套 frame，与当前 acyclic call gate 冲突 |
| MCP-specific runtime intrinsic | 在 C/runtime 中实现整个 exchange loop | compiler 改动更小 | transport-specific，隐藏 cancellation/framing，降低复用并扩大 trusted runtime |
| 保持 blocking 或固定展开 | 继续用 blocking process API，或假设固定 event 数 | 无 compiler 工作 | 占用 async worker，或在真实 pipe fragmentation 下不正确 |

本问题不需要增加 `await`、async generator 或通用 stream protocol；这些会不必要
地扩大 v0.1 surface。

## 7. 缺点与风险

Loop CFG liveness 与 exactly-once drop 明显比顺序 state numbering 更复杂。
Managed assignment 可能暴露 double release、leak 或 stale-slot bug。若 Nomo
loop 或 fixture 假设固定 chunk 数，platform event order 会造成 flaky test。

缓解措施是刻意收窄第一版形态、使用确定性 local fixture、覆盖每个 suspension
site 的 cancellation、检查 generated C、在支持时运行 sanitizer，并验证精确
runtime counter。未支持 control flow 继续以 E0876 失败。

## 8. 对 v0.1 的影响

这是 P2-PROC-E async MCP gate 与真实 Nomo-native Agent event loop 的必要能力。
v0.1 最小范围为第 4.1 节 bounded loop 形态、task-local owned mutation，以及
第 5 节完整验收矩阵。

Nested arbitrary CFG suspension、mutable parameter、recursive suspend function、
async generator/iterator、loop condition 内 suspension 与通用 early-exit
lowering 可留给后续 RFC 或 v0.2。

## 9. 提议决定

在现有 direct-style stackless coroutine model 中采用 loop-carried task-local
owned state；继续严格禁止 borrow 与 guard 跨 suspension。Loop lowering 为
non-recursive C99 CFG state，复用普通 ARC/COW storage，并以精确 cleanup 与
cost 证据作为扩大范围的门禁。

## 10. 未决问题

- 下一 CFG 切片应优先支持 `?` propagation、`break`/`continue`，还是
  branch-nested suspension。
- 稳定 liveness 是否需要 diagnostic/explain mode，供开发者查看 frame size。
- 未来 async iterator 应复用此 loop machinery，还是采用独立 protocol。

## 11. 参考

- [RFC 0031：直写式挂起函数与结构化并发](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0034：异步 runtime 验收与基准门禁](./0034-async-runtime-acceptance-and-benchmark-gates.md)
- [RFC 0038：Owner-affine async process pipe 与 blocking migration](./0038-owner-affine-async-process-pipes-and-blocking-migration.md)
