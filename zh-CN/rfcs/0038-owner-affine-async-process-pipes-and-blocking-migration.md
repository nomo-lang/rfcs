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
| 相关 RFC | [RFC 0024](./0024-controlled-child-processes-and-stdio.md)、[RFC 0028](./0028-bounded-json-rpc-and-newline-stdio-framing.md)、[RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md)、[RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md)、[RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md)、[RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md)、[RFC 0037](./0037-owner-affine-async-tcp-client-and-blocking-migration.md)、[RFC 0039](./0039-loop-carried-coroutine-state-and-suspension-safe-mutation.md) |

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

- 最多 16 个 live 或 draining child slot；
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
| P2-PROC-B | bounded start job，加 epoll/kqueue pipe、exit、cancellation、close 与 Unix native example/test | 已由 [`nomo#54`](https://github.com/nomo-lang/nomo/pull/54) 实现 |
| P2-PROC-C | overlapped named pipe、IOCP completion、process wait、cancellation，以及无 per-child thread 的 Windows native test | 已由 [`nomo#55`](https://github.com/nomo-lang/nomo/pull/55) 实现 |
| P2-PROC-D | browser pre-evaluation unsupported boundary 与 release-WASM 证据 | 已由 [`nomo#56`](https://github.com/nomo-lang/nomo/pull/56) 实现 |
| P2-PROC-E | MCP stdio example、saturation/leak stress、low-memory run 与 RFC 0034 benchmark report | 已由 [`nomo#57`](https://github.com/nomo-lang/nomo/pull/57) 部分实现；stress、low-memory 与 benchmark gate 仍未完成 |

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
构建，以及 Linux、macOS、Windows PR CI 组均已通过。在本切片，该 workload
保持 disabled，且不能用于性能声明；P2-PROC-B 的实现证据在下节单独记录。

这些证据只完成 P2-PROC-A；它本身并不能证明 native process I/O、IOCP、
browser pre-evaluation capability handling、async MCP 示例或
resource/performance evidence。

### 11.2 P2-PROC-B 实现证据

[`nomo#54`](https://github.com/nomo-lang/nomo/pull/54) 已用 toolchain-owned
native runtime 替换 Unix ready 占位实现。Process start 与最终 reap 共用一个
惰性 worker 和固定表：最多 16 个 live handle、16 个并发 start job、32 个
start/reap 总 job。Command、argument、cwd 与 environment storage 在
publication 前完成 deep-copy，combined item 上限为 4096，storage 上限为
1 MiB，且 runtime error 与 diagnostic 都不会包含这些内容。Worker 不通过
shell 解析和启动 executable；每个 child 都没有专属 reader、writer 或
lifetime thread。

Child stdin、stdout 与 stderr 均为 nonblocking，并保持 owner-affine。Linux
把它们注册到 epoll，并在可用时通过 `pidfd` 观察退出；旧内核回退到同一个
bounded worker watch table 与唯一的 owner wake pipe。macOS 把 pipe 与
`EVFILT_PROC` 注册到 kqueue；exit-registration race 也回退到该 bounded watch
source。Fallback 不会增加 owner-side polling timer。带 generation 的 handle
slot 会阻止 late reap completion 关闭或释放已复用的 process identity。

Native fixture 已验证 `StdinFlushed`、incremental stdout/stderr 与最终
`Exited` 顺序；timeout 后复用 child；queued-start cancellation；termination
与 nonwaiting close；invalid UTF-8 protocol closure；精确 frame、timer、
reactor、process、blocking-job、retained-byte 与 zero-live counter；以及 host
支持 ASAN 时 cancellation/drop path 的 ASAN-clean。Runtime shutdown 会先
detach watch 并 join worker，再处理剩余 child，因此 `waitpid` 与 PID reuse
不会和 late completion delivery 竞态。`examples/async_process_pipe_unix`
通过 public Nomo path 执行，应用不写 C FFI。

该 PR 的 native Linux epoll/`pidfd`、macOS kqueue/`EVFILT_PROC` 与 Windows
CI 组均已通过。Windows 有意继续返回 typed、secret-safe `unsupported`；
cross-target C99 test 会锁定该 capability split。Clean-checkout P1 与 P3
benchmark harness 已接受全部 enabled static/counter gate，并继续拒绝性能
声明。Cross-language process workload 在拥有自包含的跨平台 child fixture
与公平、固定版本的 Go 对照前仍保持 disabled。

这只完成 Unix P2-PROC-B 切片。在当时，Windows IOCP process pipe、browser
pre-evaluation/release-WASM 证据、async MCP 组合、saturation/low-memory
stress 与可参与声明的 RFC 0034 measurement 仍属于 P2-PROC-C 至
P2-PROC-E；后续证据记录如下，本 RFC 继续保持 `Proposed`。

### 11.3 P2-PROC-C 实现证据

[`nomo#55`](https://github.com/nomo-lang/nomo/pull/55) 已用关联到当前 owner
IOCP 的 toolchain-owned overlapped named pipe 替换 Windows ready 占位实现。
现有固定 process table 继续保持 owner-local；唯一的惰性 bounded worker
只负责创建 process，不读取或写入 child pipe。一个受限的
`RegisterWaitForSingleObject` callback 会把带 generation 校验的 exit
completion 回投 owner IOCP，因此每个 child 都不占用 lifetime、reader 或
writer thread。

Runtime 会在打开 child endpoint 前启动每条 overlapped named-pipe connection，
并限制 connection handshake。已提交的 stdin、stdout 与 stderr operation 使用
固定表中的稳定 `OVERLAPPED` storage。Cancellation 调用 `CancelIoEx`；late
completion 在 IOCP packet 排空前继续拥有 detached buffer，因此 coroutine
frame drop 不会留下悬空 `OVERLAPPED` 指针。Process-pool completion
registration 只在存在 live job 时激活，并在最后一个 owner-visible completion
后停用，避免 idle registration 让 current-thread executor 永不退出。

Windows native fixture 已验证 stdin flush、incremental output 与 exit 顺序；
start/protocol failure；timeout 与 handle reuse；capability rejection；process、
blocking-job、reactor、timer 与 IOCP state 全部归零；registration/deregistration
平衡；以及每条已提交 IOCP operation 都被完整排空。IOCP counter 会区分临时
预留的固定 slot 与已被系统接受、后续交付 completion 的操作，因此同步 EOF
不会虚构一条已提交操作。Linux smoke、macOS native regression 与完整 Windows
host-runtime CI 组已一起通过。`examples/async_process_pipe_windows` 通过
public Nomo path 执行，应用不写 C FFI。

这只完成 P2-PROC-C。在当时，browser pre-evaluation/release-WASM 证据、
async MCP stdio 组合、saturation/low-memory stress 与可参与声明的 RFC 0034
process measurement 仍属于 P2-PROC-D 与 P2-PROC-E；后续证据记录如下，本 RFC
继续保持 `Proposed`。

### 11.4 P2-PROC-D 实现证据

[`nomo#56`](https://github.com/nomo-lang/nomo/pull/56) 已在 interpreter 与最终
artifact 两层锁定 browser process-capability boundary。一个 Nomo probe 把
一旦求值就会 panic 的 command 与 timeout function 传给 async
`process.start`。Browser runtime 会在任一 operand 运行前，为不可用的 process
capability 返回 secret-safe `NOMO-WASM-003`；poison text 与内部 intrinsic
名称都不会进入 error 或 stderr。

Release verifier 会构建优化后的 `wasm32-unknown-unknown` module，要求
WebAssembly import table 为空，实例化该精确 artifact，并通过 exported raw ABI
执行同一 poison-operand probe。Pull-request、main-branch 与 release workflow
共享此门禁。`nomo-wasm` suite 覆盖直接 interpreter path，Linux smoke 与
macOS/Windows native regression 也一同通过。现有
`async_process_pipe_contract` 示例继续作为 cross-target public Nomo surface；
native 示例则覆盖真实 Unix 与 Windows child I/O。

这只完成 P2-PROC-D。Async MCP stdio 组合、saturation/leak stress、low-memory
run 与可参与声明的 RFC 0034 process measurement 仍属于 P2-PROC-E，因此本
RFC 继续保持 `Proposed`。其中 MCP 组合依赖
[RFC 0039](./0039-loop-carried-coroutine-state-and-suspension-safe-mutation.md)
所提案的受限 suspending-loop 语义。

### 11.5 P2-PROC-E 部分实现证据

[`nomo#57`](https://github.com/nomo-lang/nomo/pull/57) 新增
`examples/mcp_stdio_async`：一个只使用 Nomo 应用代码、组合 owner-affine
`std.process` 与 bounded `std.jsonrpc` framing 的示例。它会执行 initialize 与
tools-list 两次 exchange，并让 decoder 与 completion state 穿过未知数量的
suspending-loop iteration。Local、无需 key 的 fixture 会刻意拆分第一条
response，合并一条 notification 与第二条 response，并独立发出 stderr。应用
不写 C FFI，也没有新增 MCP-specific runtime intrinsic。

同一 PR 修复了该 fixture 暴露的 Windows event-order 竞态。Stdout/stderr read
现在使用固定 `ProcessChild` slot 持有的 persistent registration 与 buffer。
返回 `StdinFlushed`、观察 exit 或一次 `next_event` timeout，不再取消可能已经
收到数据的无关 output read。Close 与 cancellation 仍会调用 `CancelIoEx`、
detach pending storage，并让固定 IOCP operation slot 持有它直到 completion
排空。

Linux epoll/`pidfd`、macOS kqueue/`EVFILT_PROC` 与 Windows IOCP job 都会执行
fragmented/coalesced 示例并断言 protocol output 成功。示例 metrics 要求 close
后 live process handle/operation、retained process byte、blocking job、reactor
registration 与 timer 全部为零。Linux smoke 还通过 release-WASM 与现有
P0/P1/P3 static/counter gate。

这些证据只完成 P2-PROC-E 的 MCP 组合与聚焦 lifecycle 部分。覆盖大量 child
及 cancellation race 的 saturation/leak stress、已记录的 low-memory run，以及
固定版本、公平的 RFC 0034 process-pipe 对照仍未完成；当前不能做任何相对 Go
的性能声明，本 RFC 继续保持 `Proposed`。

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
