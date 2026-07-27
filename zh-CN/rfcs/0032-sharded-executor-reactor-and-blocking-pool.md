# RFC 0032：分片 Executor、Reactor 与 Blocking Pool

> 语言 / Language: 中文 | [English](../../en/rfcs/0032-sharded-executor-reactor-and-blocking-pool.md)

## 元信息

| 字段 | 值 |
| --- | --- |
| 编号 | 0032 |
| 标题 | 分片 executor、reactor 与 blocking pool |
| 决策状态 | Proposed（已提案） |
| 实现状态 | Partially implemented（部分已实现） |
| 实现证据 | [`nomo#44`](https://github.com/nomo-lang/nomo/pull/44) 至 [`nomo#59`](https://github.com/nomo-lang/nomo/pull/59) 的 current-thread/reactor 与 native I/O slice；per-core shard 尚未实现 |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-25 |
| 关联主题 | executor、reactor、epoll、kqueue、IOCP、WASM、affinity、blocking pool、Agent I/O |
| 关联 RFC | [RFC 0017](./0017-target-triples-and-cross-compilation.md)、[RFC 0022](./0022-structured-http-client-and-host-runtime.md)、[RFC 0023](./0023-pull-based-http-streaming-and-sse.md)、[RFC 0024](./0024-controlled-child-processes-and-stdio.md)、[RFC 0026](./0026-isolated-native-tasks-and-cooperative-cancellation.md)、[RFC 0027](./0027-bundled-sqlite-persistence-and-pull-queries.md)、[RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md)、[RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md)、[RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md)、[RFC 0035](./0035-monotonic-suspend-timers-and-blocking-sleep-migration.md)、[RFC 0040](./0040-owner-affine-async-http-and-sse-migration.md) |

## 1. 摘要

Nomo async runtime 从 current-thread executor + platform reactor 起步，随后扩展
为每个选定 core 一个 executor/reactor shard。task 与 I/O handle 具有 owner
affinity；跨 shard 通过 bounded channel 转移值，而不是共享普通 mutable state。

Linux 第一版使用 `epoll`，macOS/BSD 使用 `kqueue`，Windows 使用 IOCP，
browser WASM 使用 host-driven current-thread backend。`io_uring` 是后续可选
Linux 优化，不是语义依赖。阻塞 filesystem、SQLite、未知 C FFI 和 CPU-heavy
work 使用独立的 bounded lazy blocking pool。

本 RFC 状态是 `Proposed`。相应 runtime PR 满足 RFC 0034 门禁前，现有同步 host
helper 仍是当前实现。

## 2. 动机与现状审计

当前 runtime 面向有界同步调用：

- RFC 0026 每个 task 创建一个原生线程；
- HTTP streaming 在每次 pull 中同步驱动 libcurl/WinHTTP；
- Unix process pipe 虽为 nonblocking，但由同步 `next_event` 轮询；Windows
  使用 reader/writer helper thread；
- HTTP stream、process child、SQLite database/query 存在 process-global
  linked list，并使用 process-global numeric handle allocator；
- 这些 registry 不能支持并发 worker，也没有 executor ownership；
- SQLite 即使采用 serialized/full-mutex 配置，系统/library call 仍可能阻塞。

给每个 registry 套大锁既会串行化 runtime，也不能防止错误 executor 驱动 I/O
handle。runtime 必须显式建模 owner 与 readiness。

## 3. Executor 模型

### 3.1 Current-thread 基线

suspend entry 在调用它的 OS thread 上初始化一个 executor，拥有：

- FIFO ready queue；
- reactor instance；
- monotonic timer wheel；
- task/frame slab；
- 带 generation-checked slot 的 owner-local handle table；
- cancellation/deadline queue；
- RFC 0034 要求的 metrics。

poll 持续到 root structured scope 完成。一个 poll 若同步完成，就在 bounded poll
budget 内 inline 继续。pending task 注册 interest 后把控制权还给 executor。
ready fast path 不得 enqueue 或 allocate。

同步程序不初始化这些状态、不启动线程，也不让普通 collection operation 链接
atomic runtime helper。

### 3.2 分片多核 runtime

多核阶段为每个选定 shard 至多建立一个 async worker。默认数量受可用 core、
配置和 memory policy 限制；单核/低内存 target 只用一个 worker。

每个 task 有一个 owner shard。socket、HTTP stream、server acceptor、process
pipe、timer registration 等 handle 是 `Local` 且 owner-affine，只有 owner 能
修改或 poll。handle-table slot 包含 index、generation 与 resource kind，让 stale
或 wrong-kind handle 安全失败。

跨 shard 消息走 bounded queue 与 RFC 0033 的 publish/transfer 规则。默认没有
global work-stealing deque。未来 opt-in stealing 只能移动已证明为 `Send`、且
没有 `Local` value、active reactor registration 或 handle affinity 的 task；
只有 RFC 0034 benchmark 证明稳定收益后才能交付。

## 4. Reactor 与 Timer Backend

| Target | 第一版必需 backend | 契约 |
| --- | --- | --- |
| Linux | `epoll`，edge/level 差异由 runtime 归一化 | nonblocking fd registration、wakeup fd、batched readiness |
| macOS/BSD | `kqueue` | 将 socket、pipe、process、timer readiness 归一化为公共 event |
| Windows | IOCP | overlapped socket/pipe operation 与 completion ownership |
| browser WASM | host-driven current-thread adapter | JavaScript Promise/event completion 唤醒 exported runtime polling |
| 不支持的 native target | 显式编译诊断 | 不允许静默 fallback 后阻塞 async worker |

支持的 Linux kernel 可在 capability probe 后选择 `io_uring`，但必须保持相同的
取消、deadline 与 ownership 语义；fallback 到 `epoll` 不改变应用代码。

timer wheel 使用 monotonic clock、bounded horizon/bucket 与 batch expiry。
wall-clock 变化不影响 deadline，超长 timer 可按有界 round 重新插入。
RFC 0035 定义公开 suspend timer、blocking sleep 迁移、ready path 和
cancellation/drop 契约。

每个 shard 只有一个 wakeup source 处理跨 shard message 与 cancellation。
reactor event 做 generation check，已经关闭并复用的 slot 的旧事件不能唤醒新资源。

## 5. Nonblocking Agent I/O

以下 Agent 关键操作获得真正 suspend-capable path：

- TCP connect/accept/read/write/shutdown；
- HTTPS request header/body 与连接复用；
- HTTP response streaming 与 SSE 增量读取；
- process stdin write、stdout/stderr read、exit notification、terminate；
- timer 与 task synchronization；
- 长生命周期 child 上的 MCP newline/JSON-RPC framing。

suspend operation 注册 readiness/completion 后返回 `PENDING`，仅在可推进、取消或
deadline 到达时 resume。不得在 async worker 上循环等待。buffer size 与 queued
write 保持有界；队列满时 suspend 或返回 typed backpressure result。

现有 `std.http`、`std.net` 与 controlled `std.process` 中可能等待的操作改为
`suspend fn`。direct-style 写法减少源码噪音，但 caller 必须声明 `suspend`。
立即 close/accessor 仍同步。preview migration 期间，诊断必须说明新 effect，并在
存在时指出显式 blocking compatibility path。

HTTP TLS、headers、body limit、secret redaction 与 response contract 仍遵守 RFC
0022/0023。本 RFC 只改变 progress 驱动方式，不改变安全或协议语义。

## 6. Bounded Blocking Pool

blocking pool 与 async worker 分离：

- 首个 blocking job 前有零线程；
- minimum、maximum、queue capacity、idle retirement、shutdown deadline 有界；
- queue saturation 施加 backpressure，不创建无限线程；
- blocking job 不能访问 owner-local async handle；
- completion 通过 bounded queue 返回 origin shard；
- start 前取消会移除 job；start 后取消默认协作式，除非特定 host operation
  支持 interruption；
- shutdown 等到声明的 deadline，并报告剩余 job。

SQLite、blocking filesystem、没有 async host support 的 DNS、未知 blocking C
FFI 与显式 CPU work 走此 pool。toolchain/runtime 可调用 system C library，
Agent 应用代码无需为了这些能力编写 C FFI。

RFC 0026 的 `task fn(TaskContext, string) -> string` compatibility API 在一个
有文档的 preview migration window 内由此 pool 重实现。legacy
`std.task.spawn` 不再表示“一 task 一 OS thread”。新 async task 使用 RFC 0031
structured spawn。nested legacy blocking job 不能使 pool 死锁；实现必须拒绝，
或采用有界 helping rule。

## 7. Runtime Ownership 与 Atomic Shim

async path 移除 process-global unguarded linked-list registry。HTTP stream、
process child、socket、SQLite operation 与 timer 存入 owner table 或具有显式
transfer/close 规则的 blocking-job state。

跨线程 executor metadata、shared value、channel 与 wakeup 使用私有 C99-compatible
atomic shim：

- GCC/Clang 使用 `__atomic_*`；
- Windows 使用 Interlocked；
- 每个 primitive 记录 acquire/release/sequential 需求；
- 不支持的 compiler 在 target capability validation 中失败。

普通 `string`、`Array<T>`、ordered `Map<K,V>` 与 task-local value 不使用此
shim。toolchain 生成的公共 C header 不把它暴露为 application ABI。

## 8. 取消、关闭与 Runtime Shutdown

每个 pending operation 只拥有一个 reactor registration/completion token。取消
只进行一次 pending-to-cancelled transition，注销或取消 host operation，并在
owner shard 安排 frame cleanup。late readiness 通过 generation check 忽略。

affine handle 的 close 是独占的；仅在 stdlib type 明确规定时才 idempotent。
close 消耗 handle；use-after-close 和 wrong-shard access 返回稳定 typed error 或
compiler diagnostic，不解引用 stale registry node。

root shutdown 顺序：

1. 停止接收 daemon/blocking work；
2. 取消 structured scope 与声明的 daemon scope；
3. drain completion/drop work；
4. 等待 blocking-pool deadline；
5. 释放 reactor/slab resource；
6. debug/test 模式报告 leaked handle/task。

## 9. 诊断

| 代码 | 条件 | 必需指导 |
| --- | --- | --- |
| `E0890` | 在非 owner task/shard 使用 `Local` handle | 保持在 owner 执行，跨 task 发送 data 而非 handle |
| `E0891` | async worker 调用已知 blocking intrinsic | 使用 suspend wrapper 或显式 blocking pool |
| `E0892` | target 缺少所需 reactor capability | 指明 target 和支持的 backend/configuration |
| `E0893` | legacy `task fn` 违反 blocking-pool nesting rule | flatten job 或使用 structured async task |

### 9.1 Blocking compatibility 隔离

在 owner-affine suspend 替代路径实现以前，`suspend fn` 的本地调用图只要到达
任何会等待当前 OS thread 的 compatibility 操作，就必须以 `E0891` 失败：

- HTTP client 与 stream progress：`http.get`、`http.post`、`http.send`、
  `http.open_stream`、`http.read_text` 与 `http.next_sse`；
- blocking HTTP server progress：`http.listen`、`http.accept` 与
  `http.respond_string`；
- legacy shell process helper：`process.spawn`、`process.status`、
  `process.exec` 与 `process.output`；
- 可能 spawn、wait、terminate 或 reap 的 controlled-process lifecycle：
  `process.start`、`process.next_event`、`process.terminate` 与
  `process.close_child`。

诊断覆盖 qualified call、specific import call，以及经本地 helper function
传递的 transitive call；诊断必须给出调用路径，且不得包含参数值。普通同步
function 保持 source-compatible。

stream close/cancel、bounded process-stdin queue、`close_stdin`、`try_wait`
等按契约无需等待即可返回的 compatibility 操作，不会仅因接触旧 handle 就被
归类为 `E0891`。它们仍只是 current-thread compatibility surface，不能作为
`Send`、cross-shard safety 或 owner-affine async I/O 的证明；在进入 sharded
execution 前，聚焦的 HTTP/process RFC 必须重新规定其 handle ownership。

该隔离是实现门禁，不是 async 实现：禁止只把同步 pull 包进 coroutine 或
polling loop。只有当对应 suspend path 注册 reactor/completion interest，
通过 cancellation/deadline/leak test，并取得 RFC 0034 要求的 native platform
证据后，操作才能移出隔离清单。

runtime backpressure、timeout、cancellation、closed-handle 与 reactor error 使用
typed stdlib result，且消息不得泄露 secret。Authorization header、token、process
environment secret、request body、SQLite value 不得进入诊断或 scheduler trace。

## 10. 测试与验收

单测覆盖 ready-queue fairness、timer ordering、generation reuse、registration
cancellation、late event、blocking-pool saturation、shutdown 与 atomic memory
order wrapper。

集成测试覆盖 native TCP、HTTP keep-alive/SSE、process pipe/MCP、经 blocking
pool 的 SQLite、cancellation storm、connection churn 与 resource limit。local
fixture 提供确定性 TLS/协议行为，不依赖真实 API key。

platform CI 必须执行 `epoll`、`kqueue`、IOCP 与 host-driven WASM。cross build
不能替代 reactor 验收；每个 backend 都需 native run 或长期维护的 platform
runner。sanitizer 与 debug leak counter 必须证明无 fd、buffer、registration、
task 或 handle leak。

量化门禁见 RFC 0034。只在一个平台编译成功不能让本 RFC 变为 `Accepted`。

## 11. 备选与风险

| 备选 | 不选择原因 |
| --- | --- |
| 一个 global executor/reactor lock | 形成 contention 并模糊 handle owner |
| 默认 global work stealing | 与 local handle affinity 冲突，且需先证明价值 |
| thread-per-connection/task | 空闲 Agent workload 的 stack/RSS/scheduling 成本过高 |
| blocking call 跑在 async worker | 阻塞无关 task，破坏 latency bound |
| 强制 `io_uring` | 排除 kernel/target，并使语义依赖优化 |
| 锁住所有现有 global registry | 没有定义 lifetime 或 owner affinity |

主要风险是 backend divergence、cancellation race、platform CI 成本和 worker 上
意外 blocking。统一 conformance test、公共 reactor contract、owner assertion
与 benchmark/leak harness 是必需缓解措施。

## 12. 实施阶段与决定

1. current-thread executor、yield、timer wheel、cancellation、metrics；
2. Linux `epoll` 与 macOS `kqueue`，async TCP、HTTP/SSE、process pipe；
3. Windows IOCP 与 host-driven browser WASM parity；
4. bounded blocking pool 与 RFC 0026 compatibility migration；
5. per-core shard 与 bounded cross-shard channel；
6. 最后才是可选 stealing、`io_uring`、batching 与 slab tuning。

### 12.1 已交付证据

| 切片 | 证据 | 剩余门禁 |
| --- | --- | --- |
| P2-GUARD：blocking compatibility 隔离 | [`nomo#52`](https://github.com/nomo-lang/nomo/pull/52) 已为第 9.1 节列出的 HTTP/SSE 与 process 操作实现 `E0891` | 真正 owner-affine 的 suspend HTTP/SSE 与 process-pipe path |
| P2-PROC-A：process effect 与 lowering boundary | [`nomo#53`](https://github.com/nomo-lang/nomo/pull/53) 已增加 Local/!Send process handle 拆分、suspend ABI、显式 blocking migration 与 ready zero-thread 占位实现 | native 实现与平台证据由后续 process 切片跟踪 |
| P2-PROC-B：owner-affine Unix process pipe | [`nomo#54`](https://github.com/nomo-lang/nomo/pull/54) 已增加唯一的 bounded lazy start/reap worker、Linux epoll/`pidfd`、macOS kqueue/`EVFILT_PROC`、owner-local nonblocking pipe、cancellation/timeout/close、精确 counter、ASAN fixture 与 native Nomo 示例 | Unix correctness 无剩余门禁；cross-platform completion 继续在下方跟踪 |
| P2-PROC-C：owner-affine Windows process pipe | [`nomo#55`](https://github.com/nomo-lang/nomo/pull/55) 已增加 overlapped named pipe、owner-local IOCP completion、受限 process creation 与 exit notification、late-completion draining、精确 lifecycle counter、Windows native fixture，以及没有 per-child I/O thread 的 Nomo 示例 | Windows correctness 无剩余门禁；browser 与 resource 门禁继续在下方跟踪 |
| P2-PROC-D：browser process capability boundary | [`nomo#56`](https://github.com/nomo-lang/nomo/pull/56) 已验证零 import 的 release WASM artifact 会在求值或泄漏毒化 command/timeout operand 前拒绝 async `process.start` | async MCP 组合、saturation/low-memory stress 与可参与声明的 RFC 0034 measurement |
| P2-PROC-E：MCP/resource/measurement 收口 | [`nomo#57`](https://github.com/nomo-lang/nomo/pull/57)、[`nomo#58`](https://github.com/nomo-lang/nomo/pull/58) 与 [`nomo#59`](https://github.com/nomo-lang/nomo/pull/59) 已增加 native async MCP loop、16-child saturation 与 15-job cancellation stress、单核/128 MiB resource gate，以及固定 Go 1.25.12 的 process-pipe report | process 切片已完成；controlled-host target 与更广的 HTTP/SSE/TCP/platform benchmark matrix 仍未完成 |

实现会跟踪 qualified call、specific import call、本地 transitive call 与跨 project
module 的 transitive call。Compiler test 覆盖完整隔离操作集，并保留明确无需
等待的 compatibility 例外；CLI test 证明 rendered diagnostic 会把源码摘录
替换为安全的 `operation(...)` 标签，因此 URL、token、command 与参数值不会
进入 stderr。同步 compatibility code 仍可通过。Linux smoke 以及 macOS、
Windows native CI 均已通过。

隔离证据能阻止已知 blocking compatibility I/O 占住 async worker。
P2-PROC-A 还固定了 process suspend effect 与 C99 state-machine boundary，且
没有把旧 registry 藏在该边界之后。P2-PROC-B 已在 Unix 替换该占位实现：唯一
的 bounded worker 负责 start/reap 与已记录的 portability fallback exit
watch，pipe progress 则保持在 owner reactor，没有 per-child thread 或 owner
polling。P2-PROC-C 已用 owner-local overlapped named pipe、固定 IOCP
operation table、唯一的惰性 bounded process-creation worker，以及把
completion 回投 owner IOCP 的受限 system exit wait 替换 Windows 占位实现。
P2-PROC-D 已验证最终零 import 的 browser WASM artifact 会在求值 async
command 或 timeout operand 前返回稳定的 process-capability error。
P2-PROC-E 增加 Nomo-native MCP loop、受限 saturation/cancellation cleanup，
并在 Linux affinity、address-space、RSS、fd 与 thread control 下生成版本化
process-pipe 对照。通过的 hosted-runner result 接近持平，但尚未达到 RFC 0034
的 throughput 与 RSS 设计目标。HTTP/SSE/TCP path、per-core shard、
controlled-host 重复与更广平台 benchmark matrix 仍未完成，因此本 RFC 继续
保持 `Proposed`。

**提议决定：**采用 owner-affine current-thread/sharded executor、platform
reactor 与独立 bounded blocking pool；不扩张现有 thread-per-task 或 unguarded
global-registry 架构。

## 13. 参考

- [RFC 0022：结构化 HTTP client 与 host runtime](./0022-structured-http-client-and-host-runtime.md)
- [RFC 0023：pull-based HTTP streaming 与 SSE](./0023-pull-based-http-streaming-and-sse.md)
- [RFC 0024：受控子进程与 stdio](./0024-controlled-child-processes-and-stdio.md)
- [RFC 0026：隔离原生任务与协作式取消](./0026-isolated-native-tasks-and-cooperative-cancellation.md)
- [RFC 0031：直写式挂起函数与结构化并发](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0033：任务所有权转移与并发值](./0033-task-ownership-transfer-and-concurrent-values.md)
- [RFC 0034：异步 runtime 验收与基准门禁](./0034-async-runtime-acceptance-and-benchmark-gates.md)
- [RFC 0035：单调时钟挂起 Timer 与阻塞 Sleep 迁移](./0035-monotonic-suspend-timers-and-blocking-sleep-migration.md)
- [RFC 0038：Owner-affine async process pipe 与 blocking migration](./0038-owner-affine-async-process-pipes-and-blocking-migration.md)
- [RFC 0040：Owner-affine async HTTP/HTTPS、SSE 与 blocking migration](./0040-owner-affine-async-http-and-sse-migration.md)
