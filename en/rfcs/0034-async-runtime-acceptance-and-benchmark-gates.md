# RFC 0034: Async Runtime Acceptance and Benchmark Gates

> Language: [中文](../../zh-CN/rfcs/0034-async-runtime-acceptance-and-benchmark-gates.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0034 |
| Title | Async runtime acceptance and benchmark gates |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-25 |
| Topics | performance, memory, benchmark, Go comparison, low-end devices, cross-platform, correctness |
| Related RFCs | [RFC 0003](./0003-arc-cow-runtime-cost.md), [RFC 0017](./0017-target-triples-and-cross-compilation.md), [RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md), [RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md), [RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md) |

## 1. Summary

This RFC defines evidence required to implement and stabilize Nomo's async
model. “Zero cost when unused” means no async runtime initialization, thread,
coroutine metadata, scheduler branch, or ordinary-collection atomic operation
in a synchronous program. A ready suspend path performs no frame allocation
and no enqueue; a genuinely spawned task uses at most one logical slab/frame
allocation after allocator warm-up; frames contain only values live across
suspension.

Performance comparisons with Go are limited to fair, same-host, I/O-bound
Agent workloads. Throughput at least `1.10x`, RSS at most `0.80x`, and p99
latency no worse than the pinned Go baseline are design targets, not promises
that can be asserted before measurement. Real results and bottlenecks must be
reported even when a target is missed.

This RFC remains `Proposed` until the implementation, platform matrix,
correctness stress tests, docs, examples, and reproducible benchmark evidence
all satisfy the gates below.

## 2. Why a Separate Gate RFC

“Stackless”, “C99”, and “no tracing GC” do not prove low overhead. A compiler
can still spill every local, allocate every call, churn reference counts,
enqueue already-ready work, leak cancelled registrations, or consume more
memory than a mature runtime.

The current repository has a compiler clean-build/check latency gate but no
async runtime benchmark harness. Async implementation must start with
measurement hooks and reference workloads so later optimizations do not change
the comparison rules.

## 3. Reproducible Harness

`performance/async/` will contain:

- a machine-readable benchmark manifest;
- exact Nomo compiler/runtime revision and build flags;
- an exact Go patch version plus toolchain/container checksum;
- reference Nomo and Go sources implementing the same protocol and business
  logic;
- workload generator version/configuration and TLS fixture;
- warm-up, sample count, duration, connection count, payload, timeout, and
  random-seed settings;
- raw per-run results and a summarized JSON schema;
- host OS/kernel, CPU topology, memory, power mode, compiler, and limits.

The comparison pins available cores, process affinity where supported, file
descriptor limits, TLS mode, keep-alive policy, payloads, validation work, and
logging. Both implementations must produce and validate the same bytes. Neither
side may disable safety, omit error handling, precompute responses, or use a
different protocol merely to improve its score.

At least five measured runs follow warm-up. Reports include median plus
p50/p99/p999 latency, throughput, CPU time/utilization, peak and steady RSS,
allocations/bytes where measurable, open fds/handles, and runtime-specific
queue/frame/buffer counters. Raw data is retained as CI or release evidence.

## 4. Required Workloads

| Workload | Required measurements |
| --- | --- |
| task spawn/complete | same-shard and cross-shard throughput, allocation, p99 |
| idle suspended tasks | RSS per task at increasing populations, wake latency |
| timer wheel | insert/cancel/expire throughput, drift, cancellation storm |
| bounded channel | same-shard and cross-shard throughput, backpressure, fairness |
| TCP echo | throughput, p50/p99/p999, CPU/RSS, connection churn |
| HTTP keep-alive | requests/second, TLS/plain variants, connection reuse |
| SSE/MCP stream | long-lived idle RSS, incremental message latency, cancellation |
| process pipe | bidirectional stdio throughput, exit/cancel/timeout |
| connection churn | connect/close rate, stale-event defense, fd/buffer leaks |
| cancellation storm | completion latency, CPU spike, exactly-once cleanup |

Agent scenarios combine HTTPS model-style requests, SSE token streams, MCP
stdio, bounded JSON-RPC framing, timers, and SQLite checkpoint work through the
blocking pool. They use local fixtures and no real service credentials.

The “exceed Go” comparison applies only to the high-connection, I/O-bound rows
with equivalent semantics. It does not claim superiority for CPU-bound work,
compiler speed, arbitrary programs, or every platform.

## 5. Zero-Cost and Allocation Gates

### 5.1 Async unused

A representative synchronous program must show:

- no async executor/reactor startup or worker thread;
- no coroutine frame/state metadata in typed IR or generated C;
- no scheduler polling branch on ordinary calls;
- no link/runtime dependency introduced solely by unused async modules beyond
  the toolchain's normal dead-code/link behavior;
- no atomic RC or lock operation in ordinary string, array, or ordered-map
  helpers.

Generated-C snapshots and symbol/runtime instrumentation enforce this gate.

### 5.2 Ready path and spawn

- a suspend function whose entire call chain is ready completes inline;
- the ready fast path performs zero heap/slab allocations and zero ready-queue
  enqueue/dequeue operations;
- after slab warm-up, a true spawned task performs at most one logical
  frame/slab allocation; slab chunk growth is reported separately;
- a task is not allocated merely to call a suspend function sequentially;
- reactor registrations and select arms use bounded, reclaimable storage.

### 5.3 Precise frames and ARC

Compiler tests compare source liveness with frame layouts. A local that is dead
before suspension must not appear in the frame. Alignment/padding and runtime
metadata are reported separately from user live data.

Instrumentation records local and atomic retain/release operations, COW
detach count/bytes, publish copies, frame drops, and peak live frames. No report
may infer low churn merely from the absence of tracing GC.

## 6. Correctness and Resource Gates

Every backend must pass deterministic and stress tests for:

- ready/cancel/timeout/close races and late events;
- exactly-once result delivery and frame/value drop;
- parent-child cancellation and structured-scope shutdown;
- panic cleanup before process termination;
- bounded queue and blocking-pool saturation;
- stale handle generations and owner-affinity enforcement;
- channel/select winner races and moved-value recovery;
- lock cancellation and guard release;
- no fd, HANDLE, socket, timer, buffer, task, frame, registry, or blocking-job
  leak after steady state and cancellation storms;
- secret-safe diagnostics and tracing.

Sanitizers, model/stress tests, and debug counters are used where supported.
Any platform-specific skipped check requires a documented equivalent or an
open stabilization blocker.

## 7. Platform and Device Matrix

| Environment | Required evidence |
| --- | --- |
| Linux x86-64 | native `epoll` correctness, stress, leak, and full benchmarks |
| Linux arm64 | native or maintained emulated correctness plus low-memory/one-core evidence; native performance before stabilization claims |
| macOS arm64 and x86-64 | native `kqueue` correctness and representative benchmarks |
| Windows x86-64 | native IOCP correctness, cancellation, process-pipe, and representative benchmarks |
| browser WASM | host-driven current-thread correctness, size/startup budget, timers and supported network host APIs |
| one core / low memory | no extra async worker, bounded memory, backpressure and cancellation under pressure |
| multi-core | shard scaling, cross-shard cost, imbalance, optional-stealing experiment |

Cross-compilation proves build portability but does not replace native runtime
tests. Optional `io_uring` and stealing results are reported against their
mandatory fallback/default, not only against Go.

## 8. Performance Decision Rules

The first correct implementation records a baseline before optimization.
Subsequent PRs attach before/after results for affected workloads and explain
noise controls.

The design targets for equivalent high-connection I/O Agent workloads are:

- Nomo throughput `>= 1.10x` the pinned Go baseline;
- Nomo steady/peak RSS `<= 0.80x` the Go baseline;
- Nomo p99 latency no worse than Go at the same offered load and success rate.

These are optimization goals. Failing one does not authorize changing the Go
version, semantics, load, payload, safety checks, or sample selection. The
report instead identifies the bottleneck, confidence/noise, and next action.

The acceptance gate for each phase is truthful reproducible evidence with no
unexplained regression from the last Nomo baseline. A stable marketing claim
requires the stated targets across the named workloads and platforms; an RFC
status change alone cannot create that claim.

## 9. Phased Delivery Gates

| Phase | Required merge evidence |
| --- | --- |
| P0: semantics/harness | effect/type diagnostics, benchmark manifest, Go reference, counters, sync-unused snapshots |
| P1: stackless/current-thread | lowering/drop tests, ready zero-allocation, yield/timer/join/cancel examples |
| P2: reactors/I/O/blocking | epoll+kqueue then IOCP/WASM, TCP/HTTP/SSE/process fixtures, bounded blocking pool |
| P3: structured ownership | scope/deadline/select, channel backpressure, capability/guard diagnostics |
| P4: shards | one-core behavior, owner affinity, cross-shard transfer, scaling results; stealing remains off |
| P5: shared/collections | Frozen/Shared, locks, accepted Hash+Eq prerequisite, concurrent-container stress |
| P6: optimization/stabilization | slab/elision/batching, optional io_uring/stealing experiments, full matrix report |

Each phase also updates Nomo examples, unit and CLI integration tests,
English/Chinese docs and SPEC text for implemented behavior, diagnostic docs,
and platform CI. PRs remain reviewable slices rather than one implementation
megachange.

## 10. Example Acceptance Programs

The example matrix grows incrementally:

- `async_timer_and_cancel`;
- `structured_http_pair`;
- `async_sse_agent`;
- `mcp_stdio_client`;
- `bounded_pipeline`;
- `blocking_sqlite_checkpoint`;
- `affine_handle_negative`;
- `frozen_shared_snapshot`.

Examples must run with local fixtures, explicit limits/deadlines, and no API
keys. Each one documents native/WASM availability and expected output.

## 11. Compatibility and Reporting

Benchmark result schemas are versioned. Changing workload semantics or
measurement method starts a new comparable series and keeps old raw results.
CI may use broad regression thresholds; release/stabilization evidence uses
dedicated controlled hosts and cannot be inferred from noisy shared runners.

Public documentation must distinguish:

- design target from measured result;
- current-thread from sharded runtime;
- mandatory backend from optional optimization;
- application-side freedom from C FFI from toolchain-internal system-library
  use;
- implemented platform support from cross-build-only support.

### 11.1 Delivered P2 process-pipe evidence

[`nomo#58`](https://github.com/nomo-lang/nomo/pull/58) adds deterministic
16-child saturation, typed overflow, 32-slot reuse, and a 15-queued-job
cancellation storm with exact zero-live cleanup counters across Linux, macOS,
and Windows. [`nomo#59`](https://github.com/nomo-lang/nomo/pull/59) starts
result schema 2 and the first enabled P2 cross-language workload. Nomo and
pinned Go 1.25.12 execute the same 256-exchange, 63-byte bidirectional
process-pipe protocol against one C99 fixture. The Linux collector enforces
one-core affinity, a 2 GiB address-space ceiling, and a 128 MiB peak-RSS
budget, and records CPU/RSS/fd/thread observations plus p50/p99/p999.

The passing pull-request artifact reported Nomo/Go throughput `0.958986`, p99
wall ratio `1.004829`, and peak-RSS ratio `0.997620`; both implementations
used about 15.5 MiB peak RSS. These hosted-runner numbers are preserved as raw
diagnostic evidence. They miss the 1.10 throughput and 0.80 RSS design targets
and cannot authorize a claim. Controlled-host repetition, a Windows-native
resource collector, and the remaining named workload/platform matrix are
still required. This RFC therefore remains `Proposed`.

## 12. Alternatives and Risks

| Alternative | Why it is not selected |
| --- | --- |
| optimize before adding counters/reference workloads | makes regressions and claims unreviewable |
| use only microbenchmarks | misses buffers, TLS, cancellation, and long-lived Agent behavior |
| compare best Nomo run with average Go run | statistically and operationally unfair |
| make aspirational ratios hard merge blockers from P0 | can reward benchmark distortion before a correct baseline exists |
| infer portability from cross-compilation | does not exercise reactor race and cancellation behavior |

Harness maintenance and dedicated host capacity add cost, but they are smaller
than stabilizing an unmeasured concurrency model or publishing unsupported
performance claims.

## 13. Proposed Decision

Adopt these correctness, no-cost, allocation, resource, platform, device, and
benchmark gates as required evidence for RFCs 0031 through 0033. Treat the Go
ratios as explicit design targets until controlled results justify a narrower
claim. Keep all raw results and report misses without weakening the comparison.

## 14. References

- [Nomo Preview Stabilization Gate](../../RELEASE-GATE.md)
- [RFC 0031: Direct-style suspend functions and structured concurrency](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0032: Sharded executor, reactor, and blocking pool](./0032-sharded-executor-reactor-and-blocking-pool.md)
- [RFC 0033: Task ownership transfer and concurrent values](./0033-task-ownership-transfer-and-concurrent-values.md)
