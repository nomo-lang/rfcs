# RFC 0039: Loop-Carried Coroutine State and Suspension-Safe Mutation

> Language: [中文](../../zh-CN/rfcs/0039-loop-carried-coroutine-state-and-suspension-safe-mutation.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0039 |
| Title | Loop-carried coroutine state and suspension-safe mutation |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-27 |
| Topics | suspend functions, loops, mutable locals, liveness, ARC, C99, MCP |
| Related RFCs | [RFC 0003](./0003-arc-cow-runtime-cost.md), [RFC 0004](./0004-mutable-borrow-uniqueness.md), [RFC 0028](./0028-bounded-json-rpc-and-newline-stdio-framing.md), [RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md), [RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md), [RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md), [RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md), [RFC 0038](./0038-owner-affine-async-process-pipes-and-blocking-migration.md) |

## 1. Summary

Nomo extends the RFC 0031 stackless-coroutine model with a bounded v0.1
control-flow slice for loops whose body can suspend. Task-local owned mutable
locals may carry state across a suspension and a loop backedge, while mutable
borrows, guards, raw/FFI views, and executor-affine borrowed resources remain
forbidden across the suspension point.

The C99 backend lowers the loop to explicit condition, suspension, resume, and
backedge states in the existing coroutine frame. Assignment uses the ordinary
ARC/COW move/drop rules, and cancellation or failure drops the currently
initialized loop-carried value exactly once. This enables a real incremental
MCP stdio loop without adding `await`, atomic reference counting to ordinary
values, recursive coroutine frames, or a transport-specific runtime intrinsic.

This RFC is `Proposed`. It becomes `Accepted` only after the compiler,
C99/browser paths, diagnostics, cross-platform async MCP fixture, lifecycle
counters, and RFC 0034 cost gates pass.

## 2. Motivation

RFCs 0028 and 0038 provide the reusable pieces of a Nomo-native MCP client:
bounded JSON-RPC newline framing and owner-affine async process pipes. A real
client still cannot compose them because process output is arbitrarily
fragmented and interleaved. The decoder and completion flags must survive an
unknown number of `process.next_event` suspension points:

```nomo
suspend fn exchange(
    child: ProcessChild,
    decoder: JsonRpcDecoder
) -> Result<JsonRpcDecoder, McpError> {
    let mut state: JsonRpcDecoder = decoder
    let mut received: bool = false
    for !received {
        let next: Result<ProcessEvent, ProcessControlError> =
            process.next_event(child, 65536, 5000)
        // Synchronous matching updates state and received.
    }
    return Ok(state)
}
```

The current implementation reports E0876 because the first lowering slice
accepts only immutable top-level locals and sequential suspension points.
Unrolling a fixed number of reads would be incorrect: pipe chunking and stderr
interleaving are platform- and scheduling-dependent. Keeping the blocking MCP
example would occupy an async worker. Hiding the loop in a new MCP-specific C
intrinsic would make JSON-RPC, process cancellation, and error handling less
composable.

The language therefore needs a small, audited CFG/state-machine extension
before P2-PROC-E can honestly claim a native async MCP loop.

## 3. Status and Problem

RFC 0031 already requires stackless C99 frames, liveness-derived storage,
owner affinity, and exactly-once cleanup. It explicitly permits immutable
owned values across suspension and forbids mutable borrows and guards. It does
not yet define a loop-carried mutable owned local or the first implementation
shape for a suspension inside a loop.

The current compiler conservatively rejects:

- every mutable local in a suspend function;
- suspension nested in a loop or branch;
- recursive suspension;
- most `?`, `return`, `break`, `continue`, `defer`, and panic shapes around a
  suspension.

This is safe but insufficient for incremental streams, SSE, MCP stdio,
long-running Agent event loops, and bounded retry loops. The missing decision
is not whether mutable borrows may cross suspension—they may not—but how an
owned task-local value is stored, overwritten, and dropped across a loop
backedge.

## 4. Detailed Design

### 4.1 Source syntax and v0.1 shape

No new source syntax is added. `suspend fn` and the existing conditional
`for condition { ... }` form are reused.

The first accepted implementation shape is:

- a non-suspending Boolean loop condition;
- one non-nested loop in a suspend function;
- one or more direct suspend calls in the loop body, each either a standalone
  void call or an immutable `let`-bound result;
- synchronous statements, `if`, and `match` after a resumed result;
- task-local mutable locals declared outside the loop and assigned in the
  loop body;
- normal fallthrough to the backedge and normal function return after the
  loop.

The first slice continues to reject a suspension in the loop condition,
initializer, or update; nested suspending loops; suspending calls inside
conditional arms; and `break`, `continue`, early `return`, `?`, `defer`, or
panic paths that would cross the loop suspension. These are later CFG slices,
not silently accepted approximations.

### 4.2 Suspension-safe mutable locals

A mutable local may be live across suspension when all of the following hold:

1. the local owns its value; it is not a borrow, guard, pointer, runtime buffer
   view, or borrowed FFI value;
2. its type has generated frame move/drop operations;
3. no borrow or guard derived from it is live across the suspension;
4. it remains on the same owner executor unless an explicit RFC 0033 transfer
   boundary consumes it;
5. each assignment is complete before the next suspension point.

This permission does not make the value `Send`, `Sync`, shared, locked, or
atomically reference counted. The frame remains task-local. `Array<T>`,
ordered `Map<K,V>`, strings, and other ARC/COW values continue using their
ordinary non-atomic backing. Normal COW detachment occurs only when an actual
mutation observes an alias.

A mutable parameter remains outside the first slice. Callers can move an owned
value into an immutable parameter and initialize a mutable task-local frame
slot from it.

### 4.3 Evaluation and assignment

The loop condition is evaluated on entry and after every completed body
iteration. A suspend call that returns ready continues in the same poll. A
pending call records its resume state and returns `PENDING`.

Assignment to a managed loop-carried local follows one transaction:

1. evaluate the right-hand side into owned temporary storage;
2. if evaluation succeeds, move/retain the new value into the frame slot;
3. release the previous initialized value exactly once;
4. update the slot initialization/move bit;
5. continue to the next statement or loop backedge.

If evaluation terminates the task, the previous frame value remains the
single initialized value to drop. No half-assigned state is observable.

### 4.4 C99 state-machine lowering

Each supported loop produces private labels equivalent to:

```c
NOMO_STATE_LOOP_CONDITION
NOMO_STATE_LOOP_SUSPEND_0
NOMO_STATE_LOOP_RESUME_0
NOMO_STATE_LOOP_BACKEDGE
NOMO_STATE_AFTER_LOOP
```

The concrete numbering remains private ABI. The poll function uses a switch
or equivalent C99 control flow. The backedge jumps to the condition state; it
does not recursively call the poll function and does not allocate another
frame.

Frame layout contains:

- mutable loop-carried locals live across a possible suspension;
- immutable parameters/results live across the same points;
- one child frame or reactor registration per currently reachable suspension
  site;
- initialization/move bits needed for exactly-once cleanup.

The compiler must perform liveness over the loop CFG. A conservative preview
may retain more frame-safe locals while correctness is being established, but
RFC 0034 claim eligibility requires only values live across a possible
suspension to remain in the stabilized frame.

### 4.5 Cleanup, cancellation, and errors

Every exit funnels through the RFC 0031 frame-drop plan. On cancellation,
timeout, runtime failure, or panic:

- the active child operation is cancelled/dropped first;
- each initialized loop-carried slot is released exactly once;
- overwritten values are never released again;
- owner-affine handles are closed only by their documented cleanup owner;
- no backedge or synchronous tail statement executes after termination.

An ordinary `Result.Err` returned by the suspended operation is a ready value.
Synchronous code in the loop may store it, set a completion flag, or finish
normal iteration. General early `?` propagation around a loop suspension is
not part of this first slice.

### 4.6 Diagnostics

Existing codes remain the compatibility boundary:

- E0873 reports a mutable borrow, guard, raw/FFI view, or borrowed runtime
  value that is live across the loop suspension;
- E0876 reports an unsupported suspending-loop shape and names the supported
  direct-call/fallthrough form;
- existing Local/!Send diagnostics continue to reject owner escape or
  publication.

Diagnostics must point to both the local/borrow origin and the relevant
suspension or backedge when both spans are available. They must not print
process arguments, JSON-RPC payloads, tokens, or child output.

### 4.7 Standard library and browser impact

No transport-specific intrinsic is added. `std.process` and `std.jsonrpc`
remain independent, and the Nomo example composes their public APIs.

The browser interpreter executes pure supported loops under its existing fuel
limit. A browser call to `process.next_event` still fails at the process
capability boundary before operand evaluation; this RFC does not create a
browser subprocess capability.

## 5. Acceptance Gates

The implementation PRs must provide:

1. positive compiler/C99 tests for zero, one, and many iterations with two
   suspension sites and mutable scalar plus managed ARC/COW state;
2. negative E0873 tests for a mutable borrow, guard, FFI pointer/view, and
   borrowed runtime buffer across the loop suspension;
3. negative E0876 tests for nested suspending loops, suspending conditions,
   branch-nested suspension, and unsupported early exits;
4. generated-C checks for explicit backedges, no recursive poll call, and
   frame slots limited to live values;
5. retain/release counters for overwrite, ready completion, pending resume,
   error-valued completion, cancellation at every suspension site, timeout,
   and panic cleanup;
6. a Nomo `mcp_stdio_async` example that handles fragmented and coalesced
   JSON-RPC messages plus interleaved stderr through a local fixture;
7. Linux epoll/`pidfd`, macOS kqueue/`EVFILT_PROC`, and Windows IOCP execution
   of the same example with zero live frame/process/reactor/IOCP state;
8. browser pure-loop parity and process-capability rejection;
9. RFC 0034 evidence that unused async code has no new cost, ready iterations
   do not allocate or enqueue, and a pending loop uses only its existing frame
   plus operation registration.

The RFC stays `Proposed` until all applicable gates pass.

### 5.1 Implementation evidence after `nomo#57`

[`nomo#57`](https://github.com/nomo-lang/nomo/pull/57) implements the first
bounded slice without widening the source syntax. Validation accepts one flat
top-level conditional loop with a synchronous condition, direct suspension
sites, immutable resumed results, synchronous fallthrough, and assignment to
owned mutable locals declared before the loop. Unsupported nested loops,
suspending conditions, branch-nested suspension, `break`, `continue`, `?`,
`defer`, panic, and early-exit shapes remain rejected with E0876.

The C99 backend emits explicit condition and backedge labels in the existing
stackless poll function. Scalar and managed ARC/COW values that remain live
across a possible suspension are stored in the frame. Managed assignment
retains or moves the replacement before releasing the previous slot, and loop
cancellation releases the currently initialized value once. Compiler and CLI
tests cover zero, one, and many iterations with two suspension sites;
generated-C assertions lock the non-recursive backedge; and the cancellation
path is checked with lifecycle counters and ASAN where available.

The new `examples/mcp_stdio_async` program contains only Nomo application code
and composes the public `std.process` and `std.jsonrpc` APIs. Its local fixture
splits the first JSON-RPC response, coalesces a notification with the second
response, and uses stderr independently. The same example passes Linux,
macOS, and Windows pull-request jobs with zero live process handles,
operations, retained process bytes, blocking jobs, reactor registrations, and
timers.

The Windows run exposed an IOCP race that was fixed in the same PR: stdout and
stderr overlapped reads now belong to stable owner-affine `ProcessChild`
slots, not to one temporary `next_event` pull. A stdin-flush or exit completion
therefore cannot cancel and discard bytes that Windows has transferred before
the read completion packet is dispatched. Close and cancellation detach the
buffer until IOCP drains the late completion.

[`nomo#58`](https://github.com/nomo-lang/nomo/pull/58) adds two focused
lowering regressions discovered by the process stress program. Transitive
suspend calls inside the accepted loop now use the complete global call graph
instead of a second single-function validation pass. Frame aliases restored
at the loop condition are additionally filtered by last use, so a managed
local that crossed an earlier suspension but died before the loop is not
reintroduced as an undeclared or stale C99 local. The 16-child saturation and
32-round slot-reuse example exercises the corrected path across Linux, macOS,
and Windows.

This evidence satisfies the core bounded-loop and native MCP composition
slices, but it does not complete every gate above. The full E0873
borrow/guard/FFI-view matrix, per-suspension timeout/panic/error cleanup
matrix, browser pure-loop evidence, stabilized minimal-frame proof, and focused
RFC 0034 ready/pending cost report remain open. The RFC therefore remains
`Proposed`.

## 6. Alternatives

| Option | Approach | Advantages | Disadvantages |
| --- | --- | --- | --- |
| Loop-carried frame state (proposed) | lower owned mutable locals and loop backedges into the existing stackless frame | direct Nomo code, reusable for MCP/SSE/retries, no extra thread or recursive frame | requires CFG liveness and careful drop planning |
| Recursive suspend driver | pass decoder state through a recursive suspend function | immutable source parameters | needs dynamically sized/nested frames and conflicts with the current acyclic call gate |
| MCP-specific runtime intrinsic | implement the entire exchange loop in C/runtime code | smaller compiler change | transport-specific, hides cancellation/framing, reduces reuse, expands trusted runtime |
| Keep blocking or fixed unrolling | continue using blocking process APIs or assume a fixed event count | no compiler work | blocks async workers or is incorrect under real pipe fragmentation |

Adding `await`, async generators, or a general stream protocol is not required
for this problem and would expand the v0.1 surface unnecessarily.

## 7. Drawbacks and Risks

CFG liveness and exactly-once drop across a loop are substantially more
complex than sequential state numbering. Managed assignment can expose double
release, leak, or stale-slot bugs. Platform event order makes tests flaky if
the Nomo loop or fixture assumes a fixed chunk count.

The mitigations are a deliberately narrow first shape, deterministic local
fixtures, per-suspension cancellation tests, generated-C inspection,
sanitizers where supported, and exact runtime counters. Unsupported control
flow continues to fail with E0876.

## 8. Impact on v0.1

This is required for the P2-PROC-E async MCP gate and for an honest
Nomo-native Agent event loop. The v0.1 minimum is the bounded loop form in
section 4.1, task-local owned mutation, and the complete acceptance matrix in
section 5.

Nested arbitrary CFG suspension, mutable parameters, recursive suspend
functions, async generators/iterators, suspension in loop conditions, and
general early-exit lowering may remain for later RFCs or v0.2.

## 9. Proposed Decision

Adopt loop-carried task-local owned state in the existing direct-style
stackless coroutine model. Preserve the hard rule that borrows and guards do
not cross suspension. Lower loops to non-recursive C99 CFG states, reuse
ordinary ARC/COW storage, and gate expansion on exact cleanup and cost
evidence.

## 10. Open Questions

- Whether the next CFG slice should prioritize `?` propagation, `break` and
  `continue`, or branch-nested suspension.
- Whether stabilized liveness needs a dedicated diagnostic/explain mode for
  developers inspecting frame size.
- Whether future async iterators should compile to this loop machinery or use
  a separate protocol.

## 11. References

- [RFC 0031: Direct-style suspend functions and structured concurrency](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0034: Async runtime acceptance and benchmark gates](./0034-async-runtime-acceptance-and-benchmark-gates.md)
- [RFC 0038: Owner-affine async process pipes and blocking migration](./0038-owner-affine-async-process-pipes-and-blocking-migration.md)
