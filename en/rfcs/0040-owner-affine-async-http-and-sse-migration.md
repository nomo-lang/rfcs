# RFC 0040: Owner-Affine Async HTTP/HTTPS, SSE, and Blocking Migration

> Language: [中文](../../zh-CN/rfcs/0040-owner-affine-async-http-and-sse-migration.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0040 |
| Title | Owner-affine async HTTP/HTTPS, SSE, and blocking migration |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-27 |
| Topics | HTTP, HTTPS, TLS, SSE, async I/O, reactor, owner affinity, connection reuse, migration |
| Related RFCs | [RFC 0022](./0022-structured-http-client-and-host-runtime.md), [RFC 0023](./0023-pull-based-http-streaming-and-sse.md), [RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md), [RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md), [RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md), [RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md), [RFC 0037](./0037-owner-affine-async-tcp-client-and-blocking-migration.md) |

## 1. Summary

Nomo's structured HTTP/HTTPS client and pull-based response streaming gain
owner-affine, reactor-driven suspend paths. `http.send`, `http.get`,
`http.post`, `http.open_stream`, `http.read_text`, and `http.next_sse` become
direct-style suspend operations. The accepted TLS verification, structured
headers, response limits, UTF-8/SSE framing, stable errors, and secret
redaction rules from RFCs 0022 and 0023 do not change.

`HttpStream` becomes a generation-checked `Local`/`!Send` handle owned by one
executor. Unix-like targets drive a shared libcurl multi handle through
epoll/kqueue readiness and bounded DNS jobs. Windows uses asynchronous
WinHTTP status completion routed back to the owner executor. Neither path
blocks an async worker or creates one application thread per request.

The accepted synchronous client remains available for one preview migration
window through explicit `_blocking` names and `BlockingHttpStream`. The plain
HTTP server remains a quarantined blocking compatibility surface until a
focused server RFC replaces it.

This RFC is `Proposed`. It fixes the effect, ownership, transport, migration,
connection-reuse, cancellation, platform, and acceptance contracts before
implementation. It does not relabel the current synchronous pull loop as
async.

## 2. Current Audit

The accepted RFC 0022/0023 implementation is suitable for a bounded
single-threaded CLI call, but it cannot run on an async executor worker:

- buffered requests call libcurl easy or synchronous WinHTTP to completion;
- Unix stream open/read loops call `curl_multi_perform` and
  `curl_multi_poll`/`curl_multi_wait` on the caller;
- Windows stream open/read calls synchronous WinHTTP send, receive, and read;
- stream states live in a process-global linked list with a global numeric
  allocator and no executor owner or generation;
- each Unix stream owns a separate multi handle, so the accepted runtime does
  not provide a bounded owner-local connection pool;
- portable name resolution may block unless it is isolated from the async
  worker;
- close/cancel cannot be raced safely with a pending async callback because
  the compatibility implementation has no stable completion slot;
- wrapping any existing operation in a coroutine would still block unrelated
  tasks;
- the current Unix stream cleanup template invokes easy-handle cleanup twice,
  and the SSE size-error template repeats one message fragment. The blocking
  migration must add regression coverage and one cleanup owner rather than
  carrying these defects into the async table.

The current `E0891` quarantine is therefore correct. A real replacement must
integrate transport readiness/completion with the executor, preserve all
accepted protocol behavior, and end every success/error/cancellation path
with exact resource ownership.

## 3. Goals and Non-goals

### 3.1 Goals

1. Execute verified HTTP/HTTPS requests without blocking the async worker.
2. Incrementally consume bounded UTF-8 chunks and parsed SSE events with
   natural pull backpressure.
3. Keep request, response, stream, and connection memory explicitly bounded.
4. Make streams owner affine and reject cross-task/shard publication.
5. Define deadlines, structured cancellation, explicit cancel/close, late
   completion, and runtime shutdown exactly once.
6. Reuse connections within one executor without sharing ordinary Nomo values
   or authorization state across requests.
7. Preserve application-side freedom from C FFI while allowing the toolchain
   runtime to use libcurl, WinHTTP, and platform APIs.
8. Provide an explicit one-window blocking migration.

### 3.2 Non-goals

This RFC does not add HTTP server async accept/respond, WebSocket, arbitrary
streaming request bodies, binary response chunks, cookies, automatic
redirects, ambient proxy configuration, public TLS configuration, raw
socket/reactor access, a public `HttpClient`, cross-shard stream transfer, or
browser `fetch`.

It does not promise HTTP/2 multiplexing. A backend may negotiate HTTP/2 only
when it preserves the same bounds, isolation, cancellation, and fairness; the
first implementation may force HTTP/1.1 to keep one transfer independently
accounted.

## 4. Public Standard-Library Contract

### 4.1 Types

`HttpHeader`, `HttpRequest`, `HttpResponse`, `HttpStreamChunk`, `SseEvent`, and
`HttpError` retain RFCs 0022 and 0023. The handle identity splits:

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

`HttpStream` identifies the new owner table. `BlockingHttpStream` identifies
only the compatibility registry. The two types cannot be mixed.

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

pub fn cancel_stream(stream: HttpStream) -> void
pub fn close_stream(stream: HttpStream) -> void
```

Direct-style calls require a `suspend` caller. `get` and `post` retain the
accepted 30-second deadline and 8 MiB response-body limit by constructing one
structured request and invoking the same suspend engine.

`send` completes after the response body has been fully received within
`max_response_bytes`. `open_stream` completes after the final response head is
available and retains the transport in the owner table. HTTP 4xx and 5xx
remain successful transport responses visible through `status`.

`read_text` and `next_sse` preserve the RFC 0023 chunk, UTF-8, event, and
cumulative response limits. The stream's `idle_timeout_millis` bounds each
later pull. The effective deadline is the earlier of that idle deadline and
an enclosing structured deadline.

### 4.3 Blocking compatibility surface

For one preview migration window, the accepted synchronous implementation is
available as:

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
http.cancel_stream_blocking(stream: BlockingHttpStream) -> void
http.close_stream_blocking(stream: BlockingHttpStream) -> void
```

Every `_blocking` request or pull operation remains rejected by `E0891` in a
suspend call graph. A synchronous call to an unsuffixed client operation
receives `E0870` with guidance to mark the caller `suspend` or choose the
explicit blocking name. There is no effect overload or implicit runtime
switch.

`listen`, `accept`, and `respond_string` remain blocking server operations and
stay behind `E0891`. `close_server` and `close_exchange` remain immediate
compatibility cleanup calls. This RFC does not imply server owner affinity.

## 5. Request, Stream, and Cancellation Semantics

RFC 0022 validation remains normative:

- only `GET` and `POST`;
- only absolute `http://` and `https://` URLs without user-info or fragments;
- verified peer certificate and host name for HTTPS;
- custom safe headers including `Authorization` and `Content-Type`;
- runtime ownership of hop/framing headers;
- no automatic redirects;
- at most 16 KiB of URL text, 128 application headers, 64 KiB of serialized
  application-header text, and 16 MiB of request body;
- positive request deadlines through 15 minutes;
- positive response caps through the 128 MiB hard ceiling;
- a 64 KiB response-head limit.

Request arguments are evaluated once. Before a call can suspend, all method,
URL, headers, and body data needed by native progress is copied into
toolchain-owned bounded storage. A worker, callback, or reactor registration
never retains a Nomo-managed request value.

For `send`, timeout or structured cancellation aborts the transfer and releases
all partial headers/body. For `open_stream`, failure before the head publishes
no handle. After publication, only one `read_text` or `next_sse` operation may
be pending on the stream. Choosing one consumption mode remains permanent.

An idle timeout, transport/protocol/limit error, or structured cancellation of
a pull makes the transport non-reusable and transitions the stream to closing.
The current operation releases its registration exactly once; the caller's
structured cleanup invokes idempotent `close_stream` to finish late native
cleanup. It is not legal to resume consuming the stream after one of these
terminal outcomes.

`cancel_stream` is an immediate owner-local request to abandon a response
between pulls. `close_stream` is synchronous and idempotent: it removes live
registrations, invalidates the generation, and transfers any callback or
completion drain to the owner executor without waiting. Clean EOF/close may
return a connection to the owner pool; early cancel, limit, TLS, protocol, or
transport failure closes it.

A program registers `defer http.close_stream(stream)` immediately after a
successful open. The blocking migration uses the matching
`close_stream_blocking` defer. EOF, cancel, and repeated close do not
double-release a slot or native handle.

## 6. Ownership, Bounds, and Connection Reuse

`HttpStream` is `Local`/`!Send`. It may cross suspension in its owner task
frame, but it cannot cross structured spawn, channel publication, frozen
sharing, or shard transfer. A copied handle identifies the same slot and does
not grant concurrent polling authority.

`BlockingHttpStream` is also `Local`/`!Send`; that restriction documents the
compatibility registry rather than granting it async owner-table semantics.
Neither stream identity is made safe to publish by copying its numeric field.

The current-thread baseline uses fixed owner-local capacities:

- at most 16 live buffered requests or response streams;
- at most one pending operation per stream;
- at most 64 live transport socket/completion registrations;
- at most 16 queued/running resolver jobs, sharing the bounded resolver worker
  contract with async TCP;
- at most 64 KiB of response headers per operation;
- at most 16 KiB of URL text, 128 request headers, 64 KiB of serialized
  request-header text, and 16 MiB of copied request body;
- at most 1 MiB plus a three-byte UTF-8 carry per stream read;
- at most 1 MiB of pending SSE parser state;
- at most the request's positive cumulative response cap, never above
  128 MiB;
- at most eight idle origin connections per executor.

Table, queue, registration, or idle-pool saturation returns `limit` or closes
an otherwise optional idle connection. It never grows an unbounded list,
buffer, thread set, or queue.

Connection reuse is an implementation detail of one executor. The reuse key
includes scheme, canonical host, port, a secret-safe TLS trust-configuration
generation, and backend-required isolation state. Request headers,
authorization values, request bodies,
response data, cookies, and stream parser state are never stored in the
connection key or idle entry. Idle eviction is deterministic and never evicts
an active transfer. Ordinary Nomo strings, arrays, maps, and ARC/COW values do
not become atomic because the host runtime pools native connections.

## 7. Runtime Progress and Platform Contract

### 7.1 Common operation lifecycle

A suspend HTTP operation:

1. validates public bounds and owner identity;
2. copies native request state and attempts immediate progress;
3. returns ready without registration or ready-queue traffic when complete;
4. otherwise claims one fixed operation slot and the required bounded
   transport registrations;
5. returns `PENDING`;
6. resumes only after transport progress, owner timer, cancellation, or
   structured deadline;
7. generation-checks every event and rearms or completes;
8. releases registrations, native request copies, partial values, and frame
   ownership exactly once.

One poll processes a bounded number of callbacks/bytes before yielding to the
ready queue. A continuously ready response cannot monopolize the
current-thread executor.

### 7.2 Linux, macOS, and BSD

One libcurl multi handle belongs to each executor and owns its bounded
connection cache. The runtime uses `curl_multi_socket_action` plus socket and
timer callbacks; it registers the reported sockets with epoll or kqueue and
does not call `curl_multi_poll`, `curl_multi_wait`, `curl_easy_perform`, or a
blocking drive loop on the async worker.

Hostname lookup uses the bounded resolver job from RFC 0037 and passes at most
16 ordered candidates to libcurl while preserving the original host for TLS
SNI and certificate verification. If the loaded libcurl cannot accept the
required socket/timer/resolution contract, the async path returns
`runtime_unavailable`; it does not silently resolve on the worker.

Ambient proxy behavior is outside this first async contract. The first runtime
disables implicit proxy discovery so an unbounded system callback or
credential-forwarding policy is not smuggled into the executor. A future proxy
RFC must define bounds, secrets, cancellation, and connection-key isolation.

### 7.3 Windows

The owner executor opens WinHTTP in asynchronous mode. Stable fixed operation
slots receive WinHTTP status callbacks and publish bounded,
generation-checked completions to the owner executor through its wakeup
source. System callback threads may execute WinHTTP itself, but Nomo does not
create one worker thread per request and callbacks never access Nomo-managed
values.

The session and at most eight idle origin connections are owner local. Request
handles, read buffers, callback context, and late-close state remain in stable
slots outside coroutine frames. Cancellation closes the request handle,
invalidates publication, and drains late callbacks before slot reuse. No
callback may wake a reused generation.

### 7.4 Browser WASM

Without a granted fetch capability, `send`, `get`, `post`, and `open_stream`
return a ready `runtime_unavailable` result before evaluating any request,
URL, body, timeout, or limit operand. No executor, registry, connection pool,
resolver, or host import is initialized. Pull operations cannot receive a
constructible `HttpStream`.

Browser `fetch`/`ReadableStream` support requires a focused host-capability RFC
and must preserve the same bounds and cancellation semantics.

## 8. Errors, Diagnostics, and Secret Safety

The async surface retains RFC 0022/0023 codes and adds owner/runtime outcomes:

- `invalid_request`;
- `runtime_unavailable`;
- `dns`;
- `connect`;
- `tls`;
- `timeout`;
- `response_too_large`;
- `protocol`;
- `transport`;
- `closed`;
- `busy`;
- `limit`;
- `reactor`.

Structured task cancellation is a task outcome, not a catchable `HttpError`.
`closed` covers a stale generation, closed stream, or wrong owner. `busy`
covers a second operation on one stream. `limit` covers fixed owner, resolver,
completion, or connection capacity. `reactor` covers backend
registration/completion failure.

Errors, diagnostics, scheduler traces, metrics labels, owner slots, and
connection keys must not include header values, request bodies, URL query
text, received headers/body/chunks/SSE data, bearer tokens, CA paths, native
handles, or unbounded host-derived text. Names such as `Authorization` may be
identified only when no value or source excerpt is included.

| Code | Condition | Required guidance |
| --- | --- | --- |
| `E0870` | synchronous caller reaches an unsuffixed async HTTP client operation | mark the function `suspend` or use the explicit `_blocking` compatibility name |
| `E0890` | `HttpStream` crosses an owner/task/shard boundary | keep the stream local and send owned decoded data |
| `E0891` | suspend call graph reaches a `_blocking` HTTP client or blocking server operation | use the suspend client or isolate deliberate blocking work |
| `E0892` | target lacks the required HTTP transport capability | name the target and implemented backend phase without source argument values |

## 9. Compiler and C99 Lowering

`send`, `get`, `post`, `open_stream`, `read_text`, and `next_sse` are suspend
intrinsics. The first lowering slice requires direct calls to be `let`-bound,
evaluates operands once, and uses typed start/resume/cancel registrations under
the RFC 0031 stackless ABI.

Managed request values retained across a pending start have explicit frame
ownership bits and are released exactly once on ready, error, timeout,
cancellation, panic, and enclosing-frame drop. `HttpStream` itself is an
opaque scalar identity; returned status/header values obey ordinary task-local
ARC/COW rules.

Ready validation failure, browser unsupported, stale/closed handle, buffered
chunk/event, EOF, and already-complete transport paths do not allocate a
coroutine node or enqueue the task. A pending operation uses at most one
coroutine frame plus its fixed owner slot.

When the suspend surface lands, `E0891` removes only the new unsuffixed client
operations and immediate async-handle close/cancel from quarantine. All
`_blocking` client calls and blocking server progress remain quarantined.
Programs that do not use suspend HTTP emit no executor, reactor, resolver,
async HTTP table, connection pool, callback, or atomic support.

## 10. Metrics and Acceptance Evidence

Versioned counters include at least:

- request/stream starts, ready completions, pending completions, errors,
  timeouts, and cancellations;
- response-head, body-chunk, and SSE-event delivery;
- connection creation, clean reuse, idle eviction, and forced close;
- live/peak HTTP operations, streams, connections, resolver jobs,
  registrations, and retained request/response/parser bytes;
- reactor registration/deregistration/reregistration and Windows late-callback
  draining.

Immediate validation/browser/stale/buffered/EOF paths require zero
registration and queue traffic. Every success, HTTP error status, transport
error, limit, timeout, cancellation, panic, close, and shutdown fixture ends
with zero live operation, stream, resolver job, registration, late callback,
and retained byte counters.

Native integration tests use local plain and generated-certificate TLS
fixtures and no real API key. They cover:

- verified HTTPS, host-name failure, custom authorization/content headers, and
  response status/headers/body;
- immediate and pending DNS/connect/TLS/send/head/body progress;
- keep-alive reuse without authorization/body/header state leakage;
- split UTF-8, all accepted SSE line/framing cases, `[DONE]`, EOF, and limits;
- zero/positive request and idle deadlines, enclosing deadline, structured
  cancellation at each transport phase, explicit cancel/close, late
  completion, copied stale handle, and slot reuse;
- exact owner/registration/resolver/connection saturation;
- the compatibility cleanup regression, including ASAN or equivalent native
  evidence that one easy/request handle has one cleanup owner;
- Linux epoll, macOS kqueue, and Windows asynchronous WinHTTP native execution;
- browser pre-evaluation capability rejection and zero host import;
- one-core and low-memory connection-idle/cancellation storms.

RFC 0034's fair report compares the same fixed Go version, TLS fixture,
certificate validation, request/response payload, keep-alive policy, SSE
events, cancellation schedule, core/fd/memory limits, and validation work. It
records throughput, p50/p99/p999, CPU, RSS, fd/handle/thread counts, live idle
connections, and retained buffers. The first correct result is evidence only;
it cannot claim superiority before the complete matrix and controlled-host
gates pass.

## 11. Phased Delivery

| Slice | Required behavior | Status |
| --- | --- | --- |
| P2-HTTP-A | public suspend/handle/migration contract, `E0870`/`E0890`/`E0891`, typed lowering ABI, blocking cleanup regression, and benchmark fixture | Planned |
| P2-HTTP-B | Unix buffered send/open through owner-local curl multi, bounded resolver, TLS fixture, connection reuse, timeout/cancel, and exact lifecycle counters | Planned |
| P2-HTTP-C | Unix incremental text/SSE pulls, terminal cancellation, slot reuse, limits, and epoll/kqueue native stress | Planned |
| P2-HTTP-D | asynchronous WinHTTP send/stream parity, owner wakeup, bounded connection reuse, late-callback drain, and native Windows stress | Planned |
| P2-HTTP-E | browser pre-evaluation unsupported boundary and zero-import release-WASM evidence | Planned |
| P2-HTTP-F | Nomo OpenAI-compatible buffered/SSE examples, saturation/low-memory storms, and RFC 0034 HTTP/SSE report | Planned |

The RFC must merge as `Proposed` before P2-HTTP-A starts. Each implementation
slice lands through a focused signed branch/PR with Nomo examples, compiler and
CLI tests, bilingual stdlib/SPEC/docs updates, native platform evidence, and
exact cleanup counters.

This RFC remains `Proposed` until every required platform, correctness,
resource, compatibility, and fair benchmark gate passes. Landing the document
or one implementation slice does not make it `Accepted`.

## 12. Alternatives and Risks

| Alternative | Why it is not selected |
| --- | --- |
| wrap existing synchronous pulls in coroutine frames | still blocks the executor and retains the unsafe global registry |
| implement HTTPS directly over async TCP | duplicates TLS, certificate, HTTP framing, and platform trust work already delegated to mature runtimes |
| run one blocking worker per request/stream | consumes a thread and stack for every mostly idle Agent connection |
| make `HttpStream` Send with a global lock | adds contention, obscures close ownership, and does not make callbacks or managed values safely transferable |
| expose a public client/pool immediately | expands the v0.1 API before the implicit bounded owner-local reuse contract is proven |
| preserve unsuffixed blocking and add permanent `_async` names | creates two long-term APIs and contradicts direct-style effect migration |

Risks include dynamic libcurl capability differences, resolver and callback
races, backend-specific connection reuse, early-cancel TLS state, retained
secret buffers, duplicate cleanup, and preview source breakage. Explicit
compatibility names, fixed owner slots, generation checks, bounded resolver
jobs, one normalized operation state machine, native fixtures, sanitizer
evidence, and exact counters mitigate them.

## 13. v0.1 Impact and Open Follow-Ups

This RFC supplies the nonblocking model-call transport required by a
Nomo-native CLI Agent. It does not implement an Agent product and does not
require application C FFI. Toolchain/runtime use of libcurl, WinHTTP, system
resolvers, and platform reactors remains an internal implementation boundary.

Async HTTP server accept/respond, public proxy configuration, cookies,
redirect policy, binary buffers, request streaming, WebSocket, browser fetch,
HTTP/2 tuning, and cross-shard handle transfer remain focused follow-ups. They
are not inferred from this client RFC.

## 14. Decision

Adopt the bounded owner-affine contract and phased migration above. Do not
block an executor worker, preserve the process-global stream registry, create
one thread per request, retain Nomo-managed values in host callbacks, share
authorization state through a connection cache, expose raw transport handles,
or infer platform/performance readiness from generated C alone.

## 15. References

- [RFC 0022: Structured HTTP client and toolchain-owned host runtime](./0022-structured-http-client-and-host-runtime.md)
- [RFC 0023: Pull-based HTTP streaming and SSE](./0023-pull-based-http-streaming-and-sse.md)
- [RFC 0031: Direct-style suspend functions and structured concurrency](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0032: Sharded executor, reactor, and blocking pool](./0032-sharded-executor-reactor-and-blocking-pool.md)
- [RFC 0034: Async runtime acceptance and benchmark gates](./0034-async-runtime-acceptance-and-benchmark-gates.md)
- [RFC 0037: Owner-affine async TCP client and blocking migration](./0037-owner-affine-async-tcp-client-and-blocking-migration.md)
