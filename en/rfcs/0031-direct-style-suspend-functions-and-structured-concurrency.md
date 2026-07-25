# RFC 0031: Direct-Style Suspend Functions and Structured Concurrency

> Language: [中文](../../zh-CN/rfcs/0031-direct-style-suspend-functions-and-structured-concurrency.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0031 |
| Title | Direct-style suspend functions and structured concurrency |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-25 |
| Topics | suspend functions, effects, stackless coroutines, structured concurrency, cancellation, ARC, C99 |
| Related RFCs | [RFC 0003](./0003-arc-cow-runtime-cost.md), [RFC 0004](./0004-mutable-borrow-uniqueness.md), [RFC 0010](./0010-constrained-generics-and-static-interface-dispatch.md), [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md), [RFC 0026](./0026-isolated-native-tasks-and-cooperative-cancellation.md), [RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md), [RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md), [RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md), [RFC 0035](./0035-monotonic-suspend-timers-and-blocking-sleep-migration.md) |

## 1. Summary

Nomo adds `suspend fn` as an explicit function effect while keeping calls
direct-style: a suspending call is written like an ordinary call and does not
use an `await` expression. A normal `fn` remains an ordinary C99 function and
cannot call a `suspend fn`. Concurrent work is created only inside a lexical
`task.scope` through explicit `task.spawn` and is joined before the scope exits.

The C99 backend lowers each reachable suspend call chain to stackless state
machines. A coroutine frame stores only state and values live across a possible
suspension. Completion, cancellation, timeout, error-valued completion, and
panic cleanup share one exactly-once drop plan for ARC/COW values.

This RFC is `Proposed`. It defines the semantic gate for implementation; it is
not evidence that suspend functions or the runtime already exist.

## 2. Motivation

The synchronous pull APIs accepted by RFCs 0022 through 0024 can support a
small CLI Agent, but a blocked HTTP stream, process pipe, or timer occupies its
calling thread. RFC 0026 improves isolation by creating one native thread per
task, but that cost and its fixed copied-string boundary do not scale to many
mostly-idle Agent connections.

Nomo needs concurrency without imposing an async runtime, atomic reference
counting, or coroutine metadata on ordinary programs. It also needs cancellation
and ownership cleanup to be compiler-checkable rather than conventions spread
across application code.

## 3. Current State and Audit

- The lexer and AST have `fn` but no suspend/effect marker.
- The typed IR represents every function as a synchronous body and every call
  as an ordinary expression.
- The C99 backend emits direct C functions and already has detailed ARC/COW
  retain/release plans for branches, loops, `?`, `defer`, and returns.
- RFC 0026's `task fn` is a restricted callback type for an OS-thread runtime;
  it is not an async function declaration.
- Nomo has no general closures or user-visible lifetime syntax. The design must
  not require either one for its first structured-concurrency slice.

`task fn` and `suspend fn` therefore have different meanings. The former is a
compatibility callback for blocking work; the latter is a compiler effect that
participates in coroutine lowering.

## 4. Source Model

### 4.1 Function effect

`suspend` becomes a reserved keyword and precedes `fn`:

```nomo
suspend fn fetch(url: string) -> Result<HttpResponse, HttpError> {
    return http.send(HttpRequest.get(url))
}

fn normalize(value: string) -> string {
    return value.trim()
}
```

The effect is part of a function's type and exported signature. A function
value that may suspend is spelled `suspend fn(A, B) -> T`; it is not assignable
to `fn(A, B) -> T` or `task fn(A, B) -> T`.

The following effect rules are mandatory:

1. `fn` may call `fn`, but may not call `suspend fn`.
2. `suspend fn` may call both kinds. Calls stay direct-style.
3. Effect checking is transitive after name resolution and generic
   monomorphization.
4. FFI functions are synchronous unless a toolchain-owned runtime intrinsic
   explicitly exposes a pollable operation to a `suspend fn`.
5. A program may use `suspend fn main() -> void` or
   `suspend fn main() -> Result<void, E>` as its runtime entry. A synchronous
   `fn main` keeps the existing startup path and does not initialize async
   runtime state.

There is no `await` token in this design. The declared effect makes possible
suspension visible at function boundaries; structured operations make
concurrency visible at creation points.

### 4.2 Structured task scope

The first source form is a compiler-recognized block in the `std.task`
namespace:

```nomo
suspend fn load_pair(left_url: string, right_url: string)
    -> Result<Array<HttpResponse>, AgentError> {
    task.scope {
        let left = task.spawn fetch(left_url)
        let right = task.spawn fetch(right_url)
        let left_response = task.join(left)?
        let right_response = task.join(right)?
        return Ok([left_response, right_response])
    }
}
```

`task.spawn f(args...)` accepts exactly one call to a `suspend fn`. Arguments
evaluate once from left to right and are moved into the child. This restricted
form avoids introducing closures merely to capture a task body. The result is
`Task<T>`, where `T` is the callee return type.

`task.join(handle)` is itself a suspending operation. A task handle:

- is owned by its lexical scope;
- may be moved within that scope;
- may not be returned, stored globally, captured by a longer-lived value, or
  left unconsumed;
- may be joined once.

Every child is complete before `task.scope` returns. On normal scope exit,
unjoined children are cancelled and then joined. On an early `return`, `?`
propagation, or panic, sibling cancellation happens first, followed by child
cleanup and the original control transfer. This rule is semantic, not optional
library cleanup.

### 4.3 Cancellation, deadlines, and selection

Cancellation is cooperative but structured:

- a parent cancellation token is inherited by every child;
- cancelling a scope propagates to descendants;
- cancellation is observed before and after every runtime suspension and by
  explicit `task.check_cancelled()`;
- a pending I/O registration or timer is removed before its frame is dropped;
- cancellation never exposes a partially initialized return value.

`task.deadline(duration) { ... }` is a scope with a monotonic deadline. An
earlier parent deadline wins. Timeout is represented by a typed task/runtime
error at the operation that observes it; it is not a panic.

`task.select` waits for the first ready operation from a statically enumerated
set. Non-winning registrations are cancelled before the selected arm runs.
Selection order is deterministic for operations that were already ready when
the select began; the source order wins. The exact arm syntax may be refined
without changing these semantics before this RFC becomes `Accepted`.

Detached work is not a normal escape hatch. A `task.daemon_scope` capability is
available only to the process root or a host embedding API. It must name its
shutdown deadline and error sink. Ordinary libraries cannot detach children.

## 5. Type Checking and Suspension Safety

The compiler computes possible suspension points after call effects are known.
At each point it computes local-variable liveness and enforces:

- no mutable borrow, mutable receiver loan, C pointer borrow, lock guard, or
  runtime buffer view may cross the point;
- values stored in the frame must have a valid generated move/drop operation;
- a child task may receive only values allowed by RFC 0033's transfer rules;
- a local/affine runtime handle may be used only on its owner executor;
- `defer` actions in a suspend function must be synchronous and must remain
  valid on every state-machine exit.

An immutable owned value may live across suspension. This does not make its
backing reference count atomic: the frame and its owner task remain on one
executor shard unless an explicit transfer boundary is used.

## 6. C99 Lowering and ABI

### 6.1 Generated artifacts

Each monomorphized suspend function produces private C99 artifacts equivalent
to:

```c
typedef struct nomo_frame_fetch nomo_frame_fetch;
nomo_poll nomo_fetch_poll(nomo_frame_fetch *frame, nomo_context *context);
void nomo_fetch_drop(nomo_frame_fetch *frame);
```

The exact private symbol spelling is not stable API. The frame contains:

- a compact resume-state tag;
- initialization/move bits needed for exactly-once destruction;
- only parameters and locals live across a possible suspension;
- result storage when the caller owns it;
- parent cancellation/deadline and executor affinity metadata;
- child-frame or reactor-registration state only when that call site can be
  pending.

Locals whose lifetime ends before the first suspension remain ordinary C
locals. A suspend call that completes immediately continues in the same poll;
it does not enqueue the task or allocate another scheduling node.

### 6.2 Poll contract

`nomo_poll` has internal states for `READY`, `PENDING`, and runtime
termination. A Nomo `Result.Err` is an ordinary ready value, not a runtime
failure. Cancellation and timeout complete the structured operation through
its declared task/runtime error type.

A Nomo panic remains a defect rather than a recoverable exception. The runtime
marks the task panicking, cancels siblings, runs generated frame drops, and
then resumes process-level panic termination. User code cannot catch it.

### 6.3 Exactly-once drop

The lowering pass creates one cleanup table or equivalent control-flow plan
covering:

- ordinary return;
- `Result`/`Option` `?` propagation;
- observed cancellation;
- deadline timeout;
- reactor registration failure;
- child panic propagation;
- process-level panic cleanup.

Every initialized frame field has one ownership bit. Moving a field clears its
bit before a callee or result slot becomes responsible for it. Dropping a frame
tests and clears each bit. Tests must instrument retain/release counts and
prove that every path releases each ARC/COW value exactly once.

The coroutine ABI is toolchain-private in v0.1. Generated C from a different
compiler build is not link-compatible unless its recorded compiler/runtime ABI
revision matches.

## 7. Standard Library Impact

`std.task` gains structured-scope, typed task, cancellation, deadline, yield,
join, and select surfaces. Agent I/O APIs become suspend-capable according to
RFC 0032 while retaining direct call syntax.

RFC 0026 remains the historical contract for its accepted isolated native-task
API. Its `task fn`, `TaskContext`, and copied-string entry point are deprecated
compatibility surfaces and move onto the bounded blocking pool described by
RFC 0032. They do not become aliases for `suspend fn`.

## 8. Diagnostics

The first implementation reserves this diagnostic family:

| Code | Condition | Required guidance |
| --- | --- | --- |
| `E0870` | a synchronous `fn` calls a `suspend fn` | mark the caller `suspend` or move the call behind an explicit blocking boundary |
| `E0871` | `task.spawn` appears outside `task.scope` | wrap task creation in a structured scope |
| `E0872` | a task handle or scope-owned child escapes | join it inside the scope |
| `E0873` | mutable borrow, guard, or borrowed host view crosses suspension | end the borrow/guard before the suspending call |
| `E0874` | a `defer` action in a suspend frame can suspend or use invalid state | make cleanup synchronous and locally owned |
| `E0875` | a spawn target is not one direct `suspend fn` call | extract a named suspend function and pass explicit arguments |

Diagnostics must point to both the value's origin and the suspension/escape
site. JSON diagnostics and English/Chinese diagnostic documentation are part
of the implementation gate.

## 9. Test Plan

Positive tests cover direct suspend chains, immediate-ready calls, nested
scopes, typed results, cancellation, deadlines, selection, early return, `?`,
and legal immutable locals across suspension.

Negative tests cover each diagnostic above, including transitive effect calls,
generic instantiations, handle escape, double join, mutable field/index loans,
lock guards, and FFI borrows.

C99 lifecycle tests inspect generated frames and instrument all completion and
cleanup paths. Native integration tests run cancellation storms and panic
cleanup under sanitizers where supported. Browser WASM tests drive the same
state machines from a host event loop. RFC 0034 defines the performance and
cross-platform gates.

## 10. Compatibility, Alternatives, and Risks

`suspend` becomes reserved, which is a source break for an existing identifier
with that name. A migration diagnostic and formatter-assisted rename are
required. Effect changes are API changes and must appear in generated docs and
semantic/LSP data.

| Alternative | Why it is not selected |
| --- | --- |
| pervasive `async fn` plus `await` | adds syntax at every call site without improving the chosen direct-style effect boundary |
| stackful fibers | complicate C99 portability, memory bounds, and precise frame ownership |
| implicit spawn for every suspend call | hides concurrency, lifetime, cancellation, and backpressure |
| continue one native thread per task | fails the target cost model for many idle Agent connections |
| unrestricted detached tasks | makes shutdown, errors, and resource ownership non-local |

The main risk is compiler complexity around control-flow lowering and drop
correctness. Implementation must therefore land in reviewable slices and
cannot advance this RFC to `Accepted` until all gates in RFC 0034 are met.

## 11. Implementation Phases and Decision

The implementation order is:

1. effect metadata, call-graph checking, diagnostics, and benchmark hooks;
2. C99 state-machine IR/lowering with yield, timer, join, cancel, and drop tests;
3. structured scopes, deadlines, select, and integration with nonblocking I/O;
4. optimization only after correctness and measurement evidence.

**Proposed decision:** adopt explicit `suspend fn`, direct-style suspend calls,
and compiler-enforced structured task scopes. Do not add `await`, implicit
concurrency, or general detached tasks in the first version.

The spelling of `task.select` arms and daemon capability construction may be
refined in review. The effect boundary, stackless lowering, structured lifetime,
and exactly-once drop rules are not open implementation choices.

## 12. References

- [RFC 0026: Isolated native tasks and cooperative cancellation](./0026-isolated-native-tasks-and-cooperative-cancellation.md)
- [RFC 0032: Sharded executor, reactor, and blocking pool](./0032-sharded-executor-reactor-and-blocking-pool.md)
- [RFC 0033: Task ownership transfer and concurrent values](./0033-task-ownership-transfer-and-concurrent-values.md)
- [RFC 0034: Async runtime acceptance and benchmark gates](./0034-async-runtime-acceptance-and-benchmark-gates.md)
- [RFC 0035: Monotonic suspend timers and blocking sleep migration](./0035-monotonic-suspend-timers-and-blocking-sleep-migration.md)
