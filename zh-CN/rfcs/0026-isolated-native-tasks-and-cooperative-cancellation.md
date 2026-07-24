# RFC 0026：隔离式 Native Task 与协作取消

> 语言 / Language: 中文 | [English](../../en/rfcs/0026-isolated-native-tasks-and-cooperative-cancellation.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0026 |
| 标题 | 隔离式 native task 与协作取消 |
| 状态 | Proposed（已提案） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-25 |
| 关联主题 | concurrency、task、isolation、cancellation、C99 backend、Agent |
| 关联 RFC | [RFC 0003](./0003-arc-cow-runtime-cost.md)、[RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)、[RFC 0019](./0019-typed-ffi-handles-callbacks-and-bindings.md)、[RFC 0022](./0022-structured-http-client-and-host-runtime.md)、[RFC 0023](./0023-pull-based-http-streaming-and-sse.md)、[RFC 0024](./0024-controlled-child-processes-and-stdio.md)、[RFC 0025](./0025-structured-json-values-and-construction.md) |

---

## 1. 摘要

Nomo v0.1 应增加一个刻意受限的 native task model，使独立 Agent tool 能并行
执行，但不引入通用 function value、closure、共享可变内存或 `async`/`await`。

每个 task 在一个 native OS thread 上执行一个不捕获环境的顶层 `task fn`。Parent
通过 deep copy 传入一段受限 string input；worker 返回一段受限 string result，
result 也会先复制再对 parent 可见。两端创建的全部 Nomo managed value 都只由创建
它的 thread 拥有并维护引用计数。因此，现有非原子 string/array reference count
不会跨 thread boundary。

首个 API 提供受限 task creation、timed join、cooperative cancellation、
cancellation observation 与显式 close。Compiler-owned task-safety analysis 会拒绝
transitive call graph 中包含 FFI、unsafe code、thread-confined host handle 或再次
spawn task 的 worker。Native non-streaming `std.http` request 属于首批 task-safe
能力，使 Agent 可以并行执行相互独立的 network tool。

## 2. 目标与非目标

### 2.1 目标

1. 在 Linux、macOS 与 Windows 上并行执行独立 Nomo computation。
2. 支持 native CLI Agent 并行执行 non-streaming HTTP tool call。
3. 通过复制全部 task boundary data，保持现有非原子 managed-value 表示。
4. 明确 resource limit、cancellation race、timeout 与 cleanup。
5. 在 compile time 拒绝不安全 task call graph，而不是只依靠文档约定。
6. 通过明确的 capability-denial result 保持 browser WASM sandbox 的确定性。

### 2.2 非目标

本 RFC 不增加：

- closure、capturing lambda 或通用 first-class function value；
- 共享 Nomo object、mutex、atomic、任意 typed channel 或 mutable global；
- `async`/`await`、future、work stealing、green-thread scheduler 或 event-loop
  language transform；
- 强制终止 thread 或 panic isolation；
- streaming result、multi-producer channel 或 task-to-task message；
- application FFI callback 的 foreign-thread entry；
- browser Web Worker；
- 并发使用 `HttpStream`、`ProcessChild`、socket、server 或其它 thread-confined
  handle。

## 3. 当前 Gap 审计

| 领域 | 当前实现 | 缺口 |
| --- | --- | --- |
| Language call | 只有命名顶层函数；没有 function-value type 或 closure | 无法把可复用 work unit 传给 scheduler |
| Managed value | immutable string RC 与 array RC+COW 使用非原子计数 | 在线程间共享会造成 data race |
| HTTP | 已有结构化 HTTPS 与 pull-based stream | 相互独立的 non-streaming request 无法并行 |
| Process | 已有 controlled child handle 与 multiplexed I/O | handle registry 是 thread-confined |
| FFI callback | 已有不捕获环境的 `extern "C" fn` parameter | RFC 0019 拒绝 retained callback 与 foreign-thread runtime entry |
| Browser WASM | single-threaded interpreter 与 capability denial | 没有 native thread facility |
| Runtime | Windows process I/O 已在内部使用 Win32 thread | 没有 application-visible Nomo task lifecycle 或 ownership contract |

直接通过应用 FFI 暴露 `pthread_create` 或 `CreateThread` 不能安全解决问题。那会让
每个应用自行处理 callback ABI、allocation、cancellation 与跨平台 policy，并绕过
Nomo lifecycle check。

## 4. 详细设计

### 4.1 Canonical `std.task` API

```rust
pub struct Task {
    handle: u64
}

pub struct TaskContext {
    handle: u64
}

pub struct TaskError {
    pub code: string
    pub message: string
}

pub enum TaskJoin {
    Completed(string)
    Cancelled
    Timeout
}

pub fn spawn(
    worker: task fn(TaskContext, string) -> string,
    input: string
) -> Result<Task, TaskError>

pub fn is_cancelled(context: TaskContext) -> bool
pub fn join(task: Task, timeout_millis: u64) -> Result<TaskJoin, TaskError>
pub fn cancel(task: Task) -> Result<void, TaskError>
pub fn close(task: Task) -> Result<void, TaskError>
```

`Task` 与 `TaskContext` 是 opaque type；integer field 属于 compiler/runtime
实现细节，不公开。

Task callback type 只能作为 `std.task.spawn` 的第一个 parameter。它不是可存储
function value，不能出现在 struct、enum、return type、local binding、public user
API 或 FFI declaration 中。

### 4.2 Worker 声明与 Spawn

```rust
package parallel_agent_tools.main

import std.http
import std.task

fn call_tool(context: TaskContext, url: string) -> string {
    if task.is_cancelled(context) {
        return "{\"cancelled\":true}"
    }

    let response: Result<HttpResponse, HttpError> = http.get(url)
    match response {
        Ok(value) => {
            return value.body
        }
        Err(error) => {
            return error.message
        }
    }
}

fn run() -> Result<void, TaskError> {
    let first: Task = task.spawn(call_tool, "https://fixture.invalid/a")?
    let second: Task = task.spawn(call_tool, "https://fixture.invalid/b")?

    let first_result: TaskJoin = task.join(first, 5000)?
    let second_result: TaskJoin = task.join(second, 5000)?

    task.close(first)?
    task.close(second)?
    return Ok(())
}
```

Worker 必须是 unqualified、same-package、non-generic 顶层函数，并精确匹配：

```rust
task fn(TaskContext, string) -> string
```

Method、imported function、extern function、interface method、closure 与含 `mut`
parameter 的函数都不匹配。该约束为 C backend 提供稳定 generated symbol，并排除
hidden capture。

`spawn` 校验 input limit，把 UTF-8 byte deep-copy 到 runtime-owned storage，
分配 task state 并启动一个 native thread。Worker 在自己的 thread 上从该 copy
创建新的 Nomo string。Parent input value 永远不会被 worker retain。

### 4.3 Result 传递

Worker 返回时，trampoline 把返回 string byte 复制到 runtime-owned task storage，
然后在 worker thread release worker 的 Nomo string。`join` 在 parent thread 从
这些 byte 创建新的 Nomo string。没有 managed reference-counted allocation 跨越
boundary。

在 `close` 前，`Completed` 可以被多次 `join` 观察；每次都返回独立 owned Nomo
string。`close` 释放 runtime copy 并使 handle 失效。

### 4.4 Limit

首个实现固定：

- 每个 process 最多 64 个尚未 close 的 live task；
- 每个 task input 最多 8 MiB UTF-8；
- 每个 task output 最多 8 MiB UTF-8；
- `timeout_millis` 范围为 `0..=900_000`。

`timeout_millis == 0` 表示 non-blocking join。更大的 timeout 只限制 join
operation；它不是 execution deadline，也不隐含 cancellation。

过大的 worker result 形成 terminal `limit` error。Runtime 仍必须 join 并回收
native thread，且 `close` 必须保持可用。

### 4.5 Completion、Cancellation 与 Race

`cancel` 是 cooperative：设置 runtime flag 并唤醒 task-runtime waiter。Worker
通过 `is_cancelled(context)` 观察 flag。Cancellation 绝不调用
`pthread_cancel`、`TerminateThread`、asynchronous signal 或 long jump。

Terminal outcome 在 worker 返回时、task-state lock 下确定：

- worker 在 cancellation request 前返回，则之后的 cancellation 不替换
  `Completed`；
- cancellation 在 worker 返回前被请求，则 output 被丢弃，terminal outcome
  变为 `Cancelled`；
- cancellation request 自身并非 terminal，因为 worker 可能仍在运行；worker
  未在 join deadline 前返回时，`join` 返回 `Timeout`。

Handle live 时 `cancel` 是 idempotent。它不能中断正在另一个 API 内阻塞的 worker。
因此，task-safe blocking API 必须有自己的有限 timeout contract，worker 应在调用
之间检查 cancellation。

### 4.6 Close 与 Process Exit

只有进入 `Completed`、`Cancelled` 或 terminal runtime error 后，`close` 才成功。
Worker 仍在运行时调用返回 `busy`，不会 detach 或 leak thread。成功 close 会在
需要时 join native thread，释放 input/output buffer 和 synchronization object，
移除 registry entry 并使 handle 失效。重复 close 返回 `closed`。

程序应 cancel、join 并 close 每个 spawned task。正常 process return 时仍有 live
task，则 runtime 输出一条通用 diagnostic 并 best-effort cancel，但不能无限等待
不协作的 worker。Process exit 时，operating system 是最终 cleanup boundary。

### 4.7 Panic 行为

当前 Nomo panic path 会终止 process。Worker panic 不会被捕获并转换为
`TaskError`。隔离式 panic recovery 需要独立的 unwind/abort 决策，推迟处理。

### 4.8 Task-safe Call Graph

Compiler 在 lowering `spawn` 前校验 worker 及全部 transitively reachable Nomo
function。

首批 task-safe 集合包含：

- pure language computation 与 local managed value；
- `std.option`、`std.result`、`std.array`、`std.string`、`std.char`、
  `std.path`、`std.math`、`std.num`、`std.hash`、`std.crypto`、`std.json`、
  `std.regex` 与 `std.collections`；
- monotonic-clock read 与 `std.time.sleep`；
- native non-streaming `std.http.send`、`get` 与 `post`。

首批禁止集合包含：

- 任意 `unsafe` block、extern call、application FFI callback 或 raw handle；
- worker 内的 `std.task.spawn`；
- `std.http` stream 与 server handle；
- `std.fs`、`std.env`、`std.process`、`std.net`、terminal I/O、logging 与
  debug output；
- 之后新增但未显式分类为 task-safe 的 operation。

Compiler 输出稳定 task-safety diagnostic，指出 forbidden operation 与从 worker
出发的一条最短 call path。Unknown 或 indirect effect 保守拒绝。

这是只针对 task entry point 的 scoped effect check，不是通用 effect system，也
不承诺所有允许 API 在任意共享方式下都 thread-safe。

### 4.9 Native HTTP 要求

在 toolchain-owned non-streaming HTTP runtime 被标记为 task-safe 前，必须做到：

1. dynamic platform-library discovery 与 global initialization 通过 once/mutex
   gate 完成，之后才允许并发使用；
2. initialized function table immutable；
3. 每个 request 独占 easy/session handle、header、response buffer 与 error state；
4. task-safe request 不接触任何 `HttpStream` registry state；
5. Authorization value、request body 与 response body 继续禁止出现在 runtime
   diagnostic。

### 4.10 Error Contract

`TaskError.code` 为：

- `invalid_request`：timeout 或 operation argument 非法；
- `limit`：超过 live-task、input 或 output limit；
- `spawn`：创建 native thread 或 synchronization object 失败；
- `busy`：terminal state 前请求 close；
- `closed`：stale 或已经 close 的 handle；
- `runtime_unavailable`：当前 runtime 不支持 native task；
- `internal`：invariant 或 native wait 失败。

Message 稳定且通用，不得回显 worker name、input、output、prompt、URL、header、
token 或 response body。

Task-safety failure 是 compile-time diagnostic，不是 `TaskError`。

### 4.11 C99 Backend

Generated native code使用：

- Linux/macOS 上的 POSIX thread、mutex 与 condition variable；
- Windows 上的 `CreateThread`、critical section、event/condition variable 与
  wait function。

CLI 负责必需的平台 link flag；应用不需要在 `nomo.toml` 中增加 `pthread` 或
Win32 FFI metadata。

Runtime registry 与 task buffer 只包含 native allocation、callback pointer、
integer handle 与 synchronization state。Native trampoline 只在拥有对应 value
的 worker thread 上创建和销毁 Nomo managed value。

### 4.12 Browser WASM

Browser interpreter type-check 相同源码并识别 `task.spawn`，但返回
`runtime_unavailable`，且不调用 worker。其它 task operation 拒绝 invalid handle。
不增加 Web Worker、shared memory 或 host import，并保持现有 64 MiB sandbox
memory gate。

## 5. 兼容与迁移

本提案是 additive。现有语法、`std.process.spawn`、HTTP API 与非原子
managed-value ABI 均不变。

`task fn` 是新的 restricted type form，不会让普通 function first-class，也不改变
`fn` declaration 的含义。后续通用 function-value 设计可以为兼容顶层函数提供
显式 conversion，但必须保持本 RFC 的 boundary-copy 与 task-safety rule。

## 6. 备选方案

| 方案 | 优点 | 成本 / 拒绝原因 |
| --- | --- | --- |
| 先实现完整 `async`/`await` | 通用语法与 composability | Agent use case 验证前就扩张 parser、type system、lowering、scheduler、cancellation 与 lifetime |
| 共享内存 thread + atomic RC | 熟悉的 thread model | 让每个 managed value 都可跨线程，要求同步原语与 data-race rule，并重写已接受 v0.1 memory model |
| 先做 generic typed channel | 灵活 actor-style program | 需要为每种 type 定义 `Send`/serialization contract，并大幅扩张 monomorphized runtime |
| 每个 task 一个 OS process | 强 isolation | startup cost、部署复杂度与应用可见 framing 较高 |
| 可恢复 Nomo function event loop | 没有 OS-thread RC 问题 | 需要当前不存在的 continuation/coroutine 或 source transform |
| Host-specific application FFI | toolchain 修改小 | 每个 Agent 重复不安全 callback、ownership 与平台 policy |
| 隔离顶层 task + copied string boundary | 受限、适合 Agent tool、兼容 C99 与非原子 RC | signature 固定且每个 task 只有一个 result；首个切片接受 |

## 7. 缺点与风险

- 每个 task 一个 native thread 比 pool 更重；64-task limit 限制成本，pool 在测量
  后再讨论。
- 不协作 worker 无法安全强制停止。
- 固定 string boundary 要求结构化 input/output 使用 JSON 或其它显式 protocol。
- Compile-time task-safety classification 必须与每个新增标准库 operation 同步。
- Non-streaming HTTP global 需要谨慎的 once initialization 与 concurrency stress。
- Process-wide panic 行为弱于 actor/process isolation。

## 8. 对 Native CLI Agent 目标的影响

结合 RFC 0022 与 RFC 0025，本切片使 Nomo 应用可以：

1. 以 JSON string 构造独立 tool request；
2. 并发执行多个 non-streaming HTTPS call；
3. 以显式 timeout join 每个受限 result；
4. 请求 cooperative cancellation；
5. 解析 result 并继续 Agent loop，且无需应用侧 C FFI。

这不表示复刻完整 Hermes-style Agent，也暂不并行 streaming model response 或
长生命周期 child-process tool。

## 9. Acceptance Gate

在全部 gate 通过前，本 RFC 保持 `Proposed`：

1. Parser、formatter、semantic model、文档与两份 v0.1 specification 一致定义
   restricted `task fn` type。
2. Canonical `std.task` source、standard-module registry、compiler lowering、
   typed IR、C99 codegen 与 browser interpreter 暴露上面的精确 API。
3. Compile-time test 只接受精确 signature 的 unqualified、same-package、
   non-generic 顶层 worker，并拒绝全部 escaping 或 mismatch callback form。
4. Task-safety analysis 拒绝直接和 transitive forbidden operation，并以稳定
   diagnostic 报告 call path。
5. Native test 证明 input/result string 是 deep-copy，且没有非原子 managed
   allocation 跨 thread boundary。
6. 测试覆盖 completion、repeated join、zero/nonzero timeout、completion 与
   cancellation 两种 ordering outcome、idempotent cancel、busy close、
   successful close、stale handle 与全部精确 limit。
7. Local TLS fixture 证明至少两个 OpenAI-compatible non-streaming request 从
   Nomo worker 并发执行，且不依赖真实 API key。
8. Worker input、HTTP header、request/response body 与 oversized result 中的
   secret sentinel 不出现在 error、diagnostic 或默认 log。
9. Lifecycle stress 在 AddressSanitizer/LeakSanitizer 下重复 spawn、join、
   cancel、close；native race detector 或等价 stress gate 覆盖 registry、
   cancellation、join 与 HTTP once initialization。
10. Native task conformance suite 在 Linux、macOS 与 Windows 通过；真实 macOS
    arm64→x86_64 与 Linux x86_64→arm64 cross-build 链接所需 thread runtime。
11. Browser WASM 返回 `runtime_unavailable`，不增加 import，并保持现有 memory
    limit。
12. Nomo example 运行并行 JSON-described tool work，处理 timeout 与 cancellation，
    并 close 每个 task。
13. Formatting、Clippy、unit/CLI integration、release、WASM、cross-build 与
    platform smoke check 在签名 implementation PR 与 post-merge `main` 上通过。
14. 实现从签名 child branch 经 reviewed PR 合入；status 改为 `Accepted` 前记录
    acceptance evidence 与 link。

## 10. 推迟的后续工作

- 受限 worker pool 与 scheduling policy。
- Typed `Task<T>` 与 serialization-derived task message。
- Streaming/multi-message channel 与 multi-producer ownership。
- Thread-safe controlled process 与 HTTP stream handle。
- Structured concurrency 与 lexical task scope。
- Panic isolation。
- Browser Web Worker execution。
- 通用 first-class function、closure、future 与 `async`/`await`。

## 11. 参考

- `std/src/task.nomo`（提案）
- `crates/nomo_syntax/src/parser.rs`
- `crates/nomo_compiler/src/expressions/expression_helpers.rs`
- `crates/nomo_codegen_c/src/runtime/host_http_client.c`
- `crates/nomo_codegen_c/src/runtime/host_task.c`（提案）
- `crates/nomo_wasm/src/interpreter.rs`
- [POSIX Threads](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/pthread.h.html)
- [Windows threading and synchronization](https://learn.microsoft.com/windows/win32/sync/synchronization)
