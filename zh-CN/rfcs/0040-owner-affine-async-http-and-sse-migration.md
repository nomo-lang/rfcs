# RFC 0040：Owner-Affine Async HTTP/HTTPS、SSE 与 Blocking Migration

> 语言 / Language: 中文 | [English](../../en/rfcs/0040-owner-affine-async-http-and-sse-migration.md)

## 元数据

| 字段 | 值 |
| --- | --- |
| 编号 | 0040 |
| 标题 | Owner-affine async HTTP/HTTPS、SSE 与 blocking migration |
| 决策状态 | Proposed（已提案） |
| 实现状态 | Partially implemented（部分已实现） |
| 实现证据 | [`nomo#61`](https://github.com/nomo-lang/nomo/pull/61) 的 P2-HTTP-A public suspend ABI 与 migration boundary；P2-HTTP-B–F 尚未实现 |
| 作者 | Nomo Language Working Group |
| 创建时间 | 2026-07-27 |
| 关联主题 | HTTP、HTTPS、TLS、SSE、async I/O、reactor、owner affinity、connection reuse、migration |
| 关联 RFC | [RFC 0022](./0022-structured-http-client-and-host-runtime.md)、[RFC 0023](./0023-pull-based-http-streaming-and-sse.md)、[RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md)、[RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md)、[RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md)、[RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md)、[RFC 0037](./0037-owner-affine-async-tcp-client-and-blocking-migration.md) |

## 1. 摘要

Nomo 的结构化 HTTP/HTTPS client 与 pull-based response streaming 增加
owner-affine、由 reactor 驱动的 suspend path。`http.send`、`http.get`、
`http.post`、`http.open_stream`、`http.read_text` 与 `http.next_sse`
成为 direct-style suspend operation。RFC 0022/0023 已接受的 TLS 校验、
结构化 header、response limit、UTF-8/SSE framing、稳定 error 与 secret
redaction 规则不变。

`HttpStream` 成为由一个 executor 所有、generation-checked 的
`Local`/`!Send` handle。Unix-like target 通过 epoll/kqueue readiness 驱动共享
libcurl multi handle，并隔离有界 DNS job；Windows 把 asynchronous WinHTTP
status completion 回投 owner executor。两条路径都不能阻塞 async worker，也
不能为每个 request 创建一个 application thread。

已接受的同步 client 在一个 preview migration window 内通过显式 `_blocking`
名称与 `BlockingHttpStream` 保留。Plain HTTP server 继续作为隔离的 blocking
compatibility surface，直到独立 server RFC 替换它。

本 RFC 是 `Proposed`。它会在实现前固定 effect、ownership、transport、
migration、connection reuse、cancellation、platform 与 acceptance contract，
不会把当前同步 pull loop 改名后冒充 async。

## 2. 当前审计

RFC 0022/0023 已接受的实现适合受限、单线程 CLI call，但不能在 async executor
worker 上运行：

- buffered request 会同步执行 libcurl easy 或 WinHTTP 直到完成；
- Unix stream open/read loop 会在 caller 上调用 `curl_multi_perform` 与
  `curl_multi_poll`/`curl_multi_wait`；
- Windows stream open/read 会同步调用 WinHTTP send、receive 与 read；
- stream state 位于 process-global linked list，使用全局数值 allocator，没有
  executor owner 或 generation；
- 每个 Unix stream 各自拥有一个 multi handle，因此已接受 runtime 没有受限的
  owner-local connection pool；
- portable name resolution 若不从 async worker 隔离，可能阻塞；
- compatibility 实现没有稳定 completion slot，close/cancel 无法与 pending async
  callback 安全竞态；
- 把任何现有 operation 包进 coroutine 仍会阻塞其他 task；
- compatibility registry 还没有 lifecycle counter 或 sanitizer gate，无法证明
  future cancellation/completion race 下只有一个 cleanup owner。Blocking
  migration 必须保留当前 single-thread behavior，并在 async table 落地前补充这类
  回归证据。

因此现有 `E0891` 隔离正确。真实替代实现必须把 transport
readiness/completion 接入 executor，保留全部已接受 protocol behavior，并让
每条 success/error/cancellation path 都有精确 resource ownership。

## 3. 目标与非目标

### 3.1 目标

1. 在不阻塞 async worker 的情况下执行经过校验的 HTTP/HTTPS request。
2. 使用自然 pull backpressure 增量消费受限 UTF-8 chunk 与已解析 SSE event。
3. 对 request、response、stream 与 connection memory 设置显式上限。
4. 让 stream owner affine，并拒绝跨 task/shard publication。
5. 精确定义 deadline、structured cancellation、显式 cancel/close、late
   completion 与 runtime shutdown。
6. 在一个 executor 内复用 connection，同时不让普通 Nomo value 或
   authorization state 跨 request 共享。
7. 保持 application-side 无 C FFI；toolchain runtime 仍可使用 libcurl、WinHTTP
   与 platform API。
8. 提供一个 window 的显式 blocking migration。

### 3.2 非目标

本 RFC 不增加 HTTP server async accept/respond、WebSocket、任意 streaming
request body、binary response chunk、cookie、自动 redirect、ambient proxy
配置、public TLS 配置、raw socket/reactor access、public `HttpClient`、跨 shard
stream transfer 或 browser `fetch`。

本 RFC 不承诺 HTTP/2 multiplexing。只有在保持同样 bounds、isolation、
cancellation 与 fairness 时 backend 才可协商 HTTP/2；第一版可以固定 HTTP/1.1，
保证每个 transfer 能独立计量。

## 4. Public Standard-Library Contract

### 4.1 类型

`HttpHeader`、`HttpRequest`、`HttpResponse`、`HttpStreamChunk`、`SseEvent` 与
`HttpError` 保留 RFC 0022/0023 语义。Handle identity 拆分为：

```nomo
pub struct HttpStream {
    handle: u64
    pub status: i64
    pub headers: Array<HttpHeader>
}

pub struct BlockingHttpStream {
    handle: u64
    pub status: i64
    pub headers: Array<HttpHeader>
}
```

`HttpStream` 标识新的 owner table；`BlockingHttpStream` 只标识 compatibility
registry，两者不能混用。

### 4.2 Suspend client surface

```nomo
pub suspend fn send(
    request: HttpRequest
) -> Result<HttpResponse, HttpError>

pub suspend fn get(
    url: string
) -> Result<HttpResponse, HttpError>

pub suspend fn post(
    url: string,
    body: string
) -> Result<HttpResponse, HttpError>

pub suspend fn open_stream(
    request: HttpRequest,
    idle_timeout_millis: u64
) -> Result<HttpStream, HttpError>

pub suspend fn read_text(
    stream: HttpStream,
    max_chunk_bytes: u64
) -> Result<HttpStreamChunk, HttpError>

pub suspend fn next_sse(
    stream: HttpStream,
    max_event_bytes: u64
) -> Result<Option<SseEvent>, HttpError>

pub fn cancel_stream(stream: HttpStream)
pub fn close_stream(stream: HttpStream)
```

Direct-style call 要求 caller 为 `suspend`。`get` 与 `post` 通过构造一个
structured request 调用同一 suspend engine，保留已接受的 30 秒 deadline 与
8 MiB response-body limit。

`send` 在 response body 于 `max_response_bytes` 内完整接收后完成。
`open_stream` 在最终 response head 可用后完成，并把 transport 保存在 owner
table 中。HTTP 4xx/5xx 仍是成功 transport response，通过 `status` 暴露。

`read_text` 与 `next_sse` 保留 RFC 0023 的 chunk、UTF-8、event 与 cumulative
response limit。Stream 的 `idle_timeout_millis` 限制每个后续 pull；有效 deadline
取该 idle deadline 与 enclosing structured deadline 中更早者。

### 4.3 Blocking compatibility surface

在一个 preview migration window 内，已接受同步实现迁移到：

```nomo
http.send_blocking(request: HttpRequest)
    -> Result<HttpResponse, HttpError>
http.get_blocking(url: string)
    -> Result<HttpResponse, HttpError>
http.post_blocking(url: string, body: string)
    -> Result<HttpResponse, HttpError>
http.open_stream_blocking(
    request: HttpRequest,
    idle_timeout_millis: u64
) -> Result<BlockingHttpStream, HttpError>
http.read_text_blocking(
    stream: BlockingHttpStream,
    max_chunk_bytes: u64
) -> Result<HttpStreamChunk, HttpError>
http.next_sse_blocking(
    stream: BlockingHttpStream,
    max_event_bytes: u64
) -> Result<Option<SseEvent>, HttpError>
http.cancel_stream_blocking(stream: BlockingHttpStream)
http.close_stream_blocking(stream: BlockingHttpStream)
```

每个 `_blocking` request 或 pull operation 在 suspend call graph 中继续被
`E0891` 拒绝。同步调用 unsuffixed client operation 会得到 `E0870`，指引 caller
标记 `suspend` 或选择显式 blocking 名称。不存在 effect overload 或隐式 runtime
切换。

`listen`、`accept` 与 `respond_string` 继续是 blocking server operation，并保留
`E0891`。`close_server` 与 `close_exchange` 继续作为 immediate compatibility
cleanup call。本 RFC 不暗示 server owner affinity。

## 5. Request、Stream 与 Cancellation 语义

RFC 0022 validation 继续作为规范：

- 只允许 `GET` 与 `POST`；
- 只允许无 user-info/fragment 的绝对 `http://` 与 `https://` URL；
- HTTPS 校验 peer certificate 与 host name；
- 允许包括 `Authorization`、`Content-Type` 在内的安全自定义 header；
- hop/framing header 由 runtime 所有；
- 不自动跟随 redirect；
- URL text 最多 16 KiB、application header 最多 128 个、序列化 application
  header text 最多 64 KiB、request body 最多 16 MiB；
- positive request deadline 不超过 15 分钟；
- positive response cap 不超过 128 MiB hard ceiling；
- response head 上限为 64 KiB。

Request operand 只求值一次。Call 可能挂起前，native progress 需要的 method、
URL、header 与 body 全部复制到 toolchain-owned bounded storage。Worker、callback
或 reactor registration 不得保留 Nomo-managed request value。

对 `send` 而言，timeout 或 structured cancellation 会中止 transfer 并释放全部
partial header/body。对 `open_stream` 而言，在 head 前失败不会发布 handle。Handle
发布后，同一 stream 最多只能 pending 一个 `read_text` 或 `next_sse` operation；
一旦选择 consumption mode 就不能更改。

Pull 的 idle timeout、transport/protocol/limit error 或 structured cancellation
会让 transport 不可复用，并把 stream 转为 closing。当前 operation 只释放一次
registration；caller 的 structured cleanup 调用幂等 `close_stream`，完成 late
native cleanup。发生这些 terminal outcome 后不能继续消费 stream。

`cancel_stream` 是 pull 之间放弃 response 的 immediate owner-local request。
`close_stream` 同步且幂等：移除 live registration、使 generation 失效，并把
callback/completion drain 转给 owner executor，自身不等待。Clean EOF/close
可以把 connection 还给 owner pool；early cancel、limit、TLS、protocol 或
transport failure 必须关闭 connection。

程序应在 open 成功后立即注册 `defer http.close_stream(stream)`。Blocking
migration 使用对应的 `close_stream_blocking` defer。EOF、cancel 与重复 close
不能重复释放 slot 或 native handle。

## 6. Ownership、Bounds 与 Connection Reuse

`HttpStream` 是 `Local`/`!Send`。它可以在 owner task frame 中跨 suspension，
但不能跨 structured spawn、channel publication、frozen sharing 或 shard
transfer。复制出的 handle 标识同一 slot，不会产生并发 polling authority。

`BlockingHttpStream` 同样是 `Local`/`!Send`；该限制只描述 compatibility
registry，不会授予它 async owner-table semantics。复制数值字段不会让任一 stream
identity 变得可安全 publication。

Current-thread baseline 使用固定 owner-local capacity：

- 最多 16 个 live buffered request 或 response stream；
- 每个 stream 最多一个 pending operation；
- 最多 64 个 live transport socket/completion registration；
- 最多 16 个 queued/running resolver job，与 async TCP 共用 bounded resolver
  worker contract；
- 每个 operation 最多 64 KiB response header；
- URL text 最多 16 KiB、request header 最多 128 个、序列化 request-header text
  最多 64 KiB、复制的 request body 最多 16 MiB；
- 每次 stream read 最多 1 MiB 加 3-byte UTF-8 carry；
- 最多 1 MiB pending SSE parser state；
- cumulative response 不超过 request 的 positive cap，且绝不超过 128 MiB；
- 每个 executor 最多 8 个 idle origin connection。

Table、queue、registration 或 idle-pool saturation 返回 `limit`，或关闭一个可选
idle connection；不能增长无界 list、buffer、thread set 或 queue。

Connection reuse 是一个 executor 的实现细节。Reuse key 包含 scheme、canonical
host、port、secret-safe 的 TLS trust-configuration generation 与 backend
所需的隔离 state。Request header、
authorization value、request body、response data、cookie 与 stream parser state
不能进入 connection key 或 idle entry。Idle eviction 必须确定性执行，且不能
淘汰 active transfer。Host runtime pool 不会让普通 Nomo string、array、map 或
ARC/COW value 变成 atomic。

## 7. Runtime Progress 与 Platform Contract

### 7.1 通用 operation lifecycle

一个 suspend HTTP operation：

1. 校验 public bound 与 owner identity；
2. 复制 native request state，并尝试 immediate progress；
3. 若已经完成，则不注册、不经过 ready queue，直接返回 ready；
4. 否则认领一个固定 operation slot 与所需的受限 transport registration；
5. 返回 `PENDING`；
6. 只在 transport progress、owner timer、cancellation 或 structured deadline
   后恢复；
7. 对每个 event 做 generation check，然后 rearm 或 complete；
8. 对 registration、native request copy、partial value 与 frame ownership
   精确释放一次。

一次 poll 只处理受限数量的 callback/byte，然后返回 ready queue。持续 ready 的
response 不能独占 current-thread executor。

### 7.2 Linux、macOS 与 BSD

每个 executor 拥有一个 libcurl multi handle 及其受限 connection cache。Runtime
使用 `curl_multi_socket_action`、socket callback 与 timer callback，把 libcurl
报告的 socket 注册到 epoll/kqueue；async worker 上不能调用
`curl_multi_poll`、`curl_multi_wait`、`curl_easy_perform` 或 blocking drive loop。

Hostname lookup 使用 RFC 0037 的 bounded resolver job，把最多 16 个有序 candidate
交给 libcurl，同时保留原 host 用于 TLS SNI 与 certificate verification。如果
动态加载的 libcurl 无法满足 socket/timer/resolution contract，async path 返回
`runtime_unavailable`，不能静默地在 worker 上解析。

Ambient proxy behavior 不属于第一版 async contract。第一版 runtime 禁用隐式
proxy discovery，避免把无界 system callback 或 credential-forwarding policy
偷渡进 executor。未来 proxy RFC 必须定义 bounds、secret、cancellation 与
connection-key isolation。

### 7.3 Windows

Owner executor 以 asynchronous mode 打开 WinHTTP。稳定的固定 operation slot
接收 WinHTTP status callback，并通过 owner wakeup source 发布受限、
generation-checked completion。System callback thread 可以运行 WinHTTP 本身，
但 Nomo 不为每个 request 创建一个 worker thread，callback 也不能访问
Nomo-managed value。

Session 与最多 8 个 idle origin connection 属于 owner。Request handle、read
buffer、callback context 与 late-close state 位于 coroutine frame 之外的稳定
slot。Cancellation 关闭 request handle、使 publication 失效，并在 slot reuse
前排空 late callback。任何 callback 都不能唤醒已经复用的 generation。

### 7.4 Browser WASM

在没有授予 fetch capability 时，`send`、`get`、`post` 与 `open_stream` 会在
求值 request、URL、body、timeout 或 limit operand 前返回 ready
`runtime_unavailable`。不会初始化 executor、registry、connection pool、
resolver 或 host import。Pull operation 无法获得可构造的 `HttpStream`。

Browser `fetch`/`ReadableStream` 需要独立 host-capability RFC，并保持相同 bounds
与 cancellation semantics。

## 8. Error、Diagnostic 与 Secret Safety

Async surface 保留 RFC 0022/0023 code，并增加 owner/runtime outcome：

- `invalid_request`；
- `runtime_unavailable`；
- `dns`；
- `connect`；
- `tls`；
- `timeout`；
- `response_too_large`；
- `protocol`；
- `transport`；
- `closed`；
- `busy`；
- `limit`；
- `reactor`。

Structured task cancellation 是 task outcome，不是可 catch 的 `HttpError`。
`closed` 表示 stale generation、closed stream 或 wrong owner；`busy` 表示同一
stream 上的第二个 operation；`limit` 表示固定 owner、resolver、completion 或
connection capacity；`reactor` 表示 backend registration/completion failure。

Error、diagnostic、scheduler trace、metrics label、owner slot 与 connection key
不能包含 header value、request body、URL query text、已接收
header/body/chunk/SSE data、bearer token、CA path、native handle 或无界
host-derived text。只有在不包含 value 或 source excerpt 时才可以标识
`Authorization` 等 header name。

| Code | 条件 | 必须提供的指引 |
| --- | --- | --- |
| `E0870` | 同步 caller 到达 unsuffixed async HTTP client operation | 标记函数为 `suspend`，或使用显式 `_blocking` compatibility 名称 |
| `E0890` | `HttpStream` 跨 owner/task/shard boundary | 保持 stream local，只发送 owned decoded data |
| `E0891` | suspend call graph 到达 `_blocking` HTTP client 或 blocking server operation | 使用 suspend client，或显式隔离 deliberate blocking work |
| `E0892` | target 缺少所需 HTTP transport capability | 指出 target 与已实现 backend phase，不得包含 source operand value |

## 9. Compiler 与 C99 Lowering

`send`、`get`、`post`、`open_stream`、`read_text` 与 `next_sse` 是 suspend
intrinsic。第一版 lowering 要求 direct call 必须 `let`-bound，operand 只求值
一次，并在 RFC 0031 stackless ABI 下使用 typed start/resume/cancel
registration。

跨 pending start 保留的 managed request value 具有显式 frame ownership bit，
并在 ready、error、timeout、cancellation、panic 与 enclosing-frame drop 路径
只释放一次。`HttpStream` 本身是 opaque scalar identity；返回的 status/header
value 遵守普通 task-local ARC/COW 规则。

Ready validation failure、browser unsupported、stale/closed handle、已缓冲
chunk/event、EOF 与 already-complete transport path 不分配 coroutine node，也
不把 task 入队。真实 pending operation 最多使用一个 coroutine frame 加固定
owner slot。

Suspend surface 落地时，`E0891` 只移除新的 unsuffixed client operation 与
immediate async-handle close/cancel。全部 `_blocking` client call 与 blocking
server progress 继续隔离。未使用 suspend HTTP 的程序不产生 executor、reactor、
resolver、async HTTP table、connection pool、callback 或 atomic support。

## 10. Metrics 与 Acceptance Evidence

版本化 counter 至少包括：

- request/stream start、ready completion、pending completion、error、timeout 与
  cancellation；
- response-head、body-chunk 与 SSE-event delivery；
- connection create、clean reuse、idle eviction 与 forced close；
- live/peak HTTP operation、stream、connection、resolver job、registration 与
  retained request/response/parser byte；
- reactor registration/deregistration/reregistration 与 Windows late-callback
  drain。

Immediate validation/browser/stale/buffered/EOF path 要求 registration 与 queue
traffic 为零。每个 success、HTTP error status、transport error、limit、timeout、
cancellation、panic、close 与 shutdown fixture 结束时，live operation、stream、
resolver job、registration、late callback 与 retained byte counter 都必须为零。

Native integration test 使用本地 plain 与生成证书的 TLS fixture，不使用真实 API
key，覆盖：

- verified HTTPS、host-name failure、自定义 authorization/content header，以及
  response status/header/body；
- immediate 与 pending DNS/connect/TLS/send/head/body progress；
- keep-alive reuse，且 authorization/body/header state 不泄漏；
- split UTF-8、全部已接受 SSE line/framing case、`[DONE]`、EOF 与 limit；
- zero/positive request/idle deadline、enclosing deadline、每个 transport phase
  的 structured cancellation、显式 cancel/close、late completion、复制的 stale
  handle 与 slot reuse；
- 精确 owner/registration/resolver/connection saturation；
- compatibility cleanup 回归，包括 ASAN 或等价 native 证据，证明每个
  easy/request handle 只有一个 cleanup owner；
- Linux epoll、macOS kqueue 与 Windows asynchronous WinHTTP native execution；
- browser pre-evaluation capability rejection 与零 host import；
- 单核与低内存 connection-idle/cancellation storm。

RFC 0034 公平报告会固定同一 Go 版本、TLS fixture、certificate validation、
request/response payload、keep-alive policy、SSE event、cancellation schedule、
core/fd/memory limit 与 validation work，记录 throughput、p50/p99/p999、CPU、RSS、
fd/handle/thread count、live idle connection 与 retained buffer。第一份正确结果
只作为证据；完整矩阵与 controlled-host gate 前不能声称性能优势。

## 11. 分阶段交付

| 切片 | 必须实现的行为 | 状态 |
| --- | --- | --- |
| P2-HTTP-A | public suspend/handle/migration contract、`E0870`/`E0890`/`E0891`、typed lowering ABI、blocking compatibility cleanup/sanitizer 回归与 benchmark fixture | 由 [`nomo#61`](https://github.com/nomo-lang/nomo/pull/61) 实现 |
| P2-HTTP-B | Unix buffered send/open 通过 owner-local curl multi、bounded resolver、TLS fixture、connection reuse、timeout/cancel 与精确 lifecycle counter | Planned |
| P2-HTTP-C | Unix incremental text/SSE pull、terminal cancellation、slot reuse、limit 与 epoll/kqueue native stress | Planned |
| P2-HTTP-D | asynchronous WinHTTP send/stream parity、owner wakeup、bounded connection reuse、late-callback drain 与 Windows native stress | Planned |
| P2-HTTP-E | browser pre-evaluation unsupported boundary 与 zero-import release-WASM 证据 | Planned |
| P2-HTTP-F | Nomo OpenAI-compatible buffered/SSE 示例、saturation/low-memory storm 与 RFC 0034 HTTP/SSE report | Planned |

本 RFC 已先以 `Proposed` 合并，之后才开始 P2-HTTP-A。后续每个 implementation slice
通过聚焦 signed branch/PR 落地，并包含 Nomo example、compiler/CLI test、双语
stdlib/SPEC/docs 更新、native platform 证据与精确 cleanup counter。

P2-HTTP-A 已建立 public direct-style suspend ABI、Local owner handle、blocking
compatibility 名称、诊断、typed lowering boundary 与 zero-thread ready placeholder；
它没有实现 native curl-multi/WinHTTP transport progress、browser capability closure
或 P2-HTTP-F resource/performance report，这些仍属于 P2-HTTP-B–F。

全部所需 platform、correctness、resource、compatibility 与公平 benchmark gate
完成前，本 RFC 保持 `Proposed`。仅落地文档或单个实现切片不会让它变为
`Accepted`。

## 12. 备选与风险

| 备选 | 不选择原因 |
| --- | --- |
| 把现有同步 pull 包进 coroutine frame | 仍会阻塞 executor，并保留不安全 global registry |
| 直接在 async TCP 上实现 HTTPS | 重复实现已交给成熟 runtime 的 TLS、certificate、HTTP framing 与 platform trust |
| 每个 request/stream 使用一个 blocking worker | 每个 mostly-idle Agent connection 都占用 thread 与 stack |
| 用全局锁把 `HttpStream` 变成 Send | 增加 contention，模糊 close ownership，也不会让 callback 或 managed value 安全 transfer |
| 立即暴露 public client/pool | 在 implicit bounded owner-local reuse contract 被证明前扩张 v0.1 API |
| 保留 unsuffixed blocking 并永久增加 `_async` 名称 | 产生两套长期 API，违背 direct-style effect migration |

风险包括动态 libcurl capability 差异、resolver/callback race、backend-specific
connection reuse、early-cancel TLS state、retained secret buffer、cleanup-owner 错误与
preview source breakage。显式 compatibility 名称、固定 owner slot、generation
check、bounded resolver job、统一 operation state machine、native fixture、
sanitizer 证据与精确 counter 用于缓解这些风险。

## 13. v0.1 影响与开放后续

本 RFC 提供 Nomo-native CLI Agent 所需的 nonblocking model-call transport，但
不实现 Agent 产品，也不要求 application C FFI。Toolchain/runtime 使用 libcurl、
WinHTTP、system resolver 与 platform reactor 仍属于内部实现边界。

Async HTTP server accept/respond、public proxy 配置、cookie、redirect policy、
binary buffer、request streaming、WebSocket、browser fetch、HTTP/2 tuning 与
cross-shard handle transfer 仍是独立后续，不能从本 client RFC 中推导。

## 14. 决议

采用以上 bounded owner-affine contract 与分阶段 migration。禁止阻塞 executor
worker、保留 process-global stream registry、为每个 request 创建一个 thread、
让 host callback 保留 Nomo-managed value、通过 connection cache 共享
authorization state、暴露 raw transport handle，或只凭 generated C 推断
platform/performance readiness。

## 15. 参考

- [RFC 0022：结构化 HTTP client 与 toolchain-owned host runtime](./0022-structured-http-client-and-host-runtime.md)
- [RFC 0023：Pull-based HTTP streaming 与 SSE](./0023-pull-based-http-streaming-and-sse.md)
- [RFC 0031：Direct-style suspend function 与 structured concurrency](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0032：Sharded executor、reactor 与 blocking pool](./0032-sharded-executor-reactor-and-blocking-pool.md)
- [RFC 0034：Async runtime acceptance 与 benchmark gate](./0034-async-runtime-acceptance-and-benchmark-gates.md)
- [RFC 0037：Owner-affine async TCP client 与 blocking migration](./0037-owner-affine-async-tcp-client-and-blocking-migration.md)
