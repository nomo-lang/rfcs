# RFC 0037：Owner-Affine Async TCP Client 与 Blocking Migration

> 语言 / Language: 中文 | [English](../../en/rfcs/0037-owner-affine-async-tcp-client-and-blocking-migration.md)

## 元数据

| 字段 | 值 |
| --- | --- |
| 编号 | 0037 |
| 标题 | Owner-affine async TCP client 与 blocking migration |
| 状态 | Proposed（已提案） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-26 |
| 主题 | async TCP、reactor、owner affinity、bounded I/O、DNS、迁移 |
| 关联 RFC | [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)、[RFC 0022](./0022-structured-http-client-and-host-runtime.md)、[RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md)、[RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md)、[RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md)、[RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md)、[RFC 0035](./0035-monotonic-suspend-timers-and-blocking-sleep-migration.md) |

## 1. 摘要

Nomo 第一组 reactor-backed 网络能力是 bounded、owner-affine TCP client。
`net.connect`、`TcpStream.read`、`TcpStream.write` 成为 direct-style `suspend`
operation；文本 helper 复用同一个 bounded engine。每个 operation 都有显式
timeout、返回结构化 `NetErrorKind`，且最多拥有一个带 generation 校验的
reactor registration。

当前 blocking client 在一个明确的 preview 迁移窗口内保留，名称统一带
`_blocking`。Blocking listener 与 UDP 在后续聚焦 RFC 替换前保持兼容，但文档
必须明确它们会阻塞。

本 RFC 为 `Proposed`，只锁定公开 contract 与分阶段 acceptance gate，不把现有
blocking 实现称为 async。

## 2. 当前审计

现有 `std.net` 不能原样进入 Agent async 路径：

- connect、accept、stream read/write 与 UDP 都会阻塞 OS thread；
- `TcpStream.read_to_string()` 一直读到 EOF，buffer 无上限增长；
- TCP value 保存 raw socket handle，不是 owner-table slot + generation；
- operation 没有显式 timeout 与 cancellation contract；
- portable `getaddrinfo` 可能阻塞，不能运行在 async worker；
- `NetError` 只有 host-derived message；
- 各平台尚未形成统一 capability contract。

P2 reactor foundation 已提供 lazy epoll、kqueue、IOCP lifecycle 与 timer wait，
但尚未注册 socket。仅把旧 helper 包在 coroutine 中仍会阻塞 executor，本 RFC
明确禁止这种实现。

## 3. 范围

本 RFC 定义 outbound TCP connect、增量 read、完整 bounded write、shutdown、
close、owner identity、timeout、cancellation、error 与 blocking migration。
它不定义 listener accept、UDP、TLS、HTTP/SSE、MCP framing、shared socket、
multi-shard handle migration 或公开 fd/socket/reactor-token API。

## 4. 标准库公开 Contract

### 4.1 Error 与 chunk

```nomo
pub enum NetErrorKind {
    InvalidInput
    Unsupported
    Timeout
    Cancelled
    Closed
    Busy
    Limit
    Resolve
    Connect
    Read
    Write
    Reactor
}

pub struct NetError {
    pub kind: NetErrorKind
    pub message: string
}

pub struct TcpChunk {
    pub data: Array<u32>
    pub eof: bool
}

pub struct TcpTextChunk {
    pub data: string
    pub eof: bool
}
```

portable control flow 使用 `kind`，application 不解析 `message` 中的平台错误号。
message 必须 bounded、secret-safe。`Array<u32>` 沿用 v0.1 byte 约定，元素只能
在 `0..=255`；text read 校验 UTF-8，非法输入返回 `Read`，不返回 partial text。

### 4.2 Suspend client operation

```nomo
pub suspend fn connect(
    host: string,
    port: i64,
    timeout_millis: u64
) -> Result<TcpStream, NetError>

impl TcpStream {
    pub suspend fn read(
        self,
        max_bytes: u64,
        timeout_millis: u64
    ) -> Result<TcpChunk, NetError>

    pub suspend fn read_string(
        self,
        max_bytes: u64,
        timeout_millis: u64
    ) -> Result<TcpTextChunk, NetError>

    pub suspend fn write(
        self,
        data: Array<u32>,
        timeout_millis: u64
    ) -> Result<void, NetError>

    pub suspend fn write_string(
        self,
        content: string,
        timeout_millis: u64
    ) -> Result<void, NetError>

    pub fn shutdown_write(self) -> Result<void, NetError>
    pub fn close(self) -> void
}
```

调用保持 direct style，但 caller 必须是 `suspend`。read 在至少读取一个 byte、
EOF、timeout、cancellation 或 error 时返回，绝不隐含 read-to-EOF；空 data
也可以带 `eof = true`。write 要么完整写完 bounded 输入，要么返回 error，
跨 readiness event 的进度保存在 operation frame 中。native write 每轮
executor poll 最多推进 64 KiB，避免一条 ready stream 独占 current-thread
executor。

`max_bytes` 范围为 `1..=1,048,576`；单次 write 上限为 1,048,576 bytes；
`timeout_millis` 上限为 900,000。零值只执行一次 immediate attempt，绝不注册
reactor；正 timeout 使用 monotonic clock。

### 4.3 Blocking compatibility

一个 preview migration window 内提供：

```nomo
pub fn connect_blocking(host: string, port: i64) -> Result<TcpStream, NetError>

impl TcpStream {
    pub fn read_to_string_blocking(self) -> Result<string, NetError>
    pub fn write_string_blocking(
        self,
        content: string
    ) -> Result<void, NetError>
}
```

async TCP 落地时，无后缀 client 名称使用上面的 suspend signature。同步 caller
得到 `E0870`；suspend call graph 到达 `_blocking` operation 时得到 `E0891`。
不存在按 caller effect 选择实现的 overload，也不允许 runtime 静默选择 blocking。

本 client-only RFC 暂不改变 blocking `listen`、`TcpListener.accept` 与 UDP
名称，但必须标注 blocking；后续迁移遵循相同的显式 effect/compatibility 规则。

## 5. Identity 与 Ownership

`TcpStream` 是 opaque、`Local/!Send`。runtime 保存 slot index、generation、
resource kind 与 owner executor identity；可复制的 raw socket 不是 authority。
bounded owner table 会拒绝 stale generation、错误 kind、closed slot 与 wrong
owner，绝不访问复用后的 resource。

第一切片中每个 stream direction 最多一个 pending operation。冲突返回 `Busy`，
不创建第二条 queue。application 跨 task 传 owned request/response data，不传
handle。

`close` 是独占 terminal path：deregister readiness、只关闭一次、推进 generation，
并使 late event 失效。取消一个 operation 会移除它，但 stream 保持打开，除非
structured cleanup 同时关闭其 owner。

## 6. Reactor Progress

一次 native operation：

1. 校验 limit 与 owner；
2. 尝试 immediate progress；
3. 完成时不分配、不注册并直接 ready；
4. 否则占用一个 bounded operation slot 与 registration；
5. 返回 `PENDING`；
6. readiness、cancellation 或 effective deadline 到来后 resume；
7. 校验 generation，完成或 rearm；
8. registration 与 retained buffer 各自恰好释放一次。

Unix socket 为 nonblocking。Linux 归一化 epoll one-shot readiness，macOS
归一化 kqueue one-shot filter。Windows 使用 IOCP completion ownership，
不能用 blocking worker 模拟 readiness。spurious readiness 遇到 would-block
后直接 rearm。write attempt 最多推进 64 KiB；payload 仍有剩余时 yield 并
rearm。该 fairness budget 不改变 complete-write result contract。

effective deadline 取 operation timeout 与外层 structured deadline 的较早值。
cancellation 只能赢一次，late event 由 slot/generation check 忽略。I/O
completion 必须立即回到 ready queue，不能在 timer wait loop 中继续等待。

## 7. DNS 与 Address Iteration

Portable `getaddrinfo` 可能阻塞，禁止在 async worker 上执行。分阶段交付：

1. 第一个 epoll/kqueue 切片只接受数字 IPv4/IPv6；hostname 在 I/O 前返回
   `Unsupported`；
2. bounded lazy blocking-pool resolver 增加 hostname，最多 16 个 candidate，
   并向 owner 发送一条 bounded completion；
3. native async resolver 只有在保持相同 bound、cancellation、顺序与 secret
   safety 时才能替代 blocking job。

candidate 按 resolver 顺序、共享一个 overall deadline；不能每个 address 重置
timeout。resolver queue saturation 返回 `Limit`。numeric-only 只是 milestone，
不代表 Agent networking 已完成。

## 8. Platform Phase

| 切片 | 必需行为 | 状态 |
| --- | --- | --- |
| P2-TCP-A | bounded owner table、generation check、registration lifecycle、epoll/kqueue numeric-host nonblocking connect | 已由 [`nomo#45`](https://github.com/nomo-lang/nomo/pull/45) 实现 |
| P2-TCP-B | epoll/kqueue 增量 bounded read 与完整 bounded write | 已由 [`nomo#46`](https://github.com/nomo-lang/nomo/pull/46) 实现 |
| P2-TCP-C | bounded blocking pool hostname resolution | 未实现 |
| P2-TCP-D | native Windows IOCP connect/read/write | 未实现 |
| P2-TCP-E | raw TCP 可用时接 host-driven browser adapter，否则在求值前 `runtime_unavailable` | 未实现 |

A 到 C 阶段，Windows 必须可编译并返回 `Unsupported`，不得求值或记录 secret
payload。这是显式 phase behavior，不等于 IOCP acceptance。Windows/browser
证据完成前，RFC 0032 不能进入 `Accepted`。

A/B 实现包含 bounded read/write payload、zero/positive timeout、structured
cancellation、每个 stream direction 一个 pending operation、精确
registration/retained-buffer lifecycle counter、Linux/macOS native 执行、
Windows 求值前明确拒绝与 Nomo example。`shutdown_write`、hostname
resolution、native IOCP 与 browser adapter 仍是后续切片。这些部分实现证据
不会把本 RFC 从 `Proposed` 提升为 `Accepted`。

## 9. Metrics 与 Limit

versioned metrics 至少增加：

- `reactor_registrations`、`reactor_deregistrations`、
  `reactor_reregistrations`；
- `io_connect_starts`、`io_read_starts`、`io_write_starts`；
- `io_ready_completions`、`io_timeouts`、`io_cancellations`、`io_errors`；
- `live_io_handles`、`peak_live_io_handles`、`live_io_operations`、
  `peak_live_io_operations`；
- retained read/write bytes 与 peak retained bytes。

ready path 的 registration 与 queue traffic 都为 0。timeout、cancellation、
close 与 failure fixture 结束时 live operation、registration、buffer 必须为 0。
所有 capacity 都要文档化并由 snapshot 测试；saturation 返回 `Limit`，table/
buffer 不能无界增长。

## 10. Diagnostic 与 Secret Safety

| 编号 | 条件 | 指引 |
| --- | --- | --- |
| `E0870` | 同步 caller 调用 async TCP | 标记 `suspend` 或使用显式 blocking compatibility API |
| `E0890` | `TcpStream` 跨 owner/task boundary | stream 留在 owner，传 owned data |
| `E0891` | suspend call graph 到达 blocking network I/O | 使用 suspend I/O 或 bounded blocking pool |
| `E0892` | target 缺少所需 TCP capability | 指明 target 与已实现 platform phase |

diagnostic 可以包含 operation、kind 与 bounded platform category，但不能包含
write/receive payload、高层 authorization token、environment value 或无界 host。

## 11. Acceptance Gate

每个 implementation PR 必须包含 Nomo example、unit/CLI integration test、
双语 stdlib/SPEC 文档、native platform evidence 与精确 counter/leak assertion。

确定性 fixture 覆盖 immediate/pending connect、one-byte/maximum read/write、
partial write、多次 readiness、EOF、zero/positive timeout、各生命周期阶段取消、
close/late-event、slot reuse、saturation、非法 UTF-8、numeric-only hostname
rejection、后续 bounded resolution 与 secret-safe error。

Linux/macOS 必须 native 执行 epoll/kqueue。P2-TCP-D 前 Windows 验证显式
unsupported，之后必须 native IOCP；cross-build 不能替代 native gate。

connect/read/write/cancellation 与所有必需 backend 完成前，RFC 0034 的 TCP
echo、churn、cancellation storm、latency、CPU/RSS、descriptor 与 buffer-leak
workload 都不得产生 performance claim。第一个正确切片只记录 baseline，不声称
超过 Go。

## 12. 备选方案与风险

| 备选方案 | 不采用的原因 |
| --- | --- |
| 永久增加 `connect_async` 名称 | 长期保留两套同义 API，违背 direct-style effect migration |
| 用 coroutine frame 包 blocking socket | 仍会在 executor 上阻塞其它 task |
| 保留无上限 read-to-EOF | 允许内存无界增长，也不利于增量 protocol framing |
| 暴露 raw socket/reactor token | 把 platform 与 owner-affinity 细节泄漏给 application |
| 在 worker 同步解析 DNS | 造成无界 scheduler stall |
| 强制 io_uring | 排除必需平台，并让语义依赖可选优化 |

主要风险包括 preview source breakage、backend divergence、cancellation race、
DNS queue pressure 与 retained-buffer leak。显式 compatibility 名称、统一 operation
state machine、generation check、native CI、bounded fixture 与精确 lifecycle
counter 用于降低这些风险。

## 13. v0.1 影响与后续问题

P2-TCP-A/B 已作为 additive executable slice 更新 SPEC 与标准库：Linux/macOS
提供 numeric-address suspend connect 和 bounded incremental read/write。
preview migration window 内，旧 client 行为通过显式 `_blocking` compatibility
名称保留；listener accept 与 UDP 仍为 blocking。

未来 dedicated byte type 可以替代 `Array<u32>`，但不改变 reactor contract。
listener/UDP migration、TLS 与 cross-shard stream transfer 都留给聚焦 follow-up，
本 RFC 不静默决定它们。

## 14. 决定

采用此 bounded owner-affine contract，按 phase 拆成小 PR。禁止暴露 raw socket/
reactor token、用 coroutine 包 blocking helper、在 async worker 做 DNS、在 async
名称下保留 unbounded read-to-EOF、每连接一个 thread、global registry lock，或
仅凭 generated C 推断 IOCP/browser parity。

完整 API、platform matrix、cancellation/resource gate、文档与 RFC 0034 公平
benchmark 全部通过前，本 RFC 保持 `Proposed`。

## 15. 参考

- [RFC 0015：Source-defined standard library 与 intrinsic](./0015-source-defined-standard-library-and-intrinsics.md)
- [RFC 0031：Direct-style suspend function 与 structured concurrency](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0032：Sharded executor、reactor 与 blocking pool](./0032-sharded-executor-reactor-and-blocking-pool.md)
- [RFC 0033：Task ownership transfer 与 concurrent value](./0033-task-ownership-transfer-and-concurrent-values.md)
- [RFC 0034：Async runtime acceptance 与 benchmark gate](./0034-async-runtime-acceptance-and-benchmark-gates.md)
