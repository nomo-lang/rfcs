# RFC 0026: Isolated Native Tasks and Cooperative Cancellation

> Language: [中文](../../zh-CN/rfcs/0026-isolated-native-tasks-and-cooperative-cancellation.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0026 |
| Title | Isolated native tasks and cooperative cancellation |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-25 |
| Topics | concurrency, tasks, isolation, cancellation, C99 backend, Agent |
| Related RFCs | [RFC 0003](./0003-arc-cow-runtime-cost.md), [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md), [RFC 0019](./0019-typed-ffi-handles-callbacks-and-bindings.md), [RFC 0022](./0022-structured-http-client-and-host-runtime.md), [RFC 0023](./0023-pull-based-http-streaming-and-sse.md), [RFC 0024](./0024-controlled-child-processes-and-stdio.md), [RFC 0025](./0025-structured-json-values-and-construction.md) |

---

## 1. Summary

Nomo v0.1 should add a deliberately narrow native task model for parallel,
independent Agent tools without introducing general function values,
closures, shared mutable memory, or `async`/`await`.

A task runs one non-capturing top-level `task fn` on a native OS thread. The
parent transfers one bounded string input by deep copy. The worker returns one
bounded string result, also copied before it becomes visible to the parent.
All Nomo managed values created by either side remain owned and reference
counted on that side's thread. The existing non-atomic string and array
reference counts therefore do not cross a thread boundary.

The first API provides bounded task creation, timed join, cooperative
cancellation, cancellation observation, and explicit close. A compiler-owned
task-safety analysis rejects a worker whose transitive call graph can enter
FFI, unsafe code, thread-confined host handles, or another task. Native
non-streaming `std.http` requests are included in the accepted task-safe set so
an Agent can execute independent network tools in parallel.

## 2. Goals and Non-goals

### 2.1 Goals

1. Run independent Nomo computations concurrently on Linux, macOS, and
   Windows.
2. Support parallel non-streaming HTTP tool calls for a native CLI Agent.
3. Preserve the existing non-atomic managed-value representation by copying
   all task boundary data.
4. Make resource limits, cancellation races, timeout behavior, and cleanup
   explicit.
5. Reject unsafe task call graphs at compile time instead of relying on
   documentation.
6. Keep the browser WASM sandbox deterministic through an explicit
   capability-denial result.

### 2.2 Non-goals

This RFC does not add:

- closures, capturing lambdas, or general first-class function values;
- shared Nomo objects, mutexes, atomics, arbitrary typed channels, or mutable
  globals;
- `async`/`await`, futures, work stealing, a green-thread scheduler, or an
  event-loop language transform;
- forced thread termination or panic isolation;
- streaming results, multi-producer channels, or task-to-task messaging;
- foreign-thread entry for application FFI callbacks;
- browser Web Workers;
- concurrent use of `HttpStream`, `ProcessChild`, sockets, servers, or other
  thread-confined handles.

## 3. Current Gap Audit

| Area | Current implementation | Gap |
| --- | --- | --- |
| Language calls | Named top-level functions; no function-value type or closures | No reusable unit of work can be passed to a scheduler |
| Managed values | Immutable string RC and array RC+COW are non-atomic | Sharing them between threads would race |
| HTTP | Structured HTTPS and pull-based streams exist | Independent non-streaming requests cannot run in parallel |
| Process | Controlled child handles and multiplexed I/O exist | The handle registry is thread-confined |
| FFI callbacks | Non-capturing `extern "C" fn` parameters exist | RFC 0019 rejects retained callbacks and foreign-thread runtime entry |
| Browser WASM | Single-threaded interpreter with capability denial | No native thread facility is available |
| Runtime | Platform code already uses Win32 threads internally for process I/O | No application-visible Nomo task lifecycle or ownership contract |

The gap is not solved safely by exposing `pthread_create` or `CreateThread`
through application FFI. That would make every application own callback ABI,
allocation, cancellation, and cross-platform policy while bypassing Nomo
lifecycle checks.

## 4. Detailed Design

### 4.1 Canonical `std.task` API

```rust
pub struct Task {
    handle: u64
}

pub struct TaskContext {
    handle: u64
}

pub struct TaskError {
    pub code: string
    pub message: string
}

pub enum TaskJoin {
    Completed(string)
    Cancelled
    Timeout
}

pub fn spawn(
    worker: task fn(TaskContext, string) -> string,
    input: string
) -> Result<Task, TaskError>

pub fn is_cancelled(context: TaskContext) -> bool
pub fn join(task: Task, timeout_millis: u64) -> Result<TaskJoin, TaskError>
pub fn cancel(task: Task) -> Result<void, TaskError>
pub fn close(task: Task) -> Result<void, TaskError>
```

`Task` and `TaskContext` are opaque. Their integer fields are compiler/runtime
implementation details and are not public.

The task callback type is only legal as the first parameter of
`std.task.spawn`. It is not a storable function value and cannot appear in a
struct, enum, return type, local binding, public user API, or FFI declaration.

### 4.2 Worker Declaration and Spawn

```rust
package parallel_agent_tools.main

import std.http
import std.task

fn call_tool(context: TaskContext, url: string) -> string {
    if task.is_cancelled(context) {
        return "{\"cancelled\":true}"
    }

    let response: Result<HttpResponse, HttpError> = http.get(url)
    match response {
        Ok(value) => {
            return value.body
        }
        Err(error) => {
            return error.message
        }
    }
}

fn run() -> Result<void, TaskError> {
    let first: Task = task.spawn(call_tool, "https://fixture.invalid/a")?
    let second: Task = task.spawn(call_tool, "https://fixture.invalid/b")?

    let first_result: TaskJoin = task.join(first, 5000)?
    let second_result: TaskJoin = task.join(second, 5000)?

    task.close(first)?
    task.close(second)?
    return Ok(())
}
```

The worker must be an unqualified, same-package, non-generic top-level
function with exactly this signature:

```rust
task fn(TaskContext, string) -> string
```

Methods, imported functions, extern functions, interface methods, closures,
and functions with `mut` parameters do not match. This constraint gives the C
backend a stable generated symbol and excludes hidden captures.

`spawn` validates the input limit, deep-copies its UTF-8 bytes into
runtime-owned storage, allocates a task state, and starts one native thread.
The worker creates a new Nomo string from that copy on its own thread. The
parent's input value is never retained by the worker.

### 4.3 Result Transfer

When the worker returns, the trampoline copies the returned string bytes into
runtime-owned task storage and releases the worker's Nomo string on the worker
thread. `join` creates a new Nomo string from those bytes on the parent thread.
No managed reference-counted allocation crosses the boundary.

`Completed` results may be observed by repeated `join` calls before `close`;
each observation returns an independently owned Nomo string. `close` releases
the runtime copy and invalidates the handle.

### 4.4 Limits

The first implementation fixes these limits:

- at most 64 live, unclosed tasks per process;
- at most 8 MiB of UTF-8 input per task;
- at most 8 MiB of UTF-8 output per task;
- `timeout_millis` in `0..=900_000`.

`timeout_millis == 0` is a non-blocking join. A larger timeout bounds only the
join operation; it is not an execution deadline and does not imply
cancellation.

An oversized worker result becomes a terminal `limit` error. The runtime must
still join and reclaim the native thread, and `close` must remain possible.

### 4.5 Completion, Cancellation, and Races

`cancel` is cooperative. It sets one runtime flag and wakes any task-runtime
waiters. The worker observes the flag through `is_cancelled(context)`.
Cancellation never invokes `pthread_cancel`, `TerminateThread`, asynchronous
signals, or long jumps.

The terminal outcome is determined under the task-state lock when the worker
returns:

- if the worker returns before cancellation is requested, later cancellation
  does not replace `Completed`;
- if cancellation is requested before the worker returns, its output is
  discarded and the terminal outcome becomes `Cancelled`;
- a cancellation request alone is not terminal because the worker may still
  be running; if the worker has not returned before the join deadline, `join`
  returns `Timeout`.

`cancel` is idempotent while the handle is live. It cannot interrupt a worker
currently blocked in another API. Task-safe blocking APIs must therefore have
their own finite timeout contract, and workers should check cancellation
between calls.

### 4.6 Close and Process Exit

`close` succeeds only after `Completed`, `Cancelled`, or a terminal runtime
error. Calling it while a worker is still running returns `busy`; it does not
detach or leak the thread. A successful close joins the native thread if
needed, releases input/output buffers and synchronization objects, removes the
registry entry, and invalidates the handle. A repeated close returns `closed`.

Programs are expected to cancel, join, and close every spawned task. Normal
process return with live tasks emits one generic diagnostic and performs
best-effort cancellation, but it must not wait forever for a non-cooperative
worker. The operating system remains the final cleanup boundary at process
exit.

### 4.7 Panic Behavior

The current Nomo panic path terminates the process. A panic in a worker is not
caught and converted into `TaskError`. Isolated panic recovery requires a
separate unwind/abort decision and is deferred.

### 4.8 Task-safe Call Graph

The compiler validates the worker and every transitively reachable Nomo
function before lowering `spawn`.

The initial task-safe set includes:

- pure language computation and local managed values;
- `std.option`, `std.result`, `std.array`, `std.string`, `std.char`,
  `std.path`, `std.math`, `std.num`, `std.hash`, `std.crypto`, `std.json`,
  `std.regex`, and `std.collections`;
- monotonic-clock reads and `std.time.sleep`;
- native non-streaming `std.http.send`, `get`, and `post`.

The initial forbidden set includes:

- any `unsafe` block, extern call, application FFI callback, or raw handle;
- `std.task.spawn` from a worker;
- `std.http` stream and server handles;
- `std.fs`, `std.env`, `std.process`, `std.net`, terminal I/O, logging, and
  debug output;
- any operation added later without an explicit task-safe classification.

The compiler emits a stable task-safety diagnostic that identifies both the
forbidden operation and a shortest call path from the worker. Unknown or
indirect effects are rejected conservatively.

This is a scoped effect check for task entry points, not a general effects
system or a promise that every accepted API is globally thread-safe.

### 4.9 Native HTTP Requirement

The toolchain-owned non-streaming HTTP runtime must be made safe for concurrent
independent requests before it is classified task-safe:

1. dynamic platform-library discovery and global initialization execute
   through a once/mutex gate before concurrent use;
2. initialized function tables are immutable;
3. each request owns its easy/session handle, headers, response buffer, and
   error state;
4. no `HttpStream` registry state is touched by task-safe requests;
5. Authorization values, request bodies, and response bodies remain excluded
   from runtime diagnostics.

### 4.10 Error Contract

`TaskError.code` is one of:

- `invalid_request`: invalid timeout or operation arguments;
- `limit`: live-task, input, or output limit exceeded;
- `spawn`: native thread or synchronization creation failed;
- `busy`: close requested before a terminal state;
- `closed`: stale or already-closed handle;
- `runtime_unavailable`: native tasks are unavailable on the current runtime;
- `internal`: an invariant or native wait failed.

Messages are stable and generic. They must not reproduce worker names, input,
output, prompts, URLs, headers, tokens, or response bodies.

Task-safety failures are compile-time diagnostics, not `TaskError` values.

### 4.11 C99 Backend

Generated native code uses:

- POSIX threads, mutexes, and condition variables on Linux and macOS;
- `CreateThread`, critical sections, events/condition variables, and wait
  functions on Windows.

The CLI owns the required platform link flags. Applications do not add
`pthread` or Win32 FFI metadata to `nomo.toml`.

The runtime registry and task buffers contain only native allocations,
callback pointers, integer handles, and synchronization state. The native
trampoline constructs and destroys Nomo managed values only on the worker
thread that owns them.

### 4.12 Browser WASM

The browser interpreter type-checks the same source and recognizes
`task.spawn`, but returns `runtime_unavailable` without invoking the worker.
Other task operations reject invalid handles. No Web Worker, shared memory, or
host import is added, and the 64 MiB sandbox memory gate remains unchanged.

## 5. Compatibility and Migration

The proposal is additive. Existing syntax, `std.process.spawn`, HTTP APIs, and
the non-atomic managed-value ABI remain unchanged.

`task fn` is a new restricted type form. It does not make ordinary functions
first-class and does not change the meaning of `fn` declarations. A later
general function-value design may provide an explicit conversion from a
compatible top-level function, but it must preserve this RFC's boundary-copy
and task-safety rules.

## 6. Alternatives

| Alternative | Benefit | Cost / reason rejected |
| --- | --- | --- |
| Full `async`/`await` first | General syntax and composability | Requires parser, type-system, lowering, scheduler, cancellation, and lifetime expansion before the Agent use case is proven |
| Shared-memory threads plus atomic RC | Familiar thread model | Makes every managed value cross-thread-capable, requires synchronization primitives and data-race rules, and rewrites the accepted v0.1 memory model |
| Generic typed channels first | Flexible actor-style programs | Requires a `Send`/serialization contract for every type and substantially expands monomorphized runtime code |
| OS process per task | Strong isolation | High startup cost, deployment complexity, and application-visible framing |
| Event loop with resumable Nomo functions | No OS-thread RC issue | Needs continuations/coroutines or a source transform that Nomo does not have |
| Host-specific application FFI | Small toolchain change | Repeats unsafe callback, ownership, and platform policy in every Agent |
| Isolated top-level task with copied string boundary | Bounded, useful for Agent tools, compatible with C99 and non-atomic RC | Fixed signature and one result per task; accepted for the first slice |

## 7. Drawbacks and Risks

- One native thread per task is heavier than a pool. The 64-task limit bounds
  the cost; pooling is deferred until behavior is measured.
- A non-cooperative worker cannot be safely forced to stop.
- A fixed string boundary requires JSON or another explicit protocol for
  structured input and output.
- Compile-time task-safety classification must remain synchronized with every
  new standard-library operation.
- Non-streaming HTTP globals need careful once initialization and concurrency
  stress coverage.
- The process-wide panic behavior is less isolated than an actor/process
  model.

## 8. Impact on the Native CLI Agent Goal

Together with RFCs 0022 and 0025, this slice allows a Nomo application to:

1. construct independent tool requests as JSON strings;
2. run multiple non-streaming HTTPS calls concurrently;
3. join each bounded result with explicit timeouts;
4. request cooperative cancellation;
5. parse results and continue the Agent loop without application-side C FFI.

It does not claim to reproduce a complete Hermes-style Agent, and it does not
yet parallelize streaming model responses or long-lived child-process tools.

## 9. Acceptance Gate

This RFC remains `Proposed` until all gates pass:

1. Parser, formatter, semantic model, docs, and both v0.1 specifications define
   the restricted `task fn` type consistently.
2. Canonical `std.task` source, standard-module registry, compiler lowering,
   typed IR, C99 codegen, and browser interpreter expose the exact API above.
3. Compile-time tests accept only an unqualified, same-package, non-generic
   top-level worker with the exact signature and reject every escaping or
   mismatched task callback form.
4. Task-safety analysis rejects direct and transitive forbidden operations and
   reports a stable diagnostic with the call path.
5. Native tests prove that input and result strings are deep-copied and that
   no non-atomic managed allocation crosses a thread boundary.
6. Tests cover completion, repeated join, zero/nonzero timeout, both
   completion/cancellation ordering outcomes, idempotent cancel, busy close,
   successful close, stale handles, and all exact limits.
7. A local TLS fixture proves at least two OpenAI-compatible non-streaming
   requests execute concurrently from Nomo workers without a real API key.
8. Secret sentinels in worker input, HTTP headers, request/response bodies, and
   oversized results never appear in errors, diagnostics, or default logs.
9. Lifecycle stress repeatedly spawns, joins, cancels, and closes tasks under
   AddressSanitizer/LeakSanitizer; a native race detector or equivalent stress
   gate covers registry, cancellation, join, and HTTP once initialization.
10. The native task conformance suite passes on Linux, macOS, and Windows.
    Real macOS arm64-to-x86_64 and Linux x86_64-to-arm64 cross-builds link the
    required thread runtime.
11. Browser WASM returns `runtime_unavailable`, adds no imports, and keeps the
    existing memory limit.
12. A Nomo example runs parallel JSON-described tool work, handles timeout and
    cancellation, and closes every task.
13. Formatting, Clippy, unit/CLI integration, release, WASM, cross-build, and
    platform smoke checks pass on the signed implementation PR and post-merge
    `main`.
14. Implementation lands from a signed child branch through a reviewed PR.
    Acceptance evidence and links are recorded here before the status changes
    to `Accepted`.

## 10. Deferred Follow-up

- A bounded worker pool and scheduling policy.
- Typed `Task<T>` and serialization-derived task messages.
- Streaming/multi-message channels and multi-producer ownership.
- Thread-safe controlled process and HTTP stream handles.
- Structured concurrency and lexical task scopes.
- Panic isolation.
- Browser Web Worker execution.
- General first-class functions, closures, futures, and `async`/`await`.

## 11. References

- `std/src/task.nomo` (proposed)
- `crates/nomo_syntax/src/parser.rs`
- `crates/nomo_compiler/src/expressions/expression_helpers.rs`
- `crates/nomo_codegen_c/src/runtime/host_http_client.c`
- `crates/nomo_codegen_c/src/runtime/host_task.c` (proposed)
- `crates/nomo_wasm/src/interpreter.rs`
- [POSIX Threads](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/pthread.h.html)
- [Windows threading and synchronization](https://learn.microsoft.com/windows/win32/sync/synchronization)
