# RFC 0023：Pull-Based HTTP 文本 Streaming 与 SSE

> 语言 / Language: 中文 | [English](../../en/rfcs/0023-pull-based-http-streaming-and-sse.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0023 |
| 标题 | Pull-based HTTP 文本 streaming 与 SSE |
| 状态 | Proposed（已提案） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-24 |
| 实现状态 | 尚未接受；`std.http` 当前会缓冲完整 response body |
| 关联主题 | HTTP、HTTPS、streaming、SSE、取消、timeout、secret、C backend |
| 关联 RFC | [RFC 0003](./0003-arc-cow-runtime-cost.md)、[RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)、[RFC 0017](./0017-target-triples-and-cross-compilation.md)、[RFC 0022](./0022-structured-http-client-and-host-runtime.md) |

---

## 1. 摘要

Nomo v0.1 应在已接受的结构化 HTTP client 上增加受限、pull-based 的 UTF-8
response streaming 与 Server-Sent Events（SSE）。调用方打开一个 response，读取
response head，然后显式拉取文本 chunk 或解析后的 SSE event。每个 stream 都具有
header deadline、idle read timeout、累计 response 上限、显式 close/cancel 操作与
secret-safe error。

本切片不增加 `async`/`await`、后台 Nomo task、跨线程取消或 binary streaming。
同步 pull API 自然提供 backpressure，并保持现有 C99 backend 与非原子 managed
value 模型不变。

## 2. 动机

[RFC 0022](./0022-structured-http-client-and-host-runtime.md) 已建立非流式模型调用
闭环：verified HTTPS、自定义 authorization header、受限 response body、稳定
transport error 与 OpenAI-compatible fixture。它刻意使用 `http.send`，因此只有
完整 body 被缓冲后才返回。

OpenAI-compatible streaming response 使用 `text/event-stream`。CLI Agent 需要在
token 到达时立刻显示、在应用决定数据已足够时停止消费、检测 stalled peer，并对
完整 response 与单个 SSE event 都设置硬上限。若要求应用自己解析任意 transport
chunk 或持有 libcurl/WinHTTP 状态，就会重新制造 RFC 0022 已拒绝的 unsafe
boundary。

Nomo 尚无 task model、原子 managed value 或安全的跨线程 ownership contract。
因此第一个 streaming API 必须同步且 pull-based，不能暗中引入 worker thread 或
一次扩张大量语法/runtime。

## 3. 当前证据与 Gap

| 表面 | 当前证据 | P1 缺口 |
| --- | --- | --- |
| 公共 API | `http.send(HttpRequest)` 返回一次性缓冲的 `HttpResponse` | 没有 response handle、增量 read、SSE event 或提前停止 |
| Timeout | `HttpRequest.timeout_millis` 是非流式请求的总 deadline | 长生命周期 stream 还需要 per-read idle timeout |
| 上限 | `max_response_bytes` 限制缓冲 body | Streaming 需要累计 cap、per-chunk cap 与 per-event cap |
| Native runtime | Unix-like target 使用 libcurl easy，Windows 使用 WinHTTP | 控制返回 Nomo 前 runtime state 已被销毁 |
| 取消 | 不存在 stream handle | 应用不能主动停止进行中的 response |
| Browser WASM | 网络访问以 `NOMO-WASM-003` 拒绝 | 新 streaming entry point 必须维持相同 sandbox boundary |
| 测试 | RFC 0022 覆盖本地 TLS 与非流式 failure path | 没有 delayed chunk、event framing、idle timeout、early close 或 streamed secret 测试 |

## 4. 详细设计

### 4.1 公共 Nomo API

现有 `HttpRequest`、`HttpHeader`、`HttpError`、`http.send`、`http.get` 与
`http.post` API 保持源码兼容。Streaming 扩展为：

```nomo
pub struct HttpStream {
    handle: u64
    pub status: i64
    pub headers: Array<HttpHeader>
}

pub struct HttpStreamChunk {
    pub data: string
    pub done: bool
}

pub struct SseEvent {
    pub event: string
    pub data: string
    pub id: string
    pub retry_millis: Option<u64>
}

http.open_stream(
    request: HttpRequest,
    idle_timeout_millis: u64
) -> Result<HttpStream, HttpError>

http.read_text(
    stream: HttpStream,
    max_chunk_bytes: u64
) -> Result<HttpStreamChunk, HttpError>

http.next_sse(
    stream: HttpStream,
    max_event_bytes: u64
) -> Result<Option<SseEvent>, HttpError>

http.cancel_stream(stream: HttpStream) -> void
http.close_stream(stream: HttpStream) -> void
```

`open_stream` 校验并发送 `send` 已接受的同一类 `GET` 或 `POST` request，在
response header 可用后返回。HTTP 4xx 与 5xx 继续属于成功 transport response，
通过 `status` 暴露。

对 `open_stream` 而言，`request.timeout_millis` 是 connect、TLS、发送 request 与
接收 response head 的 deadline。`idle_timeout_millis` 是后续每个消费操作在没有
response progress 时允许等待的最长时间。两者必须大于零且不超过 15 分钟。

`request.max_response_bytes` 是所有 read 的累计 decoded body 上限，并保留 RFC
0022 的 128 MiB hard ceiling。`max_chunk_bytes` 必须大于零且不超过 1 MiB。
`read_text` 会等待 decoded text、stream 结束、error 或 idle timeout。Stream 结束
报告为 `{ data: "", done: true }`；非最终结果的 `data` 必须非空。

返回 chunk 是合法 UTF-8 文本，且不会切断 UTF-8 scalar。嵌入 NUL 或非法 UTF-8
返回 `protocol`。Binary body streaming 需要未来的 byte-buffer type，不属于本
RFC。

### 4.2 Stream Ownership、Close 与 Cancellation

`HttpStream.handle` 是工具链托管的 opaque registry identifier，不是 native
pointer。复制 Nomo value 可能复制 identifier，但不会复制网络操作。
`close_stream` 与 `cancel_stream` 均为幂等，因此复制出的 stale handle 不会导致
double-free。

`close_stream` 释放已完成或被放弃的 response。`cancel_stream` 把未完成 response
标记为应用主动放弃，并在同步调用方重新取得控制时立即关闭 native transport。
由于 v0.1 没有并发 task model，取消发生在消费调用之间；本 RFC 不承诺另一个
Nomo thread 可以中断正在阻塞的 `read_text` 或 `next_sse`。Idle timeout 是该阻塞
区间的硬上限。

程序应在 open 后立即注册 `defer http.close_stream(stream)`。Cancel 或 EOF 后再
close 是安全的。Close/cancel 后继续 read 属于非法操作，返回
`invalid_request`。

### 4.3 SSE 语义

`next_sse` 在同一 transport 上增量解析 UTF-8 `text/event-stream`：

- 接受 CRLF、CR 与 LF line ending。
- 只忽略一次开头的 UTF-8 BOM。
- 忽略以 `:` 开头的 comment line。
- 连续 `data:` field 以 `\n` 拼接；dispatch 时移除最终合成 newline。
- `event:` 默认值为 `message`；`id:` 更新 event identifier。
- 十进制非负 `retry:` 值成为 `Some(milliseconds)`；忽略非法 retry field。
- 空行 dispatch event；EOF 会 dispatch 最后一个 pending event。
- `[DONE]` 等应用 sentinel 保持普通 `data`，由 Nomo 应用解释。

`max_event_bytes` 是正数 decoded-byte limit，hard ceiling 为 1 MiB。它覆盖一个
pending event 中已缓冲的 field name/value 与拼接后的 data。超限返回
`response_too_large` 并关闭 stream。

第一次调用 `read_text` 或 `next_sse` 时会选择 stream 的消费模式。在同一 handle
上混合 raw-text 与 SSE 消费返回 `invalid_request`，避免已被 SSE decoder 缓冲的
byte 出现 ownership 歧义。

### 4.4 Error 与 Secret 处理

Streaming 复用 RFC 0022 的稳定 `HttpError.code`：
`invalid_request`、`runtime_unavailable`、`dns`、`connect`、`tls`、`timeout`、
`response_too_large`、`protocol` 与 `transport`。Idle expiration 使用
`timeout`；非法 UTF-8 与异常 transport framing 使用 `protocol`。

Error、diagnostic、默认 log 与 handle registry entry 均不得包含 request-header
value、request body、URL query text、已经接收的 SSE data 或 streamed response
chunk。测试为每个表面使用不同 sentinel，并断言 failure 与 browser capability
error 都不会泄露它们。

### 4.5 工具链托管 Native Runtime

应用继续使用 canonical Nomo source，不声明 C FFI、native source 或 linker
metadata。

- Unix-like target 扩展动态加载的 libcurl adapter，使用 multi interface 在没有
  后台 Nomo thread 的情况下 pause/resume 一个 easy handle。Runtime 只驱动选中的
  handle，直到 header、text、EOF、timeout 或 error 可观察。
- Windows 保留 WinHTTP request handle，并按需读取 response data。
- Opaque registry 拥有所有 native handle、text carry byte、counter 与 SSE parser
  state。每条退出路径根据公共操作结果删除或保留 registry state。

`open_stream` 返回后，实现不得继续持有 Nomo-managed request value。Native 操作
需要的数据必须复制进 runtime-owned storage，并在 close、cancel、EOF 或 error 时
释放。

Browser WASM interpreter 对全部新网络 entry point 都应在求值 request/stream
参数前返回 `NOMO-WASM-003`。Browser `fetch`/`ReadableStream` integration 继续
留给独立 host-capability RFC。

## 5. 备选方案

| 方案 | 优点 | 缺点 | 倾向 |
| --- | --- | --- | --- |
| 同步 pull handle | 自然 backpressure、受限阻塞、适配 C99 与当前 ownership | 阻塞期间无法跨线程 interrupt | v0.1 提案 |
| 每个 chunk/event 回调 | Streaming shape 常见 | 需要尚不存在的 callback lifetime、reentrancy 与 captured-value ownership rule | v0.1 拒绝 |
| 后台 worker + queue | 可并发接收和 interrupt | 需要 thread、atomic、同步与 thread-safe managed value | 推迟到 task-model RFC |
| 先增加 `async`/`await` | 通用语言方案 | 在 Agent loop 被证明前扩张 parser、type system、lowering、runtime 与取消语义 | P1 范围拒绝 |
| 缓冲完整 body 后再 split | 完全复用 RFC 0022 | 不增量，也不能提前停止 | 拒绝 |

## 6. 缺点与风险

- Opaque handle 需要 runtime registry 与 stale-handle 校验。
- libcurl multi 与 WinHTTP 的 readiness/error 行为不同，必须归一化。
- Cooperative cancellation 无法中断当前 blocking read；调用方必须选择有限 idle
  timeout。
- Text-only chunk 不支持任意 binary body。
- SSE 在拆分 line ending、UTF-8 boundary、BOM 与 multi-line data 上存在大量
  edge case，需要确定性 parser 测试。

## 7. 对 v0.1 范围的影响

本 RFC 是交互式原生 CLI Agent 所需的 P1 transport 切片。它不增加 Agent 产品、
并行 tool execution、reusable connection pool、browser 网络、binary streaming、
WebSocket 或 async 语法。

接下来的独立 P1 切片仍是受控长生命周期 child process 与结构化 JSON value
model；其公共 API 固化前需要各自 RFC。

## 8. Acceptance Gate

以下 gate 全部通过前，本 RFC 保持 `Proposed`：

1. Canonical `std.http` source、compiler lowering、生成 C ABI、文档与中英文 v0.1
   规格暴露完全一致的 streaming API 与语义。
2. 现有 RFC 0022 缓冲式 HTTP/HTTPS 行为保持源码兼容，既有测试全部通过。
3. 使用生成证书的 localhost TLS fixture 在刻意拆分的 write 中发送 header 与 SSE
   field，证明无需公网或真实 API key 即可增量交付。
4. 确定性测试覆盖 UTF-8 split boundary、CR/LF 变体、BOM、comment、multi-line
   data、`id`、`event`、`retry`、EOF dispatch、`[DONE]`、per-event cap、
   per-chunk cap、累计 cap 与 idle timeout。
5. Close/cancel 幂等，early cancellation 关闭 native connection，stale handle
   不 double-free，全部 failure path 释放 registry/native state。
6. Secret-sentinel 测试证明 request header、body、query、已接收 chunk 与 SSE data
   不会进入 error、diagnostic 或默认 log。
7. Nomo OpenAI-compatible streaming 示例增量消费 fixture event，并在 `[DONE]`
   停止。
8. Formatting、Clippy、unit/CLI integration test、browser-WASM capability
   behavior、macOS/Linux cross-build 与 Windows native compile/run test 全部通过。
9. 实现必须通过签名提交、子分支、PR review 与 required CI 合入；之后 RFC 才能转
   `Accepted`。

## 9. 推迟的后续工作

- Task model 建立后的 cross-task/cross-thread cancellation。
- Binary response chunk 与专用 byte-buffer type。
- Connection pooling、proxy policy、redirect 与 compression control。
- Browser `fetch`/`ReadableStream` host capability。
- Streaming request body、WebSocket 与 HTTP/2-specific control。

## 10. 参考

- `std/src/http.nomo`
- `crates/nomo_compiler/src/builtins/builtins_http.rs`
- `crates/nomo_codegen_c/src/runtime/host_http_client.c`
- `crates/nomo_wasm/src/interpreter.rs`
- [RFC 0003](./0003-arc-cow-runtime-cost.md)
- [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)
- [RFC 0017](./0017-target-triples-and-cross-compilation.md)
- [RFC 0022](./0022-structured-http-client-and-host-runtime.md)
