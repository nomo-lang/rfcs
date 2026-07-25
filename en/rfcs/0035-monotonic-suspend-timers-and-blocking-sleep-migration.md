# RFC 0035: Monotonic Suspend Timers and Blocking Sleep Migration

> Language: [中文](../../zh-CN/rfcs/0035-monotonic-suspend-timers-and-blocking-sleep-migration.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0035 |
| Title | Monotonic suspend timers and blocking sleep migration |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-25 |
| Topics | suspend functions, timers, monotonic clock, cancellation, blocking compatibility, C99 |
| Related RFCs | [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md), [RFC 0026](./0026-isolated-native-tasks-and-cooperative-cancellation.md), [RFC 0029](./0029-bounded-utc-cron-schedule-calculation.md), [RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md), [RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md), [RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md) |

## 1. Summary

Nomo adds one monotonic, suspend-capable timer operation:

```nomo
pub suspend fn sleep(duration: Duration) -> Result<void, TaskError>
```

This declaration lives in `std.task`; callers use it as `task.sleep`.
`task.sleep` participates in RFC 0031's direct-style suspend effect and RFC
0032's owner-local timer wheel. A non-positive duration completes inline
without allocating, registering, enqueueing, or yielding. A positive duration
registers one bounded timer and returns `PENDING`; it resumes no earlier than
its monotonic deadline.

The existing synchronous `time.sleep` and `time.sleep_millis` remain available
to ordinary synchronous code and RFC 0026 compatibility workers during the
preview migration window. They are known-blocking operations and are rejected,
transitively, when reachable from a `suspend fn`. This keeps a blocking call
from occupying an async worker without forcing legacy `task fn` code through
the new coroutine model.

This RFC is `Proposed`. It is an implementation gate, not evidence that the
timer wheel or suspend timer has shipped.

## 2. Background and Motivation

RFCs 0031 and 0032 require a timer wheel, deadlines, cancellation, and a ready
fast path, but they do not settle the public sleep API or its migration from
the already implemented synchronous `std.time` functions.

The current implementation has:

- synchronous `time.sleep(Duration) -> void`;
- synchronous `time.sleep_millis(i64) -> void`;
- `task.yield_now()` as the first suspend runtime primitive;
- legacy `task fn` workers and cron examples that intentionally use blocking
  sleep outside the async executor;
- no timer registration, timer wakeup, or cancellation-safe timer state.

Changing `time.sleep` in place to `suspend fn` would break ordinary programs,
cron examples, and RFC 0026 workers before the bounded blocking-pool migration
exists. Keeping it callable from `suspend fn` would block unrelated async
tasks. Adding both `time.sleep_async` and `task.sleep_millis` would duplicate
the API and encode units in operation names despite the existing `Duration`
type.

The timer slice therefore needs an explicit suspend operation and an explicit
compatibility rule before implementation.

## 3. Detailed Design

### 3.1 Public API

`std.task` gains:

```nomo
import std.result
import std.time.Duration

pub suspend fn sleep(duration: Duration) -> Result<void, TaskError>
```

Typical use remains direct-style:

```nomo
package agent.main

import std.result
import std.task
import std.time

suspend fn heartbeat() -> Result<void, TaskError> {
    task.sleep(time.duration_seconds(1))?
    return Ok()
}
```

The API deliberately does not add `task.sleep_millis`. Callers construct a
`Duration` with `time.duration_millis` or `time.duration_seconds`. This keeps
units visible in one standard type and avoids parallel timer surfaces.

`TaskError` continues to use its stable public `code` and `message` fields.
The suspend timer may return:

| Code | Meaning |
| --- | --- |
| `timer_limit` | the owner executor's bounded timer capacity is exhausted |
| `runtime` | the target timer backend cannot register or wait correctly |

Messages are bounded and contain no source values or secrets. A non-positive
duration is not an error; it returns `Ok()` on the ready fast path.

### 3.2 Effect and Blocking Rules

`task.sleep` is a `suspend fn` intrinsic:

1. a synchronous `fn` cannot call it and receives E0870;
2. a `suspend fn` calls it without `await`;
3. the call is a possible suspension point for liveness, borrow, frame-drop,
   cancellation, and affinity checking;
4. generic and cross-module call summaries preserve the suspend effect.

The current `time.sleep` and `time.sleep_millis` remain synchronous
compatibility operations for one documented preview migration window. They
are classified as known blocking intrinsics. A `suspend fn` may not call them
directly or through a synchronous helper. E0891 reports the complete call path
and recommends `task.sleep`.

RFC 0026 `task fn` workers are not suspend functions and may continue using
the synchronous operations until they move to RFC 0032's bounded blocking
pool. The compatibility functions must be documented as blocking; they are
not an escape hatch for async code.

### 3.3 Time Semantics

`task.sleep` uses a monotonic clock. Wall-clock corrections, timezone changes,
and daylight-saving transitions do not change its deadline.

- `duration.millis <= 0`: return `Ok()` immediately;
- `duration.millis > 0`: compute a checked, saturating monotonic deadline and
  register one timer owned by the current executor shard;
- expiry makes the task eligible to run, but does not promise exact
  scheduling at the deadline;
- a task resumes only after the deadline and any already-ready work selected
  by the executor's fairness policy;
- very long durations may be reinserted in bounded timer-wheel rounds without
  changing the logical deadline.

The operation does not busy-poll. When no task is ready, a native executor
waits until the earliest timer or reactor event. A browser host records the
deadline and requests a host wakeup; it does not spin inside WebAssembly.

### 3.4 Cancellation and Drop

Each pending sleep owns exactly one generation-checked timer registration.

- parent or scope cancellation disarms the registration before dropping the
  coroutine frame;
- expiry and cancellation race through one owner-local terminal transition;
- a late event for a cancelled or reused slot is ignored by generation;
- the timer registration and any frame-owned `Duration` value are released
  exactly once;
- dropping an already completed or cancelled frame is idempotent.

Cancellation terminates the cancelled task according to RFC 0031. The
cancelled `task.sleep` body does not resume with an `Err` that user code could
ignore; the observing `task.join`/scope operation reports the typed
`cancelled` task outcome. `timer_limit` and local backend registration failure
occur before the operation becomes pending and return `Err(TaskError)` to the
same task.

Deadlines later reuse the same timer-registration primitive, but
`task.deadline` scope syntax and timeout result typing remain governed by RFC
0031's structured-scope phase.

### 3.5 Executor and C99 Lowering

For a possible pending sleep, the generated C99 frame contains only the state
required at that call site:

```c
typedef struct {
    uint32_t slot;
    uint32_t generation;
    int64_t deadline_millis;
    uint8_t armed;
} nomo_async_timer_registration;
```

The exact layout and symbol names are toolchain-private. The required
lowering is:

1. evaluate the duration once;
2. take the non-positive ready path inline;
3. try to reserve one bounded owner-local timer slot;
4. store and arm the registration before returning `PENDING`;
5. on a later poll, verify generation and terminal state;
6. clear `armed` before producing `Ok()` or transferring cleanup;
7. disarm through the same idempotent path on cancellation or frame drop.

The executor must distinguish cooperative yield from reactor/timer pending.
`task.yield_now` schedules the current task on the FIFO ready queue.
`task.sleep` does not immediately re-enqueue itself; only timer expiry schedules
it. A ready-only program never initializes timer storage. A zero-duration sleep
does not enqueue and does not allocate.

The first native current-thread implementation may wait with platform
monotonic facilities only when its ready queue is empty. Linux `epoll`,
macOS/BSD `kqueue`, Windows IOCP, and browser host-driven integration later
share the same registration contract from RFC 0032.

### 3.6 Structured Concurrency Interaction

A timer inherits the current task's owner shard, cancellation token, and
earliest parent deadline. It cannot be moved between shards while armed.
Spawning a child that sleeps creates a timer on the child's owner shard; the
parent does not poll or close that registration directly.

`task.select` and `task.deadline` may compose with the same primitive only
after their non-winning-registration cleanup and typed outcome rules are
implemented. This RFC does not introduce detached timers, callbacks, global
schedulers, or cron execution.

## 4. Type-Checking Rules

The compiler must:

- resolve `task.sleep` only with `std.task` or the specific import;
- require exactly one `Duration` argument;
- type the result as `Result<void, TaskError>`;
- apply the suspend-call rule E0870;
- include the call in suspension-point liveness;
- reject mutable borrows, guards, host views, or affine handles that illegally
  cross the sleep with E0873;
- reject direct or transitive blocking `time.sleep*` from a suspend function
  with E0891;
- keep synchronous `time.sleep*` legal in ordinary `fn` and legacy `task fn`
  compatibility workers.

No implicit conversion from integer milliseconds to `Duration` is added.

## 5. Standard Library Impact

`std.task` adds the source declaration and intrinsic identity for
`task.sleep`. `std.time.Duration` remains the single public duration type.
`std.time.sleep` and `std.time.sleep_millis` are documented as synchronous
blocking compatibility operations.

Generated documentation, semantic/LSP signatures, import completion, and
diagnostic examples must show the suspend effect and `Result<void, TaskError>`
return type.

## 6. Diagnostic Impact

| Code | Condition | Required guidance |
| --- | --- | --- |
| `E0870` | synchronous code calls `task.sleep` | mark the call chain `suspend` |
| `E0873` | an invalid borrow/guard/affine view crosses the timer | end it before sleeping |
| `E0891` | a suspend call chain reaches blocking `time.sleep*` | use `task.sleep` or move the whole operation to the bounded blocking pool |
| existing type/arity code | wrong duration, missing import, or ignored required shape | name the expected `Duration` and `Result<void, TaskError>` |

Diagnostics must not suggest `time.sleep*` as an async workaround.

## 7. Test and Acceptance Plan

Positive compiler and C99 tests cover:

- non-positive ready completion with zero allocation/enqueue/registration;
- positive timer ordering and no early wake;
- multiple equal-deadline timers with deterministic FIFO tie-breaking;
- direct and transitive suspend call chains;
- a managed local live across sleep with exactly-once frame drop;
- `timer_limit` before pending and recovery after capacity is released;
- cancellation before expiry, expiry/cancellation races, late events, slot
  generation reuse, and repeated drop;
- native current-thread execution without busy polling;
- host-driven browser WASM wakeup;
- unchanged synchronous `fn` codegen when async timers are unused.

Negative tests cover E0870, E0873, E0891 with a transitive call path, incorrect
arguments, and use of a timer registration from the wrong owner.

Sanitizer/debug counters must prove no timer, frame, buffer, or managed-value
leak. RFC 0034 benchmarks record zero-duration latency, timer insertion/expiry,
idle suspended-task RSS, cancellation storms, CPU while idle, and p50/p99/p999
wake latency on one-core/low-memory and normal hosts.

Platform CI must execute native timer behavior on Linux, macOS, and Windows;
a cross-build alone is insufficient. Browser tests must prove host wakeup and
bounded memory/fuel behavior.

## 8. Compatibility Impact

This proposal adds `task.sleep` without changing existing synchronous source
signatures. The source break is limited to calling known blocking
`time.sleep*` from a `suspend fn`, which was not safe under the new executor
contract. E0891 provides a direct migration.

The preview compatibility window for synchronous sleep ends only after the
bounded blocking pool and its explicit application surface are documented and
implemented. Removing or renaming `time.sleep*` requires a later RFC; this RFC
does not silently change their effect.

## 9. Alternatives

| Alternative | Why it is not selected |
| --- | --- |
| change `time.sleep*` in place to suspend | breaks ordinary and RFC 0026 worker code before a blocking compatibility path exists |
| permit `time.sleep*` on async workers | blocks unrelated tasks and violates RFC 0032 |
| add `time.sleep_async` | effect belongs in the signature; an `async` suffix duplicates that information |
| add `task.sleep_millis` | duplicates unit-bearing construction already provided by `Duration` |
| return `void` | cannot report bounded timer-capacity or local registration failure |
| busy-poll the monotonic clock | wastes CPU and prevents low-power/low-memory acceptance |
| implement cron callbacks here | conflates pure RFC 0029 schedule calculation with process scheduling and persistence |

## 10. Drawbacks and Risks

The compiler must add transitive known-blocking analysis in addition to
suspend-effect analysis. The executor must stop treating every `PENDING` poll
as an immediate ready-queue yield. Timer cancellation and generation reuse
introduce race-sensitive lifecycle state that requires native platform tests.

Keeping synchronous sleep during a preview window temporarily exposes two
operations with different execution models. Documentation and E0891 must make
that distinction explicit.

## 11. Unresolved Questions

No question blocks the first implementation slice. The eventual removal or
renaming of synchronous `time.sleep*`, the final `task.deadline` block syntax,
and public executor configuration are deferred to their respective migration
and structured-concurrency RFC work.

## 12. Final Decision

**Proposed decision:** add `task.sleep(Duration) ->
Result<void, TaskError>` as the only first suspend timer; use a monotonic,
bounded, owner-local, cancellation-safe registration with a zero-cost
non-positive ready path; and reject synchronous `time.sleep*` transitively on
async workers while preserving it for ordinary and legacy blocking code during
the preview migration.

The RFC remains `Proposed` until implementation, native/browser platform
tests, sanitizer lifecycle gates, documentation, and RFC 0034 benchmark
evidence are complete.

## 13. References

- [RFC 0026: Isolated native tasks and cooperative cancellation](./0026-isolated-native-tasks-and-cooperative-cancellation.md)
- [RFC 0029: Bounded UTC cron schedule calculation](./0029-bounded-utc-cron-schedule-calculation.md)
- [RFC 0031: Direct-style suspend functions and structured concurrency](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0032: Sharded executor, reactor, and blocking pool](./0032-sharded-executor-reactor-and-blocking-pool.md)
- [RFC 0034: Async runtime acceptance and benchmark gates](./0034-async-runtime-acceptance-and-benchmark-gates.md)
