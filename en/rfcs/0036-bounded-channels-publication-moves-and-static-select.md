# RFC 0036: Bounded Channels, Publication Moves, and Static Select

> Language: [中文](../../zh-CN/rfcs/0036-bounded-channels-publication-moves-and-static-select.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0036 |
| Title | Bounded channels, publication moves, and static select |
| Decision Status | Proposed |
| Implementation Status | Partially implemented |
| Implementation Evidence | P3-A [`nomo#41`](https://github.com/nomo-lang/nomo/pull/41), P3-B [`nomo#42`](https://github.com/nomo-lang/nomo/pull/42), P3-C [`nomo#43`](https://github.com/nomo-lang/nomo/pull/43); P3-D/P4 remain open |
| Author | Nomo Language Working Group |
| Created | 2026-07-26 |
| Topics | channel, select, move publication, Send, backpressure, cancellation, C99 |
| Related RFCs | [RFC 0003](./0003-arc-cow-runtime-cost.md), [RFC 0004](./0004-mutable-borrow-uniqueness.md), [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md), [RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md), [RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md), [RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md), [RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md), [RFC 0035](./0035-monotonic-suspend-timers-and-blocking-sleep-migration.md) |

## 1. Summary

This RFC refines the open source and ownership contracts left by RFCs 0031 and
0033. Nomo adds a bounded `Channel<T>` in `std.task`, compiler-checked
publication moves for values sent across task boundaries, and one
compiler-recognized `task.select` statement with statically enumerated arms.

The design keeps ordinary `Array<T>`, ordered `Map<K, V>`, strings, structs,
and enums task-local with non-atomic ARC/COW. Only explicit channel control
blocks, select winner metadata, and later cross-shard wakeups use the private
atomic runtime shim. A synchronous program that does not use async facilities
continues to emit no executor, channel, select, or atomic runtime.

This RFC is `Proposed`. It is an implementation gate, not evidence that the
capability, channel, or select acceptance tests have passed.

## 2. Audit and Problem

RFC 0033 already requires bounded channels with consuming sends, owned
receives, FIFO behavior, close wakeups, cancellation-safe waiter removal, and
typed immediate outcomes. RFC 0031 already requires deterministic selection
and exactly-once cancellation of losing registrations.

Those contracts are not sufficient to implement a public API:

- the exact channel functions and typed close/full outcomes are unspecified;
- Nomo has no implemented use-after-publication-move analysis;
- a failed or losing send must retain exactly one owner for its value;
- RFC 0031 explicitly leaves select arm syntax open;
- affine task handles and moved send values need defined loser behavior;
- channel capacity, waiter storage, browser behavior, counters, and the first
  reviewable implementation slice are not fixed.

Implementing directly from the older text would silently choose language
semantics in the compiler. This RFC closes those gaps before implementation.

## 3. Goals and Non-Goals

The goals are:

1. bounded producer/consumer backpressure without blocking an executor worker;
2. real consuming publication with structural `Send` checking;
3. deterministic, cancellation-safe selection over a small static arm set;
4. exactly-once ownership on success, full, close, cancellation, timeout, and
   losing-select paths;
5. a C99 ABI that can start current-thread and later cross owner shards without
   changing the source contract;
6. native and browser behavior that is either implemented or rejected before
   evaluating a value that would otherwise be consumed.

The first implementation does not add:

- an unbounded channel;
- a process-global channel registry;
- implicit actor mailboxes;
- general futures, closures, `await`, or dynamically assembled select sets;
- public lock-free memory ordering controls;
- a general user-implementable `Send` or `Sync` interface;
- a replacement for ordered RFC 0030 `Map<K, V>`.

## 4. Public Standard-Library Surface

The canonical source-defined surface is in `std.task`:

```nomo
pub struct Channel<T> {
    handle: u64
}

pub struct ChannelError {
    pub code: string
    pub message: string
}

pub struct ChannelSendError<T> {
    pub error: ChannelError
    pub value: T
}

pub enum ChannelTrySend<T> {
    Sent
    Full(T)
    Closed(T)
    Failed(ChannelSendError<T>)
}

pub enum ChannelTryReceive<T> {
    Value(T)
    Empty
    Closed
}

pub fn channel<T>(capacity: u64) -> Result<Channel<T>, ChannelError>
pub suspend fn send<T>(
    channel: Channel<T>,
    value: T
) -> Result<void, ChannelSendError<T>>
pub suspend fn receive<T>(channel: Channel<T>) -> Option<T>
pub fn try_send<T>(channel: Channel<T>, value: T) -> ChannelTrySend<T>
pub fn try_receive<T>(channel: Channel<T>) -> ChannelTryReceive<T>
pub fn close<T>(channel: Channel<T>)
```

All functions are compiler-known intrinsics with source-defined signatures and
documentation under RFC 0015. Generic type arguments remain explicit when
ordinary Nomo inference cannot determine `T`:

```nomo
let created: Result<Channel<string>, ChannelError> =
    task.channel<string>(64)
```

`Channel<T>` is an explicit shared runtime carrier, not an ordinary COW
collection. Copying a handle refers to the same bounded queue. `close` is
shared and idempotent; it does not consume every other handle.

### 4.1 Capacity bounds

A channel capacity must be from 1 through 65,536 elements. The checked buffer
size may not exceed 64 MiB, including slot metadata but excluding the explicit
channel control block. Multiplication and alignment use checked arithmetic.

Constructor failures use bounded, secret-safe codes:

| Code | Meaning |
| --- | --- |
| `invalid_capacity` | capacity is zero |
| `capacity_limit` | element count or checked byte size exceeds the v0.1 bound |
| `allocation` | the bounded control block or buffer could not be allocated |
| `runtime_unavailable` | the target has no channel backend |

No failure message contains a queued value, string contents, or derived debug
representation.

## 5. Publication Move Contract

`task.send`, `task.try_send`, and send arms of `task.select` are consuming
publication boundaries for their value argument. The same dataflow machinery
also applies to structured `task.spawn` arguments as RFC 0033 is implemented.

Nomo does not add a `move` keyword in this RFC. Consumption is determined by
the compiler-known parameter position:

```nomo
let message: string = build_message()
let sent = task.send(channel, message)
// error E0881: message was consumed by channel publication
```

Copy primitives may be copied into a publication boundary. A named non-copy
binding is unavailable after the boundary on every continuation path. A
temporary has no later source use.

Publication is transactional:

1. recursively validate the value against the compiler-known `Send` rules;
2. move logical ownership into an operation-local rollback slot and mark the
   source binding unavailable;
3. prepare every required COW detach and enforce message bounds while the
   rollback slot remains the single owner;
4. on success, clear the rollback owner and publish with one release/acquire
   edge when crossing a shard; on failure, move the rollback value into the
   typed outcome.

Unique COW backing moves without copying elements. Aliased backing detaches
before publication so a destination never shares an ordinary non-atomic
backing with the source task.

If publication preparation fails, the consuming operation returns one
`ChannelSendError<T>` that owns the logical value. The original binding is
still unavailable, but the caller can explicitly recover `error.value`.
`ChannelTrySend.Full(value)` and `ChannelTrySend.Closed(value)` use the same
rule. No path both retains the original binding and returns the value.

This refines RFC 0033's transactional wording: preparation cannot partially
publish or lose the logical value, but the source-language binding is
unconditionally consumed at the compiler-known boundary. v0.1 does not make
binding availability depend on which runtime outcome is later matched.

For a suspending send, the pending coroutine frame owns the prepared value.
Task cancellation or panic drops it once. A close wakeup returns it through
`ChannelSendError<T>`. Successful delivery clears the frame ownership bit
before the receiver or buffer becomes the owner.

## 6. Channel Semantics

### 6.1 Send and receive

`send` behaves as follows:

- if a receiver is already waiting, ownership is handed directly to the oldest
  eligible receiver and the send completes without buffering;
- otherwise, if the ring has capacity, the value is appended and the send
  completes;
- otherwise the sender registers once in FIFO order and suspends;
- if the channel closes before delivery, it resumes with
  `Err(ChannelSendError { error.code: "closed", value })`;
- structured task cancellation terminates the sending task under RFC 0031 and
  drops the frame-owned value rather than returning to user code.

`receive` behaves as follows:

- if a buffered value exists, it removes and returns the oldest value;
- otherwise, if a sender is waiting, it takes that sender's value directly;
- otherwise, if the channel is closed, it returns `None`;
- otherwise it registers once and suspends.

Buffered values remain receivable after close. `None` therefore means
"closed and drained", never merely "currently empty".

### 6.2 Immediate operations

`try_send` never suspends:

- `Sent` means a receiver or buffer owns the value;
- `Full(value)` means the open channel had no capacity;
- `Closed(value)` means the channel was closed;
- `Failed(error)` means publication preparation failed.

`try_receive` never suspends:

- `Value(value)` contains one owned value;
- `Empty` means open with no value currently available;
- `Closed` means closed and drained.

### 6.3 Close and destruction

`close` linearizes once, wakes every pending receiver and sender, and is
idempotent. Pending receivers first drain values that had already linearized
into the buffer; remaining receivers receive `None`. Pending senders whose
values had not been delivered receive the typed closed result.

A channel handle keeps its explicit control block alive. Wait registrations
hold a runtime reference while linked. Final destruction is therefore
impossible while a waiter still points at the channel. Final destruction drops
every buffered value exactly once.

FIFO is required for the ring, for one sender's sends, and for one receiver's
receives. Competing producers or consumers are ordered by registration
linearization; OS scheduling order is not promised.

## 7. Static Select Statement

`task.select` is a compiler-recognized statement with 2 through 8 source arms:

```nomo
task.select {
    task.receive(inbox) => received {
        if let Some(message) = received {
            io.println(message)
        }
    }
    task.sleep(time.duration_millis(250)) => elapsed {
        let checked: Result<void, TaskError> = elapsed
        io.println("idle")
    }
}
```

Each arm has one permitted operation, `=>`, one new immutable result binding,
and a lexical block. The binding type is inferred from the operation:

| Operation | Binding type |
| --- | --- |
| `task.receive(channel)` | `Option<T>` |
| `task.send(channel, value)` | `Result<void, ChannelSendError<T>>` |
| `task.sleep(duration)` | `Result<void, TaskError>` |
| `task.join(child)` | `Result<T, TaskError>` |

Arms are not closures and cannot be stored or dynamically appended. Arbitrary
suspend calls, nested `task.select` descriptors, `task.scope`, and
`task.deadline` are not selectable operations.

### 7.1 Evaluation and winner ordering

Select evaluates operation operands once, from top to bottom, without
suspending. It then checks cancellation and the effective deadline before
observing arm readiness.

If one or more arms are already ready, the first source arm wins. Otherwise
every arm registers at most once and the parent task suspends. Exactly one arm
may transition the shared select token from pending to won. Before its block
runs, every losing registration is removed or marked unable to win.

An inherited cancellation or deadline that is visible at the resume boundary
wins before an arm result, including an operation that became ready at the
exact deadline. This matches RFC 0031 deadline ordering.

Close, send, receive, timer, join, and cancellation races each have one
linearization point. Late wakeups are generation checked and cannot run a
losing arm or a reused frame.

### 7.2 Ownership of losing arms

A receive or timer arm owns no unpublished application value. Cancelling it
only removes its registration.

A send-arm value is consumed while the select frame is prepared. If that arm
wins, success transfers it or the arm binding receives a typed failure that
owns it. If that arm loses, select cleanup regains the value from the
registration into the select frame and drops it exactly once. It does not make
the original source binding available again.

An affine task handle named by a join arm is unavailable after the select
statement. A winning join consumes it normally. A losing join registration
does not cancel the child; ownership returns to the surrounding structured
scope for mandatory implicit cleanup. This deliberately avoids path-dependent
use of the source binding in v0.1.

The first implementation slice may support receive and sleep arms before send
and join arms, but unsupported shapes must produce a compile-time diagnostic
and must not be accepted by one backend only.

### 7.3 Arm control flow

The final semantics allow the selected arm to fall through, `return`, propagate
`?`, or panic. Losing registrations and staged values are cleaned before any
such exit. A smaller implementation slice may initially require flat,
fallthrough arm bodies under E0876, but the RFC cannot become `Accepted` until
all exits share the verified drop plan.

## 8. Capability Rules

`Channel<T>` exists only when `T` satisfies compiler-known `Send`. User code
cannot implement `Send` unsafely.

- immutable numeric, Boolean, and character values are copyable and `Send`;
- owned strings, arrays, ordered maps, and aggregates are `Send` through
  consuming publication and recursive detach;
- `Frozen<T>` and explicit shared carriers follow RFC 0033;
- socket, HTTP stream, process, SQLite, query, FFI pointer, borrowed value,
  mutable borrow, guard, and owner-reactor handles remain `Local/!Send` unless
  a later RFC provides an exclusive transfer operation;
- `Channel<T>` itself is an explicit shared handle and is `Send + Sync` when
  its element contract is valid.

Ordinary COW values do not become `Sync`, and this RFC adds no lock to ordinary
collections.

## 9. C99 Lowering and Runtime

Each monomorphized channel element type receives private helpers for:

- publication preparation and detach;
- move into and out of a ring slot;
- exactly-once slot/frame drop;
- optional debug-only type identity.

The channel control block contains a checked ring, closed state, handle count,
and intrusive FIFO heads/tails for sender and receiver waiters. Wait nodes live
inside coroutine/select frames, so waiting does not allocate one heap node per
suspension. Registration and cancellation unlink a node exactly once.

Current-thread operations may use owner-local non-atomic queue mutation.
Explicit shared lifetime metadata and cross-shard publication use RFC 0032's
private C99 atomic shim. GCC/Clang `__atomic_*` and Windows Interlocked are
runtime implementation details; ordinary generated values do not include
atomic fields.

A select frame contains one bounded array of arm registrations, one winner
token, result storage for the selected arm, staged ownership bits, and the
continuation state. The ready fast path does not enqueue or allocate. A
genuinely pending select uses the enclosing coroutine frame and at most one
owner-ready-queue entry when woken.

No process-global unsynchronized handle registry is permitted.

## 10. Errors and Diagnostics

This RFC uses the existing RFC 0033 codes and adds two select-shape codes:

| Code | Condition | Required help |
| --- | --- | --- |
| `E0880` | `Local/!Send` value crosses spawn or channel publication | identify the first non-Send field or handle |
| `E0881` | binding is used after a publication move | point to the consuming source boundary |
| `E0883` | structural `Send` derivation fails | show the field/path that prevents derivation |
| `E0886` | select has invalid arm count, syntax, or non-selectable operation | list supported static operations |
| `E0887` | affine join handle or moved send value escapes the select ownership rule | explain winner/loser ownership |

Runtime channel errors use stable codes such as `closed`, `transfer_limit`,
`capacity_limit`, `allocation`, and `runtime_unavailable`. Messages are
bounded and never format the transferred value.

Compiler, formatter, standard-library docs, LSP semantic data, English/Chinese
diagnostic pages, and browser capability errors must agree.

## 11. Platform and Browser Contract

Linux, macOS/BSD, and Windows must expose identical source ordering, close,
capacity, and ownership behavior. Platform atomics may differ internally.

Browser WASM uses the host-driven current-thread executor when channel/select
support is enabled. A backend without support returns or reports
`runtime_unavailable` before evaluating a constructor argument, send value, or
select arm operand that would be consumed. It may not run a sequential
"first arm" approximation.

## 12. Acceptance Gates

### 12.1 Semantic and ownership gates

Tests must cover:

- structural `Send` derivation and the first failing field path;
- use-after-publication-move across straight-line and branch control flow;
- unique COW zero-copy publication and aliased recursive detach;
- typed value recovery for full, closed, and transfer-limit outcomes;
- no duplicate retain/release or partially published value on failure.

### 12.2 Channel correctness gates

Tests must cover:

- exact element and byte capacity boundaries;
- FIFO wraparound and direct sender-to-receiver handoff;
- full/empty immediate outcomes;
- close while buffered, blocked send, blocked receive, and repeated close;
- cancellation before registration, while linked, and after wake;
- root/child drop, panic, timeout, and queue saturation under ASan/UBSan;
- cross-shard stress under TSAN when the sharded executor exists.

### 12.3 Select correctness gates

Tests must cover:

- source-order choice when multiple arms are pre-ready;
- one winner under send/receive/timer/join races;
- cancellation and deadline priority at resume;
- losing registration removal and late-event rejection;
- losing send-value and losing join-handle cleanup;
- `return`, `?`, panic, and frame drop after a winner;
- fixed arm-count and registration-memory bounds.

### 12.4 Performance and no-cost gates

The counter catalog adds, at minimum:

- channel constructions and close transitions;
- buffered sends/receives and direct handoffs;
- send and receive suspensions;
- publication detaches and copied bytes;
- select registrations, immediate wins, suspended wins, and loser
  cancellations;
- live and peak buffered elements/waiters.

RFC 0034's bounded-channel workload measures same-shard and later cross-shard
throughput, backpressure, fairness, p50/p99/p999 latency, RSS, and cancellation
storms against the pinned Go baseline. These measurements are evidence, not a
predeclared performance claim.

A sync-only program and an async program that never constructs a channel or
select must contain no channel storage, atomic shim call, or select metadata.

## 13. Implementation Phases

Implementation is split into reviewable PRs:

1. **P3-A capability and move dataflow — implemented by
   [`nomo#41`](https://github.com/nomo-lang/nomo/pull/41):** compiler-known `Send` derivation,
   publication move/use-after-move analysis, IR ownership bits, and tests; no
   public channel yet.
2. **P3-B current-thread channel — implemented by
   [`nomo#42`](https://github.com/nomo-lang/nomo/pull/42):** constructor, send/receive, try operations,
   close, managed-value detach/drop, counters, native/browser capability gate.
3. **P3-C static receive/timer select — implemented by
   [`nomo#43`](https://github.com/nomo-lang/nomo/pull/43):** exact parser/formatter form, immediate
   source ordering, pending registration, cancellation, deadline, and loser
   cleanup.
4. **P3-D send/join select — planned:** staged moved values, affine join ownership, early
   exits, and complete diagnostics.
5. **P4 cross-shard publication — planned:** private atomic shim, owner wakeup, stress
   tests, and per-core evidence.

RFCs 0031, 0033, and this RFC remain `Proposed` until the implementation,
cross-platform CI, sanitizer tests, browser contract, and RFC 0034 benchmark
gates all pass. Merging this document does not mark any of them `Accepted`.

## 14. Alternatives

| Alternative | Why it is not selected |
| --- | --- |
| unbounded channels | hides memory growth and removes backpressure |
| lock every ordinary collection | charges synchronization to non-concurrent code and breaks the task-local ARC/COW model |
| dynamically allocated future arrays | requires a futures/closure model and unbounded registration storage |
| `select2`, `select3`, and `select4` functions | avoids syntax temporarily but produces heterogeneous carrier types and does not express arm-local control flow |
| poll readiness then perform the operation | introduces a race between observation and consumption |
| restore losing send values to their original bindings | requires path-dependent binding availability not otherwise present in v0.1 |
| cancel child tasks for losing join arms | confuses cancellation of a wait registration with cancellation of the child |
| silently fall back to sequential browser execution | violates selection and cancellation semantics |

## 15. Risks

Publication detach can be expensive for aliased nested COW values. Counters and
message bounds make that cost visible. Cross-shard channel correctness is
substantially harder than the current-thread slice; it is deliberately gated
behind the atomic shim and stress evidence.

Consuming call positions are a new dataflow obligation even without a `move`
keyword. Diagnostics must make the boundary obvious. If this proves too
surprising in real use, a future RFC may add explicit ownership annotations,
but implementations must not invent syntax before that review.

## 16. Proposed Decision

Adopt the exact bounded channel API, implicit compiler-known publication moves,
and static `task.select` arm syntax in this RFC. Implement capability/move
checking first, then current-thread channels, then receive/timer selection,
before send/join arms and cross-shard optimization.

## 17. References

- [RFC 0031: Direct-style suspend functions and structured concurrency](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0032: Sharded executor, reactor, and blocking pool](./0032-sharded-executor-reactor-and-blocking-pool.md)
- [RFC 0033: Task ownership transfer and concurrent values](./0033-task-ownership-transfer-and-concurrent-values.md)
- [RFC 0034: Async runtime acceptance and benchmark gates](./0034-async-runtime-acceptance-and-benchmark-gates.md)
- [RFC 0035: Monotonic suspend timers and blocking sleep migration](./0035-monotonic-suspend-timers-and-blocking-sleep-migration.md)
