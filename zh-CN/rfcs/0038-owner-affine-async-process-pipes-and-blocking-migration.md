# RFC 0038：Owner-Affine Async Process Pipe 与 Blocking Migration

> 语言 / Language: 中文 | [English](../../en/rfcs/0038-owner-affine-async-process-pipes-and-blocking-migration.md)

## 元数据

| 字段 | 值 |
| --- | --- |
| 编号 | 0038 |
| 标题 | Owner-affine async process pipe 与 blocking migration |
| 状态 | Proposed（已提案） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-27 |
| 主题 | process、async pipe、reactor、MCP、owner affinity、blocking pool、migration |
| 相关 RFC | [RFC 0024](./0024-controlled-child-processes-and-stdio.md)、[RFC 0028](./0028-bounded-json-rpc-and-newline-stdio-framing.md)、[RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md)、[RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md)、[RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md)、[RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md)、[RFC 0037](./0037-owner-affine-async-tcp-client-and-blocking-migration.md) |

## 1. 摘要

Nomo 的 controlled child-process API 增加 owner-affine、reactor-backed path，
以支持长生命周期 MCP stdio client。`process.start` 与
`process.next_event` 成为 direct-style suspend operation。bounded stdin
queue、close-stdin、non-consuming exit observation、termination request 与
close 保持不会等待 async worker 的同步操作。

新的 `ProcessChild` 标识由单个 executor 持有的 generation-checked slot。
Unix pipe 是 nonblocking reactor source；Windows 使用 overlapped pipe 与
IOCP，不再为每个 child 启动三个 helper thread。可能阻塞的 process creation
通过 bounded lazy blocking job queue 执行，并把 completion 返回 owner
executor。

RFC 0024 的同步 controlled API 在一个 preview migration window 内通过显式
`_blocking` 名称与 `BlockingProcessChild` 保留。legacy shell-string helper
保持不变且仍为 blocking。

本 RFC 状态为 `Proposed`。它固定 API、ownership、cancellation、migration、
platform 与 acceptance contract，但不声称当前同步 registry 已变成 async。

## 2. 当前审计

RFC 0024 已提供 MCP client 所需的协议行为，但 host 实现不能运行在 async
worker 上：

- Unix `next_event` 会同步循环调用 `poll` 与 `waitpid(WNOHANG)`；
- Windows 会为每个 child 启动一个 stdin writer 与两个 output reader thread，
  随后让 `next_event` 阻塞在 `WaitForMultipleObjects`；
- `start` 在 caller 上执行 executable search、pipe creation 与 process
  creation；
- process state 位于 process-global linked list，并使用没有 executor owner 的
  global numeric allocator；
- close 可能等待 worker 或 process exit；
- 把这些调用包进 coroutine 仍会阻塞 executor；
- 当前 `E0891` 已正确隔离会等待的 compatibility operation，但还没有
  nonblocking replacement。

现有 bounded 行为仍需保留：shell-free argv、显式 environment policy、一个
pending stdin payload、multiplexed stdout/stderr、UTF-8 boundary、
final-output-before-exit ordering、typed timeout 与 secret-safe error。

## 3. 目标与非目标

### 3.1 目标

1. 启动 shell-free child，且不阻塞 async worker。
2. 通过 native reactor/completion backend 增量交换 bounded UTF-8
   stdin/stdout/stderr。
3. 保留 multiplexed output，避免一个已满 pipe 使另一个 pipe deadlock。
4. 使 child 具备 `Local`/`!Send`、generation check 与 owner affinity。
5. 对 timeout、task cancellation、terminate、close、late completion 与
   runtime-shutdown cleanup 规定 exactly-once contract。
6. 移除 Windows per-child helper-thread model。
7. 保持 Agent application code 无需 C FFI。
8. 提供显式的单 preview-window blocking migration。

### 3.2 非目标

本 RFC 不增加 PTY、terminal emulation、inherited/null stream selection、
binary buffer、shell parsing、pipeline、process group、descendant-tree
termination、任意 signal、daemon child、MCP protocol semantic 或 HTTP
transport。

它也不会使 process handle 具备 `Send`、允许多个 task 并发 poll 同一个 child，
或用一个 blocking-pool job 承担每个 pipe 的完整生命周期。

## 4. 公共标准库 Contract

### 4.1 类型

现有 value type 保持不变，但 handle identity 分为两种：

```nomo
pub struct ProcessChild {
    handle: u64
}

pub struct BlockingProcessChild {
    handle: u64
}

pub struct ProcessExit {
    pub code: i32
    pub signal: i32
}

pub enum ProcessEvent {
    StdinFlushed
    Stdout(string)
    Stderr(string)
    Exited(ProcessExit)
}

pub struct ProcessControlError {
    pub code: string
    pub message: string
}
```

`ProcessCommand`、`ProcessEnv`、`ProcessExit`、`ProcessEvent` 与
`ProcessControlError` 保留 RFC 0024 的 field。`ProcessChild` 是新的
owner-affine async handle；`BlockingProcessChild` 只属于 compatibility
registry，两种类型不能混用。

### 4.2 Async surface

```nomo
pub suspend fn start(
    command: ProcessCommand,
    timeout_millis: u64
) -> Result<ProcessChild, ProcessControlError>

pub fn write_stdin(
    child: ProcessChild,
    data: string
) -> Result<void, ProcessControlError>

pub fn close_stdin(
    child: ProcessChild
) -> Result<void, ProcessControlError>

pub suspend fn next_event(
    child: ProcessChild,
    max_chunk_bytes: u64,
    timeout_millis: u64
) -> Result<ProcessEvent, ProcessControlError>

pub fn try_wait(
    child: ProcessChild
) -> Result<Option<ProcessExit>, ProcessControlError>

pub fn terminate(
    child: ProcessChild
) -> Result<void, ProcessControlError>

pub fn close_child(child: ProcessChild) -> void
```

`start` 在创建 runtime state 前校验 command。其 timeout 必须为正且不超过
15 分钟，覆盖 blocking-pool queue wait、process creation、pipe setup 与
owner-table handle delivery。它绝不调用 shell。

`write_stdin` 保留 RFC 0024 的 one-payload queue。它把一个非空、最大 1 MiB
的 UTF-8 payload 复制到 owner-local native storage，并在不等待 pipe capacity
的情况下返回。已有 queued payload 时返回 `busy`。`next_event` 驱动该 payload，
在全部 byte 写入后恰好发出一次 `StdinFlushed`。Timeout 或 task cancellation
保留未发送 suffix；调用方必须继续 poll，不能重复 queue 同一 payload。

`next_event` 保留 4-byte 到 1-MiB chunk bound，以及大于零且不超过 15 分钟的
timeout。它返回一个 `StdinFlushed`、`Stdout`、`Stderr` 或最终 `Exited`
event。Output 是合法 UTF-8，不拆分 scalar，保持各 stream 内部顺序；两个
stream 都 ready 时轮换首先检查的 stream。只有 exit 已知、两个 output pipe
均达到 EOF 且全部 buffered output 已返回后，才发出 `Exited`。

flush 后 `close_stdin` 幂等；有 pending payload 时返回 `busy`。`try_wait`
是 non-consuming、non-waiting observation。`terminate` 对 direct child 发出
一次 immediate forced-termination request，exit 后仍安全，且不会丢弃 final
output。

`close_child` 同步且幂等，但不得等待。它取消 child 的 reactor registration、
关闭 pipe direction、必要时请求 forced termination，并把 pending reap 或
late-completion cleanup 转交 owner executor。OS process 被 reap 且所有 late
completion drain 前，owner slot 不得复用。程序在 `start` 后立即注册
`defer process.close_child(child)`。

### 4.3 Blocking compatibility surface

在一个 preview migration window 内，RFC 0024 的 controlled 实现迁移为：

```nomo
process.start_blocking(command: ProcessCommand)
    -> Result<BlockingProcessChild, ProcessControlError>
process.write_stdin_blocking(child: BlockingProcessChild, data: string)
    -> Result<void, ProcessControlError>
process.close_stdin_blocking(child: BlockingProcessChild)
    -> Result<void, ProcessControlError>
process.next_event_blocking(
    child: BlockingProcessChild,
    max_chunk_bytes: u64,
    timeout_millis: u64
) -> Result<ProcessEvent, ProcessControlError>
process.try_wait_blocking(child: BlockingProcessChild)
    -> Result<Option<ProcessExit>, ProcessControlError>
process.terminate_blocking(child: BlockingProcessChild)
    -> Result<void, ProcessControlError>
process.close_child_blocking(child: BlockingProcessChild) -> void
```

这些名称保留已接受的同步行为，并继续在 suspend 调用图中被 `E0891` 拒绝。
`process.spawn`、`status`、`exec` 与 `output` 保留 legacy blocking shell
行为与隔离。

同步调用新的 `start` 或 `next_event` 时，编译器给出普通 suspend-effect
diagnostic，并指导标记 caller 为 `suspend` 或使用显式 `_blocking` path。
不存在隐式 blocking fallback。

## 5. Ownership、Bound 与 Backpressure

`ProcessChild` 是 `Local`/`!Send`。它可跨 suspension 存活在 owner task frame，
但不能跨 structured spawn、channel publication、frozen sharing 或 shard
transfer。复制 identifier 仍指向同一 slot；复制出的 stale value 只使 close
保持幂等，不产生 shared polling authority。

每个 current-thread executor 持有固定 process table。第一版使用以下 hard
bound：

- 最多 64 个 live 或 draining child slot；
- 每个 child 最多一个 pending `next_event` operation；
- 最多一个 pending stdin payload，上限 1 MiB；
- stdout/stderr direction 各最多一个 bounded read buffer；
- 每个 output direction 上限为 1 MiB 加 3-byte UTF-8 carry；
- 每个 child 最多四个 live reactor/completion interest；
- 最多 16 个 queued/running process-start blocking job；
- current-thread baseline 使用一个惰性 process-start worker。

Saturation 返回 `limit` 或 `busy`，绝不创建 unbounded queue、thread、buffer
或 registry node。普通 Nomo collection 与 ARC/COW value 不会因为 process I/O
而改用 atomic。

pending start job 或 stdin write 需要的全部 string/array，都必须在调用可
suspend 或返回前复制到 toolchain-owned native storage。后台 OS worker 不得
持有 Nomo-managed value。

## 6. Cancellation、Timeout、Close 与 Exit

start job 在 queued 阶段被取消或 timeout 时，从 queue 移除并释放 native copy。
如果 process creation 已经运行，frame 与 job detach；detachment 后才创建出的
child 会被 forced terminate、关闭 pipe 并 reap，且不会 publish handle。

`next_event` timeout 返回 `ProcessControlError { code: "timeout", ... }`，
deregister 本次调用的 interest，并保留 child、queued stdin suffix、buffer 与
exit state。Structured task cancellation 是 runtime task outcome，不是可捕获的
process error；它恰好一次移除 interest，随后由 caller 的同步 defer 关闭 child。

Readiness、timeout、cancellation、process exit 与 close 可能竞态。一个 atomic
或 owner-local state transition 胜出。每个 late event 都携带 slot 与 generation
identity，不能影响复用后的 slot。每个 pipe handle、process handle、native
buffer、blocking job、registration 与 frame-owned value 都只有一个 cleanup
owner。

Runtime shutdown 停止接收新 start job，取消 live process operation，发起 child
termination，drain late completion，并在声明的 shutdown deadline 前 reap 全部
child；随后在 debug/test 模式把剩余 job/handle 报告为 runtime failure。Native
Unix execution 不得遗留 zombie process。

## 7. Error 与 Secret Safety

Async surface 使用以下稳定 `ProcessControlError.code`：

- `invalid_request`：非法 command、limit argument 或 timeout；
- `unsupported`：target 或 host 缺少 process capability；
- `closed`：stale generation、closed child 或错误 executor owner；
- `busy`：已有 pending stdin payload 或 event pull；
- `limit`：child table、start queue 或 completion capacity 已满；
- `spawn`：executable、cwd、environment、pipe 或 process creation 失败；
- `io`：stdin/stdout/stderr、wait、terminate 或 close 失败；
- `timeout`：start 或 event deadline 到期；
- `protocol`：output 不是受支持的 UTF-8 text；
- `reactor`：registration 或 completion-backend 失败。

Compatibility path 在 preview window 内也可保留 RFC 0024 的
`runtime_unavailable`。

Error、diagnostic、scheduler trace、owner-table entry 与 benchmark label 都不得
包含 program、argv、environment name/value、cwd、stdin、stdout、stderr、
JSON-RPC content、native identifier 或复制出的 source argument。测试对每个
surface 使用不同 sentinel。

## 8. Platform Runtime Contract

### 8.1 Linux

Parent pipe descriptor 使用 nonblocking 与 close-on-exec。epoll 驱动
stdout/stderr read 与 stdin write。Process exit 在可用时使用 `pidfd`。portable
fallback 使用一个 bounded、lazy runtime reaper/wakeup source，把
generation-checked completion 路由到 owner；不得为每个 child 创建 thread，
也不得让多个 shard 在 `waitpid` 上竞态。

### 8.2 macOS 与 BSD

kqueue 驱动 pipe readiness 与 `EVFILT_PROC` exit notification。Process
creation 经 bounded start job 执行，因此 executable search、cwd policy 与
spawn 不占住 async worker。

### 8.3 Windows

Runtime 创建支持 overlapped 的 parent pipe endpoint，将其关联 owner IOCP，
并把 `OVERLAPPED` 与 payload ownership 放在 coroutine frame 外的稳定 operation
slot。Process exit 使用 bounded system wait callback，向 owner IOCP 投递一个
generation-checked completion。

Async path 会移除 RFC 0024 实现中的 stdin writer 与两个 output reader thread。
`CancelIoEx` 配合 completion draining 持有 late pipe operation；cancelled frame
绝不持有 live `OVERLAPPED` storage。

### 8.4 Process creation 与 blocking pool

Process creation 是 bounded lazy blocking pool 中的 typed job。Job 只包含已
验证的 native copy，带 generation，并最多向 owner 投递一个 completion。
第一版可以使用 process-specific one-thread queue，但必须遵守 RFC 0032 的公共
job/cancellation/shutdown contract，并在 RFC 0032 接受前并入 general pool。

Toolchain/runtime code 可以使用 platform process/C API。Nomo Agent application
code 不写 C FFI。

### 8.5 Browser WASM

没有 host process capability 时，`process.start` 在求值 command 或 timeout
operand 前返回 ready `unsupported` result。不会初始化 executor、blocking
worker、registry 或 host import。其他 async child operation 无法接收可构造的
handle。

## 9. Compiler 与 C99 Lowering

`process.start` 与 `process.next_event` 是 suspend intrinsic。第一版 lowering
要求 direct call 使用 `let` 绑定、operand 只求值一次，并复用 RFC 0031 与 async
TCP 的 nested stackless ABI 和 exactly-once frame-drop plan。

Validation failure、stale/closed handle、已有 buffered event、已观察 exit、无需
registration 的情况，以及 browser unsupported 都属于 ready path，不分配
coroutine node 或 enqueue task。真正 pending 的 start/event operation 最多持有
一个 frame 与固定 runtime slot。

Async surface 落地后，`E0891` 只把新的 suspend call 与已规定的 non-waiting
owner-local call 移出隔离。legacy shell helper 与全部 `_blocking` controlled
call 仍在隔离中。Sync-unused program 不得生成 executor、reactor、
blocking-pool、process-owner-table 或 atomic runtime support。

## 10. Acceptance Gate

### 10.1 Language 与 API

- canonical `std.process`、compiler builtin、C ABI、doc、example 与中英文
  specification 一致；
- effect diagnostic 覆盖 sync-to-suspend 与 transitive blocking compatibility
  call，且不泄漏 source argument；
- `ProcessChild` 为 Local/!Send，并在 spawn/channel/shard boundary 被拒绝；
- blocking migration 显式，source guidance 指明 `_blocking`。

### 10.2 Native correctness

Local fixture 覆盖：

- argv、cwd、inherited/replaced environment、missing executable 与 non-zero
  exit；
- 两条以上 newline-framed stdin message 与 `StdinFlushed`；
- interleaved stdout/stderr、pipe pressure、fairness、EOF 与 final exit；
- split UTF-8、invalid UTF-8、4-byte/1-MiB boundary；
- timeout 后成功复用、task cancellation、terminate、close、copied stale
  handle 与 slot reuse；
- queue/table saturation 与 one-core/low-memory 行为；
- start 在 spawn 前/中 cancellation，包括 late-created child termination 与
  reap；
- success、error、timeout、cancellation、panic 与 shutdown 后精确 zero-live
  counter。

Linux epoll、macOS kqueue 与 Windows IOCP 都需要 native execution。Cross-build
只是补充证据，不能替代 native run。Windows test 还需断言 async child 不创建
per-child reader/writer thread。

### 10.3 Browser 与 secret safety

Browser test 证明在 operand evaluation 前返回 unsupported，且 release artifact
没有 process host import。Native/browser diagnostic 与 error 必须排除全部
command、environment、pipe 与 JSON-RPC sentinel。

### 10.4 Example 与 benchmark

`mcp_stdio_async` 使用 local fixture、显式 limit/deadline、无 API key、无应用
C FFI，组合 `std.process` 与 `std.jsonrpc`。
`process_controlled_blocking` 记录 migration path。

RFC 0034 的 process-pipe workload 记录 bidirectional throughput、incremental
latency、cancellation、exit latency、CPU、RSS、thread count、handle/fd 与
p50/p99/p999。比较必须语义等价，不能为了分数丢弃 stderr 或 error handling。

## 11. 分阶段交付

| 切片 | 必需行为 | 状态 |
| --- | --- | --- |
| P2-PROC-A | public effect/handle/migration contract、diagnostic、lowering ABI、benchmark fixture | 已由 [`nomo#53`](https://github.com/nomo-lang/nomo/pull/53) 实现 |
| P2-PROC-B | bounded start job，加 epoll/kqueue pipe、exit、cancellation、close 与 Unix native example/test | Proposed |
| P2-PROC-C | overlapped named pipe、IOCP completion、process wait、cancellation，以及无 per-child thread 的 Windows native test | Proposed |
| P2-PROC-D | browser pre-evaluation unsupported boundary 与 release-WASM 证据 | Proposed |
| P2-PROC-E | MCP stdio example、saturation/leak stress、low-memory run 与 RFC 0034 benchmark report | Proposed |

每个切片通过聚焦 implementation PR 落地，并在此记录证据。全部 required native
correctness、resource、compatibility 与 benchmark gate 通过前，本 RFC 保持
`Proposed`。

### 11.1 P2-PROC-A 实现证据

[`nomo#53`](https://github.com/nomo-lang/nomo/pull/53) 已拆分 public handle
identity 与 migration path。`ProcessChild` 现在只属于 owner-affine suspend
surface；`BlockingProcessChild` 与七个显式 `_blocking` operation 则在 preview
migration window 内保留 RFC 0024 registry。Compiler 对同步调用
`process.start` 或 `process.next_event` 给出 secret-safe `E0870` 指引，继续用
`E0891` 隔离全部 shell helper 与 `_blocking` call，并在 structured spawn 与
bounded channel publication boundary 拒绝 `ProcessChild`。

C99 backend 通过类型化 start/resume/cancel registration lowering
`process.start` 与 `process.next_event`。`ProcessCommand` operand 只求值一次，
为调用 retain，并且恰好 release 一次；完成的 `Result` ownership 会移出 frame，
或由 cancellation/drop 释放。P2-PROC-A host adapter 有意 inline 返回
secret-safe `unsupported` result。generated-C gate 证明此占位实现不会发出
RFC 0024 process registry、helper thread 或 atomic support；Linux、macOS 与
Windows target lowering test 共享这一 contract。

Nomo 示例 `async_process_pipe_contract`、显式 blocking process/MCP migration
示例、native generated-C execution，以及 disabled 的 RFC 0034 process-pipe
fixture 已锁定 public 与 lowering contract。Workspace test、release WASM
构建，以及 Linux、macOS、Windows PR CI 组均已通过。在 P2-PROC-B 提供 native
registration 与 lifecycle counter 前，该 workload 保持 disabled，且不能用于
性能声明。

这些证据只完成 P2-PROC-A。Native bounded start job、epoll/kqueue pipe、
process exit、cancellation 与 close 仍属于 P2-PROC-B；IOCP、browser
pre-evaluation capability handling、async MCP 示例以及 resource/performance
证据仍是后续切片。因此本 RFC 继续保持 `Proposed`。

## 12. 备选与风险

| 备选 | 不选择原因 |
| --- | --- |
| 在 suspend code 中保留同步 `next_event` | 阻塞无关 task，违反 RFC 0032 |
| child 全生命周期都在 blocking pool 中运行 | 为 idle I/O 占用稀缺 blocking worker |
| 保留每个 Windows child 三个 thread | thread/RSS cost 随 child count 增长 |
| 分离的 blocking stdout/stderr read | 另一个 pipe 写满时可能 deadlock |
| 使 `ProcessChild` Send 或使用 global lock | 隐藏 owner affinity，并串行化无关 child |
| 返回 raw fd/HANDLE | 向应用暴露不安全的平台 authority |
| unbounded callback/background queue | 违反 backpressure 与 low-memory gate |

主要风险是 OS 已创建 child 后的 spawn cancellation、portable Unix exit
notification、Windows late completion，以及 panic/runtime shutdown cleanup。
Generation check、稳定 completion storage、单一 cleanup owner、native fault
fixture、精确 counter 与分阶段 platform gate 是强制缓解措施。

## 13. 提议决定

采用上述 owner-affine async process surface 与显式 blocking migration。从
current-thread executor 与 bounded job queue 起步；不得把同步 polling 或
per-child worker thread 隐藏在 suspend signature 后。
