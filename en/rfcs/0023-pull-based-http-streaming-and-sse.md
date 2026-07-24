# RFC 0023: Pull-Based HTTP Text Streaming and SSE

> Language: [中文](../../zh-CN/rfcs/0023-pull-based-http-streaming-and-sse.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0023 |
| Title | Pull-based HTTP text streaming and SSE |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-24 |
| Implementation | Implemented by [nomo PR #12](https://github.com/nomo-lang/nomo/pull/12); acceptance gates passed on 2026-07-24 |
| Topics | HTTP, HTTPS, streaming, SSE, cancellation, timeout, secrets, C backend |
| Related RFCs | [RFC 0003](./0003-arc-cow-runtime-cost.md), [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md), [RFC 0017](./0017-target-triples-and-cross-compilation.md), [RFC 0022](./0022-structured-http-client-and-host-runtime.md) |

---

## 1. Summary

Nomo v0.1 extends the accepted structured HTTP client with bounded,
pull-based UTF-8 response streaming and Server-Sent Events (SSE). A caller
opens one response, reads the response head, and then explicitly pulls either
text chunks or parsed SSE events. Every stream has a header deadline, an idle
read timeout, a cumulative response limit, explicit close/cancel operations,
and secret-safe errors.

This slice does not add `async`/`await`, background Nomo tasks, cross-thread
cancellation, or binary streaming. The synchronous pull API supplies
backpressure naturally and keeps the existing C99 backend and non-atomic
managed-value model intact.

## 2. Motivation

[RFC 0022](./0022-structured-http-client-and-host-runtime.md) established the
non-streaming model-call loop: verified HTTPS, custom authorization headers,
bounded response bodies, stable transport errors, and an OpenAI-compatible
fixture. It deliberately uses `http.send`, which returns only after the full
body has been buffered.

OpenAI-compatible streaming responses use `text/event-stream`. A CLI agent
must show tokens as they arrive, stop consuming when the application decides
it has enough data, detect a stalled peer, and place a hard upper bound on both
the complete response and one SSE event. Requiring an application to parse
arbitrary transport chunks or own libcurl/WinHTTP state would recreate the
unsafe boundary rejected by RFC 0022.

Nomo does not yet have a task model, atomic managed values, or a safe
cross-thread ownership contract. Therefore the first streaming API must be
synchronous and pull-based rather than hiding a worker thread or introducing a
large syntax/runtime expansion.

## 3. Implementation Evidence and Remaining Gaps

The accepted implementation landed through
[nomo PR #12](https://github.com/nomo-lang/nomo/pull/12) on 2026-07-24.

| Surface | Accepted evidence | Remaining gap |
| --- | --- | --- |
| Public API | `std.http` exposes an opaque `HttpStream`, bounded text pulls, parsed SSE events, and explicit cancel/close while preserving RFC 0022 APIs | Binary chunks and streaming request bodies remain deferred |
| Timeout | `HttpRequest.timeout_millis` bounds response-head acquisition and `idle_timeout_millis` bounds each later pull | Cross-task interruption awaits a task model |
| Limits | The native registry enforces cumulative response, per-chunk, per-event, and response-header caps | Configurable connection-pool and compression policy remain deferred |
| Native runtime | Unix-like targets use a paused/resumed libcurl multi handle; Windows retains a WinHTTP request and normalizes late reads | Browser networking requires a separate host-capability design |
| Cancellation | Close/cancel and stale copied handles are idempotent; early cancel closes the connection | Cancellation remains cooperative between blocking pulls |
| Browser WASM | Every streaming network entry point rejects with `NOMO-WASM-003` before argument evaluation | `fetch`/`ReadableStream` is not granted in v0.1 |
| Tests and example | Split UTF-8/SSE fixtures cover framing, limits, timeout, cancellation, secret redaction, Windows execution, and an OpenAI-compatible `[DONE]` loop | Structured JSON construction remains the next independent P1 slice |

## 4. Detailed Design

### 4.1 Public Nomo API

The existing `HttpRequest`, `HttpHeader`, `HttpError`, `http.send`,
`http.get`, and `http.post` APIs remain source-compatible. The streaming
extension is:

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

`open_stream` validates and sends the same `GET` or `POST` request accepted by
`send`, then returns after response headers are available. HTTP 4xx and 5xx
remain successful transport responses and are visible through `status`.

For `open_stream`, `request.timeout_millis` is the deadline for connecting,
performing TLS, sending the request, and receiving the response head.
`idle_timeout_millis` is the maximum time that each later consuming operation
may wait without receiving response progress. Both values must be positive and
no greater than 15 minutes.

`request.max_response_bytes` is the cumulative decoded body limit across all
reads. It retains RFC 0022's 128 MiB hard ceiling. `max_chunk_bytes` must be at
least 4 bytes and no greater than 1 MiB, so one UTF-8 scalar always fits.
`read_text` waits until decoded text is available, the stream ends, or an
error/idle timeout occurs. End of stream is reported as
`{ data: "", done: true }`; a non-final result always contains non-empty
`data`.

The returned chunks are valid UTF-8 text and never split a UTF-8 scalar.
Embedded NUL and invalid UTF-8 produce `protocol`. Binary-body streaming needs
a future byte-buffer type and is not part of this RFC.

### 4.2 Stream Ownership, Close, and Cancellation

`HttpStream.handle` is an opaque toolchain-owned registry identifier, not a
native pointer. Copying a Nomo value may copy the identifier, but it does not
duplicate the network operation. `close_stream` and `cancel_stream` are
idempotent, so copied stale handles cannot double-free native state.

`close_stream` releases a completed or abandoned response. `cancel_stream`
marks an unfinished response as intentionally abandoned and closes its native
transport as soon as the synchronous caller regains control. Because v0.1 has
no concurrent task model, cancellation is cooperative between consuming
calls; it does not promise that another Nomo thread can interrupt a currently
blocked `read_text` or `next_sse`. The idle timeout is the hard bound on that
blocking interval.

A program should register `defer http.close_stream(stream)` immediately after
open. Calling close after cancel or after end-of-stream is harmless. Reads
after close/cancel are invalid and return `invalid_request`.

### 4.3 SSE Semantics

`next_sse` incrementally parses UTF-8 `text/event-stream` data from the same
transport:

- CRLF, CR, and LF line endings are accepted.
- A leading UTF-8 BOM is ignored once.
- Comment lines beginning with `:` are ignored.
- Consecutive `data:` fields are joined with `\n`, with the final synthetic
  newline removed when the event is dispatched.
- `event:` defaults to `message`; `id:` updates the event identifier.
- A decimal non-negative `retry:` value becomes `Some(milliseconds)`;
  malformed retry fields are ignored.
- A blank line dispatches an event. EOF dispatches a final pending event.
- Application sentinels such as `[DONE]` remain ordinary `data`; the Nomo
  application decides what they mean.

`max_event_bytes` is a positive decoded-byte limit with a 1 MiB hard ceiling.
It covers buffered field names/values and joined data for one pending event.
Exceeding it returns `response_too_large` and closes the stream.

The first call to `read_text` or `next_sse` selects the stream's consumption
mode. Mixing raw-text and SSE consumption on one handle returns
`invalid_request`. This avoids ambiguous ownership of bytes already buffered
inside the SSE decoder.

### 4.4 Errors and Secret Handling

Streaming reuses RFC 0022's stable `HttpError.code` set:
`invalid_request`, `runtime_unavailable`, `dns`, `connect`, `tls`, `timeout`,
`response_too_large`, `protocol`, and `transport`. Idle expiration uses
`timeout`; invalid UTF-8 and malformed transport framing use `protocol`.

No error, diagnostic, default log, or handle registry entry may contain
request-header values, request bodies, URL query text, previously received SSE
data, or streamed response chunks. Tests use distinct sentinels for each
surface and assert that failures and browser capability errors disclose none
of them.

### 4.5 Toolchain-Owned Native Runtime

Applications continue to use canonical Nomo source and declare no C FFI,
native source, or linker metadata.

- Unix-like targets extend the dynamically loaded libcurl adapter with the
  multi interface required to pause/resume one easy handle without a
  background Nomo thread. The runtime drives only the selected handle until
  headers, text, EOF, timeout, or error become observable.
- Windows retains a WinHTTP request handle and reads response data on demand.
- The opaque registry owns all native handles, text carry bytes, counters, and
  SSE parser state. Every exit path removes or preserves registry state
  according to the public operation's result.

The implementation must not retain Nomo-managed request values after
`open_stream` returns. Any data needed by the native operation is copied into
runtime-owned storage and released on close, cancel, EOF, or error.

The browser WASM interpreter rejects all new network entry points with
`NOMO-WASM-003` before evaluating request or stream arguments. Browser
`fetch`/`ReadableStream` integration remains a separate host-capability RFC.

## 5. Alternatives

| Option | Advantages | Disadvantages | Direction |
| --- | --- | --- | --- |
| Synchronous pull handle | Natural backpressure, bounded blocking, fits C99 and current ownership | No cross-thread interrupt while blocked | Accepted for v0.1 |
| Callback per chunk/event | Familiar streaming shape | Requires callback lifetime, reentrancy, and captured-value ownership rules not yet present | Rejected for v0.1 |
| Background worker plus queue | Can interrupt and receive concurrently | Requires threads, atomics, synchronization, and thread-safe managed values | Defer to task-model RFC |
| Add `async`/`await` first | General language solution | Expands parser, type system, lowering, runtime, and cancellation semantics before the Agent loop is proven | Rejected as P1 scope |
| Buffer full body and split afterward | Reuses RFC 0022 unchanged | Not incremental and cannot stop early | Rejected |

## 6. Drawbacks and Risks

- Opaque handles require a runtime registry and stale-handle validation.
- libcurl multi and WinHTTP expose different readiness/error behavior that
  must be normalized.
- Cooperative cancellation cannot interrupt the current blocking read; callers
  must choose a finite idle timeout.
- Text-only chunks do not support arbitrary binary bodies.
- SSE has edge cases around split line endings, UTF-8 boundaries, BOM, and
  multi-line data that require deterministic parser tests.

## 7. Impact on v0.1 Scope

This RFC is the P1 transport slice needed for an interactive native CLI agent.
It does not add an Agent product, parallel tool execution, reusable connection
pools, browser networking, binary streaming, WebSockets, or async syntax.

The next independent P1 slices remain controlled long-lived child processes
and a structured JSON value model. They require separate RFCs before their
public APIs are fixed.

## 8. Acceptance Gate

All acceptance gates passed on 2026-07-24:

1. Canonical `std.http` source, compiler lowering, generated C ABI, docs, and
   both v0.1 specifications expose the same streaming API and semantics in
   this accepted change set.
2. Existing RFC 0022 buffered HTTP/HTTPS behavior remains source-compatible and
   all prior tests continue to pass.
3. A localhost generated-certificate TLS fixture sends headers and SSE fields
   across deliberately split writes and proves incremental delivery without
   public network access or a real API key.
4. Deterministic tests cover UTF-8 split boundaries, CR/LF variants, BOM,
   comments, multi-line data, `id`, `event`, `retry`, EOF dispatch, `[DONE]`,
   per-event cap, per-chunk cap, cumulative cap, and idle timeout.
5. Close/cancel are idempotent, early cancellation closes the native
   connection, stale handles do not double-free, and all failure paths release
   registry/native state.
6. Secret-sentinel tests prove request headers, bodies, queries, received
   chunks, and SSE data never appear in errors, diagnostics, or default logs.
7. A Nomo OpenAI-compatible streaming example consumes fixture events
   incrementally and stops on `[DONE]`.
8. Formatting, Clippy, unit/CLI integration tests, browser-WASM capability
   behavior, macOS arm64-to-x86_64 cross-build, and Linux
   x86_64-to-arm64 cross-build passed in
   [full CI run 30098333656](https://github.com/nomo-lang/nomo/actions/runs/30098333656);
   native Windows buffered and streaming compile/run paths passed in
   [PR smoke run 30098027086](https://github.com/nomo-lang/nomo/actions/runs/30098027086).
9. The implementation landed through signed commits on a child branch and
   merged PR #12. The post-merge
   [main CI run 30098552254](https://github.com/nomo-lang/nomo/actions/runs/30098552254)
   also passed.

## 9. Deferred Follow-Ups

- Cross-task and cross-thread cancellation after a task model exists.
- Binary response chunks and a dedicated byte-buffer type.
- Connection pooling, proxy policy, redirects, and compression controls.
- Browser `fetch`/`ReadableStream` host capabilities.
- Streaming request bodies, WebSockets, and HTTP/2-specific controls.

## 10. References

- `std/src/http.nomo`
- `crates/nomo_compiler/src/builtins/builtins_http.rs`
- `crates/nomo_codegen_c/src/runtime/host_http_client.c`
- `crates/nomo_codegen_c/src/runtime/host_http_stream.c`
- `crates/nomo/tests/cli_project.rs`
- `crates/nomo/tests/examples.rs`
- `crates/nomo_wasm/src/lib.rs`
- `examples/openai_streaming`
- [nomo PR #12](https://github.com/nomo-lang/nomo/pull/12)
- [RFC 0003](./0003-arc-cow-runtime-cost.md)
- [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)
- [RFC 0017](./0017-target-triples-and-cross-compilation.md)
- [RFC 0022](./0022-structured-http-client-and-host-runtime.md)
