# RFC 0037: Owner-Affine Async TCP Client and Blocking Migration

> Language: [中文](../../zh-CN/rfcs/0037-owner-affine-async-tcp-client-and-blocking-migration.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0037 |
| Title | Owner-affine async TCP client and blocking migration |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-26 |
| Topics | async TCP, reactor, owner affinity, bounded I/O, DNS, migration |
| Related RFCs | [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md), [RFC 0022](./0022-structured-http-client-and-host-runtime.md), [RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md), [RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md), [RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md), [RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md), [RFC 0035](./0035-monotonic-suspend-timers-and-blocking-sleep-migration.md) |

## 1. Summary

Nomo's first reactor-backed network surface is a bounded, owner-affine TCP
client. `net.connect`, `TcpStream.read`, and `TcpStream.write` become
direct-style `suspend` operations. Text helpers use the same bounded engine.
Each operation has an explicit timeout, returns a structured `NetErrorKind`,
and owns at most one generation-checked reactor registration.

The current blocking client remains available for one preview migration window
through names ending in `_blocking`. Blocking listener and UDP APIs remain
documented compatibility surfaces until focused RFCs replace them.

This RFC is `Proposed`. It fixes the public contract and phased acceptance
gates; it does not mark the existing blocking implementation as async.

## 2. Current Audit

The current `std.net` surface cannot be carried unchanged into Agent-facing
async code:

- connect, accept, stream read/write, and UDP block the calling OS thread;
- `TcpStream.read_to_string()` reads to EOF into an unbounded buffer;
- TCP values contain raw socket handles instead of owner-table slot and
  generation identities;
- operations have no explicit timeout or cancellation contract;
- portable `getaddrinfo` may block and cannot run on an async worker;
- `NetError` contains only a host-derived message;
- platform behavior is not expressed through one capability contract.

The P2 reactor foundation provides lazy epoll, kqueue, and IOCP lifecycle and
timer waits, but it does not register sockets. Wrapping the old helpers in a
coroutine would still block the executor and is rejected by this RFC.

## 3. Scope

This RFC defines outbound TCP connect, incremental read, complete bounded
write, shutdown, close, owner identity, timeouts, cancellation, errors, and the
blocking migration. It does not define listener accept, UDP, TLS, HTTP/SSE,
MCP framing, shared sockets, multi-shard handle migration, or a public
fd/socket/reactor-token API.

## 4. Public Standard-Library Contract

### 4.1 Errors and chunks

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

Portable control flow uses `kind`; applications do not parse platform numbers
from `message`. Messages are bounded and secret-safe. `Array<u32>` follows the
v0.1 byte convention and contains only `0..=255`. Text reads validate UTF-8;
invalid input returns `Read` without returning partial text.

### 4.2 Suspend client operations

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

Calls remain direct-style, but the caller must be `suspend`. Reads return after
at least one byte, EOF, timeout, cancellation, or error; they never imply
read-to-EOF. `eof` may be true with empty data. Writes either complete the
whole bounded input or return an error, retaining progress across readiness
events. Native writes advance at most 64 KiB per executor poll so one ready
stream cannot monopolize the current-thread executor.

`max_bytes` is in `1..=1,048,576`; one write is at most 1,048,576 bytes.
`timeout_millis` is at most 900,000. Zero performs one immediate attempt and
never registers with the reactor. Positive timeouts use the monotonic clock.

### 4.3 Blocking compatibility

For one preview migration window:

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

When async TCP lands, unsuffixed client names have the suspend signatures above.
A synchronous caller receives `E0870`; a suspend call graph reaching a
`_blocking` operation receives `E0891`. There is no effect-based overload and
no runtime switch that silently chooses blocking behavior.

Blocking `listen`, `TcpListener.accept`, and UDP names remain unchanged in this
client-only RFC and must be labeled blocking. Their later migration follows the
same explicit effect and compatibility rule.

## 5. Identity and Ownership

`TcpStream` is opaque and `Local/!Send`. The runtime stores slot index,
generation, resource kind, and owner executor identity; a copied raw socket is
not authority. The bounded owner table rejects stale generation, wrong kind,
closed slot, and wrong owner without touching a reused resource.

The first slice permits at most one pending operation per stream direction.
Conflicts return `Busy` rather than allocating a second queue. Applications
send owned request/response data across tasks, not the handle.

`close` is the exclusive terminal path: it deregisters readiness, closes once,
advances the generation, and invalidates late events. Cancelling one operation
removes it but leaves the stream open unless structured cleanup closes it.

## 6. Reactor Progress

A native operation:

1. validates limits and owner identity;
2. attempts immediate progress;
3. returns ready without allocation or registration when complete;
4. otherwise claims one bounded operation slot and registration;
5. returns `PENDING`;
6. resumes after readiness, cancellation, or the effective deadline;
7. generation-checks the event and completes or rearms;
8. deregisters and releases retained buffers exactly once.

Unix sockets are nonblocking. Linux normalizes epoll one-shot readiness and
macOS normalizes kqueue one-shot filters. Windows uses IOCP completion
ownership, not a blocking worker. Spurious readiness simply rearms after
would-block. A write attempt advances at most 64 KiB before yielding and
rearming when more payload remains; this fairness budget does not change the
complete-write result contract.

The effective deadline is the earlier of the operation timeout and enclosing
structured deadline. Cancellation wins once; late events are ignored by slot
and generation checks. An I/O completion returns control to the ready queue
immediately and must not remain inside a timer-wait loop.

## 7. DNS and Address Iteration

Portable `getaddrinfo` may block and must not execute on an async worker.
Delivery is staged:

1. the first epoll/kqueue slice accepts numeric IPv4/IPv6 only and returns
   `Unsupported` for hostnames before I/O starts;
2. a bounded lazy blocking-pool resolver adds hostnames, returns at most 16
   candidate addresses, and sends one bounded completion to the owner;
3. native async resolvers may replace the job only with identical bounds,
   cancellation, result order, and secret safety.

Candidates are tried in resolver order under one overall deadline. Resolver
queue saturation returns `Limit`. Numeric-only support is an implementation
milestone, not a complete Agent networking claim.

## 8. Platform Phases

| Slice | Required behavior | Status |
| --- | --- | --- |
| P2-TCP-A | bounded owner table, generation checks, registration lifecycle, numeric-host nonblocking connect on epoll/kqueue | Implemented by [`nomo#45`](https://github.com/nomo-lang/nomo/pull/45) |
| P2-TCP-B | incremental bounded read and complete bounded write on epoll/kqueue | Implemented by [`nomo#46`](https://github.com/nomo-lang/nomo/pull/46) |
| P2-TCP-C | hostname resolution through the bounded blocking pool | Implemented by [`nomo#47`](https://github.com/nomo-lang/nomo/pull/47) |
| P2-TCP-D | IOCP connect/read/write with native Windows execution | Not implemented |
| P2-TCP-E | host-driven browser adapter where raw TCP exists, otherwise pre-evaluation `runtime_unavailable` | Not implemented |

During A through C, Windows compiles and returns `Unsupported` for new client
calls without evaluating or logging secret payloads. This is explicit phased
behavior, not IOCP acceptance. RFC 0032 cannot become `Accepted` before required
Windows and browser evidence exists.

The A/B/C implementation includes bounded read/write payloads, positive and
zero timeouts, structured cancellation, one pending operation per stream
direction, exact registration/retained-buffer lifecycle counters, native
Linux/macOS execution, explicit pre-evaluation Windows rejection, and Nomo
examples. Hostnames use one lazy worker and 16 live-job slots, return
completion through the owner reactor, copy at most 16 candidates, and share
one deadline with ordered connect attempts. Queued cancellation is immediate;
an in-progress system resolver call is cooperatively detached and cleaned
after it returns. `shutdown_write`, the general RFC 0032 blocking pool, native
IOCP, and the browser adapter remain follow-up slices. These partial
implementation results do not change this RFC from `Proposed`.

## 9. Metrics and Limits

Versioned metrics add at least:

- `reactor_registrations`, `reactor_deregistrations`, and
  `reactor_reregistrations`;
- `io_connect_starts`, `io_read_starts`, and `io_write_starts`;
- `io_ready_completions`, `io_timeouts`, `io_cancellations`, and `io_errors`;
- `live_io_handles`, `peak_live_io_handles`, `live_io_operations`, and
  `peak_live_io_operations`;
- retained read/write bytes and peak retained bytes;
- blocking-pool initialization, thread start/retirement, job
  queued/started/completed/cancelled/saturation, and live/peak thread and job
  counters.

Ready paths have zero registrations and queue traffic. Timeout, cancellation,
close, and failure fixtures end with zero live operations, registrations, and
buffers. All capacities are documented and snapshot-tested; saturation returns
`Limit`, and no table or buffer grows without a bound.

## 10. Diagnostics and Secret Safety

| Code | Condition | Guidance |
| --- | --- | --- |
| `E0870` | synchronous caller invokes async TCP | mark it `suspend` or use the explicit blocking compatibility API |
| `E0890` | `TcpStream` crosses an owner/task boundary | keep the stream local and send owned data |
| `E0891` | suspend call graph reaches blocking network I/O | use suspend I/O or the bounded blocking pool |
| `E0892` | target lacks the required TCP capability | name the target and implemented platform phase |

Diagnostics may include operation, kind, and a bounded platform category. They
never include written/received payloads, higher-level authorization tokens,
environment values, or unbounded host strings.

## 11. Acceptance Gates

Every implementation PR includes Nomo examples, unit/CLI integration tests,
bilingual stdlib/SPEC documentation, native platform evidence, and exact
counter/leak assertions.

Deterministic fixtures cover immediate/pending connect, one-byte and maximum
read/write boundaries, partial writes, multiple readiness cycles, EOF, zero and
positive timeout, cancellation at every lifecycle phase, close/late-event and
slot-reuse races, saturation, invalid UTF-8, numeric zero-thread execution,
hostname success and zero-timeout no-initialization, queued/running resolver
cancellation, exact resolver-capacity overflow, and secret-safe errors.

Linux and macOS require native epoll/kqueue execution. Windows requires explicit
unsupported behavior before P2-TCP-D and native IOCP execution afterward;
cross-build alone is insufficient.

RFC 0034 TCP echo, churn, cancellation storm, latency, CPU/RSS, descriptor, and
buffer-leak workloads remain ineligible for performance claims until connect,
read, write, cancellation, and every required backend exist. The first correct
slice records a baseline and does not claim to outperform Go.

## 12. Alternatives and Risks

| Alternative | Why it is not selected |
| --- | --- |
| add permanent `connect_async` names | splits one operation into two long-term APIs and contradicts direct-style effect migration |
| wrap blocking sockets in coroutine frames | still blocks unrelated tasks on the executor |
| keep read-to-EOF without a limit | permits unbounded memory growth and prevents incremental protocol framing |
| expose raw sockets or reactor tokens | leaks platform and owner-affinity details into application code |
| resolve DNS synchronously on the worker | introduces unbounded scheduler stalls |
| require io_uring | excludes required platforms and makes semantics depend on an optional optimization |

Risks include preview source breakage, backend divergence, cancellation races,
DNS queue pressure, and retained-buffer leaks. Explicit compatibility names,
one normalized operation state machine, generation checks, native CI, bounded
fixtures, and exact lifecycle counters mitigate them.

## 13. v0.1 Impact and Open Follow-Ups

P2-TCP-A/B/C are additive executable slices and update the SPEC and standard
library with numeric-address or bounded-hostname suspend connect plus bounded
incremental read/write on Linux and macOS. The old client behavior remains
available through explicit `_blocking` compatibility names for the preview
migration window. Listener accept and UDP remain blocking.

A dedicated byte type may later replace `Array<u32>` without changing the
reactor contract. Listener/UDP migration, TLS, and cross-shard stream transfer
remain focused follow-ups; none is silently decided here.

## 14. Decision

Adopt this bounded owner-affine contract and implement the phases as small PRs.
Do not expose raw sockets or reactor tokens, wrap blocking helpers in a
coroutine, run DNS on the async worker, preserve unbounded read-to-EOF under an
async name, create a thread per connection, add a global registry lock, or
infer IOCP/browser parity from generated C.

This RFC remains `Proposed` until its full API, platform matrix,
cancellation/resource gates, documentation, and fair RFC 0034 benchmarks pass.

## 15. References

- [RFC 0015: Source-defined standard library and intrinsics](./0015-source-defined-standard-library-and-intrinsics.md)
- [RFC 0031: Direct-style suspend functions and structured concurrency](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0032: Sharded executor, reactor, and blocking pool](./0032-sharded-executor-reactor-and-blocking-pool.md)
- [RFC 0033: Task ownership transfer and concurrent values](./0033-task-ownership-transfer-and-concurrent-values.md)
- [RFC 0034: Async runtime acceptance and benchmark gates](./0034-async-runtime-acceptance-and-benchmark-gates.md)
