# RFC 0033: Task Ownership Transfer and Concurrent Values

> Language: [中文](../../zh-CN/rfcs/0033-task-ownership-transfer-and-concurrent-values.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0033 |
| Title | Task ownership transfer and concurrent values |
| Decision Status | Proposed |
| Implementation Status | Partially implemented |
| Implementation Evidence | Publication moves in [`nomo#41`](https://github.com/nomo-lang/nomo/pull/41) and current-thread channel/select consumers in [`nomo#42`](https://github.com/nomo-lang/nomo/pull/42) and [`nomo#43`](https://github.com/nomo-lang/nomo/pull/43) |
| Author | Nomo Language Working Group |
| Created | 2026-07-25 |
| Topics | Send, Sync, Local, Freeze, move, channels, locks, concurrent collections, ARC, COW |
| Related RFCs | [RFC 0003](./0003-arc-cow-runtime-cost.md), [RFC 0004](./0004-mutable-borrow-uniqueness.md), [RFC 0010](./0010-constrained-generics-and-static-interface-dispatch.md), [RFC 0019](./0019-typed-ffi-handles-callbacks-and-bindings.md), [RFC 0030](./0030-collection-literals-indexing-and-ordered-map.md), [RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md), [RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md), [RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md), [RFC 0036](./0036-bounded-channels-publication-moves-and-static-select.md) |

## 1. Summary

Nomo keeps ordinary values and collections task-local with non-atomic ARC/COW.
Cross-task boundaries require a real move checked by compiler-known `Send`,
`Sync`, `Local`, and `Freeze` capabilities. A unique COW backing can move
without copying; an aliased backing detaches before publication so non-atomic
storage is never shared across workers.

Read-only sharing is explicit through `Frozen<T>`/`Shared<T>` and only that
storage uses atomic reference counting. Shared mutation is explicit through
async-aware `Mutex<T>`/`RwLock<T>` or purpose-built bounded channels and
concurrent containers. Normal `Array<T>`, RFC 0030's ordered `Map<K,V>`, future
`HashMap`/`Set`, and strings do not gain hidden locks or atomic RC.

This RFC is `Proposed`; capability inference, transfer lowering, and concurrent
containers do not exist merely because their contract is documented here.

## 2. Motivation and Current State

RFC 0003 deliberately chose non-atomic RC/COW for predictable single-thread
value semantics. RFC 0026 preserved that choice by copying a string at its
native-thread boundary and forbidding broad standard-library use inside tasks.
That is safe but too narrow for typed structured tasks and high-throughput
message passing.

Making every reference count atomic or every collection internally locked
would charge synchronous programs for concurrency they do not use. It would
also make compound operations appear safe while still racing. Nomo needs
explicit publication rules and specialized shared abstractions instead.

RFC 0030 accepts a deterministic insertion-ordered `Map<K,V>` with a bounded
linear index. It intentionally does not define `Hash`/`Eq` or a `HashMap`.
Concurrency work must preserve that contract rather than silently replacing
the map implementation.

## 3. Capability Model

The first version has compiler-known capabilities:

| Capability | Meaning |
| --- | --- |
| `Send` | an owned value may cross to another task/shard through the defined move-publication operation |
| `Sync` | the type's explicitly shared representation may be accessed from multiple tasks under its API |
| `Local` / `!Send` | the value is affine to one executor/host context and cannot cross a task boundary |
| `Freeze` | consuming the value can produce an immutable shareable snapshot |

These names are reserved semantic capabilities, not ordinary interfaces that
user code can implement unsafely in v0.1. The compiler derives them
structurally for structs/enums from all fields and from toolchain declarations
for host handles.

Primitive immutable scalars are `Send`, `Sync`, and `Freeze`. Function values
are `Send` only when their environment is empty and their ABI is allowed at the
target boundary. Raw/borrowed FFI pointers, mutable borrows, lock guards,
socket/stream/process/SQLite handles, and executor registrations are `Local`.

An owned struct/enum is `Send` when all fields can be published. It is `Freeze`
when all fields can freeze. Ordinary COW collections are `Send` by consuming
publication, not `Sync` merely because their element types are immutable.

## 4. Move Publication

`task.spawn`, channel send, and the rare eligible cross-shard scheduler move
are publication boundaries. The source binding is consumed and cannot be used
afterward.

For a non-atomic COW backing:

1. if the backing is unique, ownership moves to the destination with no element
   copy;
2. if local aliases exist, the publisher detaches/deep-copies the moved logical
   value before enqueueing it;
3. the destination receives a backing that no source-task alias references;
4. the queue publication uses the atomic shim's release/acquire edge.

This rule applies recursively to strings, arrays, ordered maps, and aggregate
fields. The compiler emits a type-directed `publish_move` helper only for
cross-task boundaries. Ordinary assignment retains existing local ARC/COW
behavior.

If detaching would exceed a configured collection/message bound, publication
returns a typed `TransferError`; it must not partially move the value.

## 5. Frozen and Shared Values

`freeze(value)` consumes a `T: Freeze` and returns `Frozen<T>`. It produces an
immutable representation that is `Send + Sync`. If ordinary backing is unique,
the runtime may move its payload into an atomic shared control block without
copying elements. If it is aliased, it first detaches.

`Shared<T>` is the explicit atomic ownership carrier used by the runtime and
shared primitives. `Frozen<T>` exposes read-only operations; it does not offer
mutable COW methods. Thawing consumes a uniquely held frozen value or creates a
detached task-local `T`.

Atomic reference counts exist only in these explicit shared control blocks and
runtime/channel metadata. Overflow is a panic-level defect; decrement-to-zero
uses acquire/release destruction. Nested ordinary values are immutable while
shared and are dropped once by the final owner.

## 6. Bounded Channels and Select

`Channel<T: Send>` is bounded at construction. Sending consumes `T`; receiving
produces owned `T`. Full senders and empty receivers suspend without blocking
an executor worker. `try_send`/`try_receive` return typed immediate outcomes.
Closing wakes all waiters; buffered messages remain receivable, and subsequent
sends fail.

The implementation may optimize same-shard channels without atomics, but
cross-shard behavior and ordering must be identical. Each waiter registers
once, cancellation removes it once, and a value is delivered to at most one
receiver. FIFO is required per sender and for a single receiver; global
multi-producer scheduling order is not promised.

RFC 0031's `task.select` can select channel send/receive, timer, task join, and
reactor operations. Registration, winner election, cancellation of losing
arms, and moved-value recovery must be atomic and exactly once.

RFC 0036 fixes the source-defined channel API, unconditional consuming-binding
rule with a typed rollback owner, static select arm syntax, capacity bounds,
and phased acceptance gates for these requirements.

## 7. Locks and Guards

`Mutex<T: Send>` and `RwLock<T: Send + Sync>` are explicit shared containers.
Acquisition is async-aware and may suspend before returning a guard. Waiters are
bounded or subject to configured admission backpressure.

Guards are `Local`, noncopyable, and may not cross any suspension point. The
compiler reports the guard origin and suspending call. Unlock is deterministic
at lexical end, explicit consume, `?`, early return, cancellation cleanup, and
panic cleanup.

This rule prevents deadlock-prone code such as:

```nomo
let guard = mutex.lock()
http.send(request) // error: guard would cross a suspension point
```

The program must copy/move the needed task-local value, release the guard, then
suspend. The runtime may use private short critical-section locks internally;
those are not the public async lock API.

## 8. Collections

### 8.1 Ordinary collections

- `Array<T>`, ordered `Map<K,V>`, future `HashMap<K,V>`, and `Set<T>` remain
  task-local non-atomic ARC/COW values.
- They do not contain hidden mutexes.
- Shared dynamic-array mutation uses `Mutex<Array<T>>`.
- Producer/consumer workloads use bounded `Channel<T>` or
  `ConcurrentQueue<T>`.
- There is no general `ConcurrentArray`.

### 8.2 Hash prerequisites

`HashMap`, `HashSet`, `ConcurrentHashMap`, and `ConcurrentSet` cannot ship until
a separate accepted RFC defines stable `Hash + Eq` coherence, numeric/string
rules, user-type derivation/implementation, hash-flood policy, and deterministic
testing. RFC 0030's ordered `Map` remains insertion ordered and is not renamed
or reimplemented as a hash map.

### 8.3 Specialized concurrent containers

After the hash contract exists:

- `ConcurrentHashMap<K,V>` starts with bounded shard locks;
- it provides compound `entry`, `compute`, compare-and-swap/replace, and
  remove-if APIs so callers do not compose racy get/set pairs;
- `ConcurrentSet<T>` follows the same shard and compound-operation rules;
- `ConcurrentQueue<T>` is bounded and offers suspend/try push-pop behavior;
- iteration is a documented snapshot or weakly consistent view, never implied
  globally atomic iteration.

Capacities, shard counts, per-operation allocation, and denial-of-service
bounds are explicit. These containers use atomic/shared storage because their
names and APIs opt into concurrent access.

## 9. Affine Resources

Socket, HTTP stream, server/exchange, process child/pipe, SQLite
database/query, reactor token, lock guard, and borrowed runtime buffer types
start as `Local/!Send`. They have one owner shard and an exclusive close path.

Applications send request/response data across tasks, not the handle. A future
resource may become transferable only after a focused RFC specifies how its
reactor registration, pending operations, buffers, and close authority move.

This rule replaces assumptions embedded in today's process-global handle
registries and prevents concurrent close/use races.

## 10. Diagnostics

| Code | Condition | Required guidance |
| --- | --- | --- |
| `E0880` | a `!Send`/`Local` value crosses spawn or channel publication | keep the handle local and send owned data |
| `E0881` | use after a publication move | point to the consuming boundary |
| `E0882` | a lock guard crosses a suspension point | release the guard before the call |
| `E0883` | a type cannot derive `Send`, `Sync`, or `Freeze` | show the first field/path that prevents it |
| `E0884` | a shared mutable operation targets ordinary COW storage | use a mutex, channel, or explicit concurrent container |
| `E0885` | a concurrent hash container is used without a stable `Hash + Eq` contract | identify the missing constraint/implementation |

Transfer errors and capacity/backpressure outcomes are typed and must not log
the transferred value. Compiler, LSP, generated docs, and English/Chinese
diagnostic references must agree.

## 11. C99 and Runtime Impact

The compiler generates type-specific local retain/release, `publish_move`,
freeze/thaw, shared-drop, and capability metadata. Ordinary helpers remain
non-atomic. Shared control blocks and concurrent primitives use RFC 0032's
private atomic shim.

Capability inference is recorded in typed IR and semantic tooling. Generated C
asserts/debug metadata may record an owner shard, but release builds do not add
owner checks to ordinary task-local collection operations.

Publish helpers are transactional: they finish all necessary detach/allocation
before consuming the source. Frame-drop ownership bits from RFC 0031 cover
values in partially prepared sends/select arms.

## 12. Test and Acceptance Plan

Tests must cover:

- structural capability derivation and every negative diagnostic;
- unique zero-copy and aliased-detach publication for nested COW values;
- use-after-move rejection;
- channel FIFO, close, saturation, cancellation, and winner races;
- lock fairness policy, cancellation, early return, panic drop, and guard
  suspension rejection;
- affine-handle cross-task and close/use rejection;
- atomic shared destruction exactly once;
- concurrent-map compound operations after the separate hash RFC.

Stress tests run under thread/address/undefined behavior tooling where each
platform supports it. Instrumentation records local versus atomic ARC traffic,
detaches, bytes copied, queue contention, and allocation counts. RFC 0034
defines the no-cost and performance gates.

## 13. Compatibility, Alternatives, and Risks

Capability bounds become part of exported generic APIs and can reject code
that RFC 0026 previously accepted only through copied strings. Because Nomo is
pre-1.0, the migration may tighten these boundaries, but diagnostics and
examples are mandatory.

| Alternative | Why it is not selected |
| --- | --- |
| atomic RC for every managed value | charges ordinary programs and hides the publication boundary |
| lock every collection | makes simple values heavier and does not make compound actions atomic |
| copy every task message | safe but loses unique-backing zero-copy transfer |
| share ordinary COW backing across workers | races its non-atomic reference count and uniqueness checks |
| one universal concurrent collection | obscures queue, map, lock, and snapshot semantics |
| make every handle `Send` | permits wrong-reactor access and close races |

The main risk is unsound capability inference or a missed alias during
publication. Initial capabilities remain compiler-owned, unsafe user
implementations are excluded, and transfer helpers receive exhaustive
lifecycle/stress tests before stabilization.

## 14. Proposed Decision

Adopt compiler-known `Send`, `Sync`, `Local/!Send`, and `Freeze`; consuming
publication with unique zero-copy/aliased detach; explicit frozen/shared
atomic storage; bounded channels; suspension-safe lock rules; and specialized
concurrent containers.

Do not change ordinary collection storage or RFC 0030's ordered-map semantics.
Require a separate `Hash + Eq` RFC before hash-based ordinary or concurrent
collections are implemented.

## 15. References

- [RFC 0003: ARC and COW runtime cost](./0003-arc-cow-runtime-cost.md)
- [RFC 0030: Collection literals, indexing, and ordered Map](./0030-collection-literals-indexing-and-ordered-map.md)
- [RFC 0031: Direct-style suspend functions and structured concurrency](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0032: Sharded executor, reactor, and blocking pool](./0032-sharded-executor-reactor-and-blocking-pool.md)
- [RFC 0034: Async runtime acceptance and benchmark gates](./0034-async-runtime-acceptance-and-benchmark-gates.md)
