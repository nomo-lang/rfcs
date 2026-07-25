# RFC 0032: Sharded Executor, Reactor, and Blocking Pool

> Language: [中文](../../zh-CN/rfcs/0032-sharded-executor-reactor-and-blocking-pool.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0032 |
| Title | Sharded executor, reactor, and blocking pool |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-25 |
| Topics | executor, reactor, epoll, kqueue, IOCP, WASM, affinity, blocking pool, Agent I/O |
| Related RFCs | [RFC 0017](./0017-target-triples-and-cross-compilation.md), [RFC 0022](./0022-structured-http-client-and-host-runtime.md), [RFC 0023](./0023-pull-based-http-streaming-and-sse.md), [RFC 0024](./0024-controlled-child-processes-and-stdio.md), [RFC 0026](./0026-isolated-native-tasks-and-cooperative-cancellation.md), [RFC 0027](./0027-bundled-sqlite-persistence-and-pull-queries.md), [RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md), [RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md), [RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md), [RFC 0035](./0035-monotonic-suspend-timers-and-blocking-sleep-migration.md) |

## 1. Summary

Nomo's async runtime starts as a current-thread executor plus a platform
reactor. It later scales as one executor/reactor shard per selected core. Tasks
and I/O handles are owner-affine; cross-shard work transfers values through
bounded channels instead of sharing ordinary mutable state.

Linux uses `epoll` first, macOS/BSD use `kqueue`, Windows uses IOCP, and browser
WASM uses a host-driven current-thread backend. `io_uring` is a later optional
Linux optimization, not a semantic dependency. Blocking filesystem, SQLite,
unknown C FFI, and CPU-heavy work use a separate bounded, lazy blocking pool.

This RFC is `Proposed`. Existing synchronous host helpers remain the current
implementation until the corresponding runtime PRs meet the gates in RFC 0034.

## 2. Motivation and Current Audit

The current runtime was designed for bounded synchronous calls:

- RFC 0026 creates one native thread per task.
- HTTP streaming drives libcurl/WinHTTP synchronously from each pull.
- process pipes are nonblocking on Unix but are polled by a synchronous
  `next_event`; Windows uses helper reader/writer threads.
- HTTP streams, process children, and SQLite databases/queries are stored in
  process-global linked lists with process-global numeric handle allocators.
- those registries are not protected for concurrent workers and do not encode
  executor ownership.
- SQLite deliberately uses a system/library call that may block despite its
  serialized/full-mutex configuration.

Putting a large lock around every registry would serialize the runtime and
would still allow an I/O handle to be driven by the wrong executor. The
runtime must instead make ownership and readiness explicit.

## 3. Executor Model

### 3.1 Current-thread baseline

A suspend entry initializes one executor on the calling OS thread. It owns:

- a FIFO ready queue;
- a reactor instance;
- a monotonic timer wheel;
- task/frame slabs;
- owner-local handle tables with generation-checked slots;
- a cancellation/deadline queue;
- metrics required by RFC 0034.

Polling continues until the root structured scope is complete. If a poll
finishes synchronously, the executor continues inline within a bounded poll
budget. A pending task registers interest and returns control to the executor.
A ready fast path must not enqueue or allocate.

A synchronous program never initializes this state, starts a thread, or links
ordinary collection operations to atomic runtime helpers.

### 3.2 Sharded multi-core runtime

The multi-core stage creates at most one async worker per selected shard. The
default count is bounded by available cores, configuration, and memory policy;
one-core/low-memory targets use one worker.

Each task has one owner shard. Socket, HTTP stream, server acceptor, process
pipe, timer registration, and similar handles are `Local` and owner-affine.
Only the owner may mutate or poll them. A handle table slot contains an index,
generation, and resource kind so stale or cross-kind handles fail safely.

Cross-shard messages use bounded queues and RFC 0033's publish/transfer rules.
There is no default global work-stealing deque. A later opt-in stealing mode
may move only a task proven `Send`, with no `Local` value, active reactor
registration, or handle affinity. It may ship only after RFC 0034 benchmarks
show a repeatable benefit.

## 4. Reactor and Timer Backends

| Target | Required first backend | Contract |
| --- | --- | --- |
| Linux | `epoll` with edge/level behavior normalized by the runtime | nonblocking fd registration, wakeup fd, batched readiness |
| macOS and BSD | `kqueue` | socket, pipe, process, and timer readiness normalized to common events |
| Windows | IOCP | overlapped socket/pipe operations with completion ownership |
| browser WASM | host-driven current-thread adapter | JavaScript Promise/event completion wakes exported runtime polling |
| unsupported native target | explicit compile diagnostic | no silent fallback that blocks an async worker |

`io_uring` may be selected on supported Linux kernels after capability probing.
It must preserve the same cancellation, deadline, and ownership semantics and
must fall back to `epoll` without changing application code.

The timer wheel uses a monotonic clock, bounded horizon/buckets, and batched
expiry. Wall-clock changes do not alter deadlines. Very long timers may be
reinserted in bounded rounds. RFC 0035 defines the public suspend timer,
blocking-sleep migration, ready path, and cancellation/drop contract.

One wakeup source per shard handles cross-shard messages and cancellation.
Reactor events are generation checked so a readiness event for a closed and
reused slot cannot wake the new resource.

## 5. Nonblocking Agent I/O

The following Agent-critical operations gain true suspend-capable paths:

- TCP connect/accept/read/write/shutdown;
- HTTPS request headers/body and connection reuse;
- HTTP response streaming and SSE incremental reads;
- process stdin writes, stdout/stderr reads, exit notification, and terminate;
- timers and task synchronization;
- MCP newline/JSON-RPC framing over a long-lived child.

A suspend operation registers readiness/completion, returns `PENDING`, and
resumes only when it can make progress, is cancelled, or reaches its deadline.
It must not wait in a loop on the async worker. Buffer sizes and queued writes
remain bounded; full queues suspend or return a typed backpressure result.

Existing `std.http`, `std.net`, and controlled `std.process` names move to
`suspend fn` where the operation can wait. Direct-style syntax minimizes source
noise, but callers must declare `suspend`. Immediate close/accessor operations
remain synchronous. During preview migration, a diagnostic names the new
effect and the explicit blocking compatibility path when one exists.

HTTP TLS, headers, body limits, secret redaction, and response contracts remain
those of RFCs 0022 and 0023. This RFC changes how progress is driven, not those
security or protocol semantics.

## 6. Bounded Blocking Pool

The blocking pool is distinct from async workers:

- zero threads exist until the first blocking job;
- minimum, maximum, queue capacity, idle retirement, and shutdown deadline are
  bounded configuration;
- queue saturation applies backpressure and never creates an unbounded thread;
- blocking jobs cannot access owner-local async handles;
- completion returns to the originating shard through a bounded queue;
- cancellation before start removes a job; cancellation after start is
  cooperative unless the specific host operation supports interruption;
- shutdown waits to its declared deadline and reports remaining jobs.

SQLite, blocking filesystem calls, DNS implementations without async host
support, unknown blocking C FFI, and explicitly marked CPU work use this pool.
Toolchain/runtime code may call system C libraries; Agent application code does
not write C FFI merely to obtain these capabilities.

RFC 0026's `task fn(TaskContext, string) -> string` compatibility API is
reimplemented on this pool for one documented preview migration window.
`std.task.spawn` in that legacy form no longer means one OS thread per task.
New async tasks use RFC 0031's structured spawn. Nested legacy blocking jobs
must not deadlock the pool; they are rejected or execute under a bounded
helping rule specified by the implementation.

## 7. Runtime Ownership and Atomic Shim

Process-global, unguarded linked-list registries are removed from async paths.
HTTP streams, process children, sockets, SQLite operations, and timers live in
owner tables or blocking-job state with explicit transfer/close rules.

Cross-thread executor metadata, shared values, channels, and wakeups use a
private C99-compatible atomic shim:

- GCC/Clang implementations use `__atomic_*`;
- Windows uses Interlocked operations;
- acquire/release/sequential requirements are documented per primitive;
- unsupported compilers fail during target capability validation.

This shim is not used by ordinary `string`, `Array<T>`, ordered `Map<K,V>`, or
task-local values. Toolchain-generated public C headers do not expose it as an
application ABI.

## 8. Cancellation, Close, and Runtime Shutdown

Every pending operation owns exactly one reactor registration or completion
token. Cancellation transitions it once from pending to cancelled, deregisters
or cancels the host operation, and schedules frame cleanup on the owner shard.
Late readiness is ignored through generation checks.

Closing an affine handle is exclusive and idempotent only where its standard
library type says so. A close consumes the handle; use-after-close and
wrong-shard access return stable typed errors or compiler diagnostics rather
than dereferencing a stale registry node.

Root shutdown:

1. stops admission of daemon/blocking work;
2. cancels structured and declared daemon scopes;
3. drains completion/drop work;
4. waits for the blocking-pool deadline;
5. releases reactor and slab resources;
6. reports leaked handles/tasks in debug/test mode.

## 9. Diagnostics

| Code | Condition | Required guidance |
| --- | --- | --- |
| `E0890` | a `Local` handle is used from a non-owner task/shard | keep work on the owner or send data, not the handle |
| `E0891` | a known blocking intrinsic is called on an async worker | use the suspend wrapper or explicit blocking pool |
| `E0892` | a target lacks a required reactor capability | name the target and supported backend/configuration |
| `E0893` | a legacy `task fn` path violates blocking-pool nesting rules | flatten the job or use structured async tasks |

Runtime backpressure, timeout, cancellation, closed-handle, and reactor errors
are typed standard-library results with secret-safe messages. Authorization
headers, tokens, process environment secrets, request bodies, and SQLite values
must not appear in diagnostics or scheduler traces.

## 10. Test and Acceptance Plan

Unit tests cover ready-queue fairness, timer ordering, generation reuse,
registration cancellation, late events, blocking-pool saturation, shutdown,
and atomic memory-order wrappers.

Integration tests cover native TCP, HTTP keep-alive/SSE, process pipes/MCP,
SQLite through the blocking pool, cancellation storms, connection churn, and
resource limits. Local fixtures provide deterministic TLS and protocol
behavior without real API keys.

Platform CI must exercise `epoll`, `kqueue`, IOCP, and host-driven WASM. Cross
build alone is insufficient for reactor acceptance; each backend needs a
native run or maintained platform runner. Sanitizers and debug leak counters
must show no fd, buffer, registration, task, or handle leaks.

RFC 0034 supplies quantitative gates. This RFC cannot become `Accepted` based
only on an executor compiling on one platform.

## 11. Alternatives and Risks

| Alternative | Why it is not selected |
| --- | --- |
| one global executor and reactor lock | creates contention and obscures handle ownership |
| global work stealing by default | conflicts with local handle affinity and must first prove value |
| thread-per-connection/task | excessive stack/RSS and scheduling cost for idle Agent workloads |
| run blocking calls on async workers | stalls unrelated tasks and destroys latency bounds |
| require `io_uring` | excludes kernels/targets and makes semantics depend on an optimization |
| lock all existing global registries | treats symptoms without defining lifetime or owner affinity |

The main risks are backend divergence, cancellation races, platform CI cost,
and accidental blocking inside a worker. Common conformance tests, one
normalized reactor contract, owner assertions, and the benchmark/leak harness
are mandatory mitigations.

## 12. Implementation Phases and Decision

1. current-thread executor, yield, timer wheel, cancellation, metrics;
2. Linux `epoll` and macOS `kqueue`, async TCP, HTTP/SSE, and process pipes;
3. Windows IOCP and host-driven browser WASM parity;
4. bounded blocking pool and RFC 0026 compatibility migration;
5. per-core shards and bounded cross-shard channels;
6. only then optional stealing, `io_uring`, batching, and slab tuning.

**Proposed decision:** adopt owner-affine current-thread/sharded executors,
platform reactors, and a separate bounded blocking pool. Do not expand the
existing thread-per-task or unguarded global-registry architecture.

## 13. References

- [RFC 0022: Structured HTTP client and host runtime](./0022-structured-http-client-and-host-runtime.md)
- [RFC 0023: Pull-based HTTP streaming and SSE](./0023-pull-based-http-streaming-and-sse.md)
- [RFC 0024: Controlled child processes and stdio](./0024-controlled-child-processes-and-stdio.md)
- [RFC 0026: Isolated native tasks and cooperative cancellation](./0026-isolated-native-tasks-and-cooperative-cancellation.md)
- [RFC 0031: Direct-style suspend functions and structured concurrency](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0033: Task ownership transfer and concurrent values](./0033-task-ownership-transfer-and-concurrent-values.md)
- [RFC 0034: Async runtime acceptance and benchmark gates](./0034-async-runtime-acceptance-and-benchmark-gates.md)
- [RFC 0035: Monotonic suspend timers and blocking sleep migration](./0035-monotonic-suspend-timers-and-blocking-sleep-migration.md)
