# RFC 0038: Owner-Affine Async Process Pipes and Blocking Migration

> Language: [中文](../../zh-CN/rfcs/0038-owner-affine-async-process-pipes-and-blocking-migration.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0038 |
| Title | Owner-affine async process pipes and blocking migration |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-27 |
| Topics | process, async pipe, reactor, MCP, owner affinity, blocking pool, migration |
| Related RFCs | [RFC 0024](./0024-controlled-child-processes-and-stdio.md), [RFC 0028](./0028-bounded-json-rpc-and-newline-stdio-framing.md), [RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md), [RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md), [RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md), [RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md), [RFC 0037](./0037-owner-affine-async-tcp-client-and-blocking-migration.md) |

## 1. Summary

Nomo's controlled child-process API gains an owner-affine, reactor-backed
path suitable for a long-lived MCP stdio client. `process.start` and
`process.next_event` become direct-style suspend operations. Bounded stdin
queueing, close-stdin, non-consuming exit observation, termination request,
and close remain synchronous operations that do not wait on the async worker.

The new `ProcessChild` identifies a generation-checked slot owned by one
executor. Unix pipes are nonblocking reactor sources; Windows uses overlapped
pipes and IOCP rather than three helper threads per child. Potentially blocking
process creation runs through a bounded lazy blocking job queue and returns
completion to the owner executor.

RFC 0024's synchronous controlled API remains available for one preview
migration window through explicit `_blocking` names and
`BlockingProcessChild`. Legacy shell-string helpers remain unchanged and
blocking.

This RFC is `Proposed`. It fixes the API, ownership, cancellation, migration,
platform, and acceptance contracts. It does not claim that the current
synchronous registry is async.

## 2. Current Audit

RFC 0024 provides the protocol behavior needed by an MCP client, but its host
implementation is not safe to run on an async worker:

- Unix `next_event` loops around `poll` and `waitpid(WNOHANG)` synchronously;
- Windows starts one stdin writer and two output reader threads per child, then
  blocks `next_event` in `WaitForMultipleObjects`;
- `start` performs executable search, pipe creation, and process creation on
  the caller;
- process states live in a process-global linked list with a global numeric
  allocator and no executor owner;
- close can wait for workers or process exit;
- wrapping any of those calls in a coroutine would still block the executor;
- current `E0891` correctly quarantines the waiting compatibility operations,
  but there is no nonblocking replacement yet.

The existing bounded behavior remains valuable: shell-free argv, explicit
environment policy, one pending stdin payload, multiplexed stdout/stderr,
UTF-8 boundaries, final-output-before-exit ordering, typed timeouts, and
secret-safe errors should be preserved.

## 3. Goals and Non-goals

### 3.1 Goals

1. Start one shell-free child without blocking the async worker.
2. Incrementally exchange bounded UTF-8 stdin/stdout/stderr over native
   reactor/completion backends.
3. Preserve multiplexed output so one full pipe cannot deadlock the other.
4. Make the child `Local`/`!Send`, generation checked, and owner affine.
5. Define timeout, task cancellation, terminate, close, late completion, and
   runtime-shutdown cleanup exactly once.
6. Remove the Windows per-child helper-thread model.
7. Keep Agent application code free of C FFI.
8. Provide an explicit one-window blocking migration.

### 3.2 Non-goals

This RFC does not add PTYs, terminal emulation, inherited or null stream
selection, binary buffers, shell parsing, pipelines, process groups,
descendant-tree termination, arbitrary signals, daemon children, MCP protocol
semantics, or HTTP transports.

It also does not make a process handle `Send`, allow multiple tasks to poll one
child concurrently, or use a blocking-pool job for the lifetime of each pipe.

## 4. Public Standard-Library Contract

### 4.1 Types

The existing value types remain, with two distinct handle identities:

```nomo
pub struct ProcessChild {
    handle: u64
}

pub struct BlockingProcessChild {
    handle: u64
}

pub struct ProcessExit {
    pub code: i32
    pub signal: i32
}

pub enum ProcessEvent {
    StdinFlushed
    Stdout(string)
    Stderr(string)
    Exited(ProcessExit)
}

pub struct ProcessControlError {
    pub code: string
    pub message: string
}
```

`ProcessCommand`, `ProcessEnv`, `ProcessExit`, `ProcessEvent`, and
`ProcessControlError` retain RFC 0024's fields. `ProcessChild` is the new
owner-affine async handle. `BlockingProcessChild` belongs only to the
compatibility registry; the two types cannot be mixed.

### 4.2 Async surface

```nomo
pub suspend fn start(
    command: ProcessCommand,
    timeout_millis: u64
) -> Result<ProcessChild, ProcessControlError>

pub fn write_stdin(
    child: ProcessChild,
    data: string
) -> Result<void, ProcessControlError>

pub fn close_stdin(
    child: ProcessChild
) -> Result<void, ProcessControlError>

pub suspend fn next_event(
    child: ProcessChild,
    max_chunk_bytes: u64,
    timeout_millis: u64
) -> Result<ProcessEvent, ProcessControlError>

pub fn try_wait(
    child: ProcessChild
) -> Result<Option<ProcessExit>, ProcessControlError>

pub fn terminate(
    child: ProcessChild
) -> Result<void, ProcessControlError>

pub fn close_child(child: ProcessChild) -> void
```

`start` validates the command before creating runtime state. Its positive
timeout is at most 15 minutes and covers blocking-pool queue wait, process
creation, pipe setup, and delivery of the owner-table handle. It never invokes
a shell.

`write_stdin` keeps RFC 0024's one-payload queue. It copies one non-empty UTF-8
payload of at most 1 MiB into owner-local native storage and returns without
waiting for pipe capacity. A second queued payload returns `busy`.
`next_event` drives that payload and emits `StdinFlushed` exactly once after
all bytes are written. Timeout or task cancellation preserves the unsent
suffix; the caller must continue polling rather than queueing it again.

`next_event` retains the 4-byte-through-1-MiB chunk bound and positive timeout
through 15 minutes. It returns one `StdinFlushed`, `Stdout`, `Stderr`, or final
`Exited` event. Output is valid UTF-8, never splits a scalar, preserves order
within each stream, and alternates the first stream checked when both are
ready. `Exited` is emitted only after exit is known, both output pipes reach
EOF, and all buffered output has been returned.

`close_stdin` is idempotent after flush and returns `busy` while a payload is
pending. `try_wait` is a non-consuming, non-waiting observation.
`terminate` makes one immediate forced-termination request for the direct child
and remains safe after exit; it does not discard final output.

`close_child` is synchronous and idempotent but must not wait. It cancels the
child's reactor registrations, closes pipe directions, requests forced
termination when necessary, and transfers any pending reap or late-completion
cleanup to the owning executor. The owner slot cannot be reused until the OS
process is reaped and all late completions are drained. A program registers
`defer process.close_child(child)` immediately after `start`.

### 4.3 Blocking compatibility surface

For one preview migration window, RFC 0024's controlled implementation moves
to:

```nomo
process.start_blocking(command: ProcessCommand)
    -> Result<BlockingProcessChild, ProcessControlError>
process.write_stdin_blocking(child: BlockingProcessChild, data: string)
    -> Result<void, ProcessControlError>
process.close_stdin_blocking(child: BlockingProcessChild)
    -> Result<void, ProcessControlError>
process.next_event_blocking(
    child: BlockingProcessChild,
    max_chunk_bytes: u64,
    timeout_millis: u64
) -> Result<ProcessEvent, ProcessControlError>
process.try_wait_blocking(child: BlockingProcessChild)
    -> Result<Option<ProcessExit>, ProcessControlError>
process.terminate_blocking(child: BlockingProcessChild)
    -> Result<void, ProcessControlError>
process.close_child_blocking(child: BlockingProcessChild) -> void
```

These names preserve the accepted synchronous behavior and remain rejected by
`E0891` in a suspend call graph. `process.spawn`, `status`, `exec`, and
`output` retain their legacy blocking shell behavior and quarantine.

A synchronous call to the new `start` or `next_event` receives the normal
suspend-effect diagnostic with guidance to mark the caller `suspend` or use
the explicit `_blocking` path. There is no implicit blocking fallback.

## 5. Ownership, Bounds, and Backpressure

`ProcessChild` is `Local`/`!Send`. It may live across suspension in the owner
task's frame but cannot cross structured spawn, channel publication, frozen
sharing, or shard transfer. A copied identifier refers to the same slot;
copied stale values make close idempotent but do not create shared polling
authority.

Each current-thread executor owns a fixed process table. The first
implementation uses these hard bounds:

- at most 64 live or draining child slots;
- at most one pending `next_event` operation per child;
- at most one pending stdin payload, limited to 1 MiB;
- at most one bounded read buffer per stdout/stderr direction;
- at most 1 MiB plus a three-byte UTF-8 carry per output direction;
- at most four live reactor/completion interests per child;
- at most 16 queued/running process-start blocking jobs;
- one lazy process-start worker in the current-thread baseline.

Saturation returns `limit` or `busy`; it never creates an unbounded queue,
thread, buffer, or registry node. Ordinary Nomo collections and ARC/COW values
do not become atomic because process I/O exists.

All strings/arrays needed by a pending start job or stdin write are copied into
toolchain-owned native storage before the call can suspend or return.
Background OS workers never retain Nomo-managed values.

## 6. Cancellation, Timeout, Close, and Exit

If a start job is cancelled or times out while queued, it is removed and its
native copies are released. If process creation is already running, the frame
detaches from the job. A child created after detachment is force-terminated,
its pipes are closed, and it is reaped without publishing a handle.

A `next_event` timeout returns `ProcessControlError { code: "timeout", ... }`,
deregisters that call's interests, and preserves the child, queued stdin
suffix, buffers, and exit state. Structured task cancellation is a runtime task
outcome rather than a catchable process error; it removes interests exactly
once. The caller's synchronous defer then closes the child.

Readiness, timeout, cancellation, process exit, and close may race. One atomic
or owner-local state transition wins. Every late event carries slot and
generation identity and cannot affect a reused slot. Each pipe handle, process
handle, native buffer, blocking job, registration, and frame-owned value has
one cleanup owner.

Runtime shutdown stops accepting new start jobs, cancels live process
operations, initiates child termination, drains late completions, reaps every
child to its declared shutdown deadline, then reports remaining jobs/handles
as a runtime failure in debug/test mode. Native Unix execution must not leave a
zombie process.

## 7. Errors and Secret Safety

The async surface uses these stable `ProcessControlError.code` values:

- `invalid_request`: malformed command, limit argument, or timeout;
- `unsupported`: target or host lacks the process capability;
- `closed`: stale generation, closed child, or wrong executor owner;
- `busy`: a stdin payload or event pull is already pending;
- `limit`: child table, start queue, or completion capacity is full;
- `spawn`: executable, cwd, environment, pipe, or process creation failure;
- `io`: stdin/stdout/stderr, wait, terminate, or close failure;
- `timeout`: a start or event deadline expired;
- `protocol`: output is not supported UTF-8 text;
- `reactor`: registration or completion-backend failure.

The compatibility path may also retain RFC 0024's `runtime_unavailable` during
the preview window.

Errors, diagnostics, scheduler traces, owner-table entries, and benchmark
labels must not include program, argv, environment names/values, cwd, stdin,
stdout, stderr, JSON-RPC content, native identifiers, or copied source
arguments. Tests use distinct sentinels on each surface.

## 8. Platform Runtime Contract

### 8.1 Linux

Parent pipe descriptors are nonblocking and close-on-exec. epoll drives
stdout/stderr reads and stdin writes. Process exit uses `pidfd` when available.
The portable fallback uses one bounded, lazy runtime reaper/wakeup source that
routes generation-checked completion to the owner; it must not create one
thread per child or let multiple shards race in `waitpid`.

### 8.2 macOS and BSD

kqueue drives pipe readiness and `EVFILT_PROC` exit notification. Process
creation runs through the bounded start job so executable search, cwd policy,
and spawn do not occupy the async worker.

### 8.3 Windows

The runtime creates overlapped-capable parent pipe endpoints, associates them
with the owner IOCP, and stores `OVERLAPPED` plus payload ownership in stable
operation slots outside coroutine frames. Process exit uses a bounded system
wait callback that posts one generation-checked completion to the owner IOCP.

The RFC 0024 implementation's stdin writer and two output reader threads are
removed from the async path. `CancelIoEx` plus completion draining owns late
pipe operations; a cancelled frame never owns live `OVERLAPPED` storage.

### 8.4 Process creation and blocking pool

Process creation is a typed job in the bounded lazy blocking pool. The job
contains only validated native copies, has a generation, and posts at most one
completion to its owner. A process-specific one-thread queue may be the first
implementation only if it uses the common RFC 0032 job/cancellation/shutdown
contract and is merged into the general pool before RFC 0032 acceptance.

Toolchain/runtime code may use platform process and C APIs. Nomo Agent
application code writes no C FFI.

### 8.5 Browser WASM

Without a host process capability, `process.start` returns a ready
`unsupported` result before evaluating command or timeout operands. No
executor, blocking worker, registry, or host import is initialized. Other
async child operations cannot receive a constructible handle.

## 9. Compiler and C99 Lowering

`process.start` and `process.next_event` are suspend intrinsics. Their direct
calls must be `let`-bound in the first lowering slice, evaluate operands once,
and use the same nested stackless ABI and exactly-once frame-drop plan as
RFC 0031 and async TCP.

The ready paths for validation failure, stale/closed handles, already buffered
events, observed exit, zero registration work, and browser unsupported do not
allocate a coroutine node or enqueue the task. A real pending start/event
operation owns at most one frame plus its fixed runtime slots.

When the async surface lands, `E0891` removes only the new suspend and
specified non-waiting owner-local calls from quarantine. Legacy shell helpers
and every `_blocking` controlled call remain quarantined. Sync-unused programs
must emit no executor, reactor, blocking-pool, process-owner-table, or atomic
runtime support.

## 10. Acceptance Gates

### 10.1 Language and API

- canonical `std.process`, compiler builtins, C ABI, docs, examples, and both
  specifications agree;
- effect diagnostics cover sync-to-suspend calls and transitive blocking
  compatibility calls without leaking source arguments;
- `ProcessChild` is Local/!Send and rejected at spawn/channel/shard boundaries;
- blocking migration is explicit and source guidance names `_blocking`.

### 10.2 Native correctness

Local fixtures cover:

- argv, cwd, inherited/replaced environment, missing executable, and non-zero
  exit;
- two or more newline-framed stdin messages and `StdinFlushed`;
- interleaved stdout/stderr, pipe pressure, fairness, EOF, and final exit;
- split UTF-8, invalid UTF-8, 4-byte/1-MiB boundaries;
- timeout followed by successful reuse, task cancellation, terminate, close,
  copied stale handles, and slot reuse;
- queue/table saturation and one-core/low-memory behavior;
- start cancellation before and during spawn, including late-created-child
  termination and reap;
- exact zero-live counters after success, error, timeout, cancellation, panic,
  and shutdown.

Linux epoll, macOS kqueue, and Windows IOCP need native execution. Cross-build
is additional evidence, not a substitute. Windows tests assert that async
children create no per-child reader/writer threads.

### 10.3 Browser and secret safety

Browser tests prove unsupported is returned before operand evaluation and the
release artifact has no process host import. Native/browser diagnostics and
errors must exclude all command, environment, pipe, and JSON-RPC sentinels.

### 10.4 Examples and benchmarks

`mcp_stdio_async` composes `std.process` and `std.jsonrpc` with a local fixture,
explicit limits/deadlines, no API key, and no application C FFI.
`process_controlled_blocking` documents the migration path.

RFC 0034's process-pipe workload records bidirectional throughput, incremental
latency, cancellation, exit latency, CPU, RSS, thread count, handles/fds, and
p50/p99/p999. It compares equivalent behavior and never discards stderr or
error handling for a score.

## 11. Phased Delivery

| Slice | Required behavior | Status |
| --- | --- | --- |
| P2-PROC-A | public effect/handle/migration contract, diagnostics, lowering ABI, benchmark fixture | Implemented by [`nomo#53`](https://github.com/nomo-lang/nomo/pull/53) |
| P2-PROC-B | bounded start jobs plus epoll/kqueue pipes, exit, cancellation, close, and native Unix examples/tests | Implemented by [`nomo#54`](https://github.com/nomo-lang/nomo/pull/54) |
| P2-PROC-C | overlapped named pipes, IOCP completion, process wait, cancellation, and native Windows tests without per-child threads | Proposed |
| P2-PROC-D | browser pre-evaluation unsupported boundary and release-WASM evidence | Proposed |
| P2-PROC-E | MCP stdio example, saturation/leak stress, low-memory run, and RFC 0034 benchmark report | Proposed |

Each slice lands through a focused implementation PR and records evidence
here. The RFC remains `Proposed` until all required native correctness,
resource, compatibility, and benchmark gates pass.

### 11.1 P2-PROC-A implementation evidence

[`nomo#53`](https://github.com/nomo-lang/nomo/pull/53) separates the public
handle identities and migration paths. `ProcessChild` now belongs to the
owner-affine suspend surface, while `BlockingProcessChild` and seven explicit
`_blocking` operations preserve the RFC 0024 registry for the preview
migration window. The compiler reports secret-safe `E0870` guidance for a
synchronous call to `process.start` or `process.next_event`, keeps all shell
helpers and `_blocking` calls behind `E0891`, and rejects `ProcessChild` at
structured-spawn and bounded-channel publication boundaries.

The C99 backend lowers `process.start` and `process.next_event` through typed
start/resume/cancel registrations. A `ProcessCommand` operand is evaluated
once, retained for the call, and released exactly once; completed `Result`
ownership is transferred out of the frame or released by cancellation/drop.
The P2-PROC-A host adapter intentionally completes inline with a secret-safe
`unsupported` result. Generated-C gates prove this placeholder emits no RFC
0024 process registry, helper thread, or atomic support. Linux, macOS, and
Windows target lowering tests share this contract.

The Nomo example `async_process_pipe_contract`, explicit blocking process/MCP
migration examples, native generated-C execution, and a disabled RFC 0034
process-pipe fixture lock the public and lowering contracts. Workspace tests,
release WASM construction, and the Linux, macOS, and Windows PR CI groups
passed. At this slice the workload remained disabled and ineligible for
performance claims; P2-PROC-B implementation evidence is recorded separately
below.

This evidence completes only P2-PROC-A. It does not by itself establish native
process I/O, IOCP, browser pre-evaluation capability handling, the async MCP
example, or resource/performance evidence.

### 11.2 P2-PROC-B implementation evidence

[`nomo#54`](https://github.com/nomo-lang/nomo/pull/54) replaces the Unix ready
placeholder with a toolchain-owned native runtime. Process start and final
reap use one lazy worker with fixed tables: at most 16 live handles, 16
concurrent start jobs, and 32 total start/reap jobs. Command, argument, cwd,
and environment storage is deep-copied before publication, bounded to 4096
combined items and 1 MiB, and never appears in runtime errors or diagnostics.
The worker resolves and starts the executable without a shell. No child owns a
dedicated reader, writer, or lifetime thread.

Child stdin, stdout, and stderr are nonblocking and remain owner-affine. Linux
registers them with epoll and observes exit through `pidfd` when available;
older kernels use the same bounded worker watch table and one owner wake pipe.
macOS registers pipes and `EVFILT_PROC` with kqueue; an exit-registration race
falls back to that bounded watch source. The fallback never adds an owner-side
polling timer. Generation-tagged handle slots prevent late reap completion
from closing or releasing a reused process identity.

Native fixtures verify `StdinFlushed`, incremental stdout/stderr, and final
`Exited` ordering; timeout followed by child reuse; queued-start cancellation;
termination and nonwaiting close; invalid UTF-8 protocol closure; exact frame,
timer, reactor, process, blocking-job, retained-byte, and zero-live counters;
and ASAN-clean cancellation/drop paths where the host supports ASAN. Runtime
shutdown first detaches watches and joins the worker, then resolves remaining
children, so `waitpid` and PID reuse cannot race late completion delivery.
`examples/async_process_pipe_unix` exercises the public Nomo path with no
application C FFI.

The PR passed native Linux epoll/`pidfd`, macOS kqueue/`EVFILT_PROC`, and
Windows CI groups. Windows intentionally continues to return a typed,
secret-safe `unsupported` result, while cross-target C99 tests lock that
capability split. Clean-checkout P1 and P3 benchmark harness runs accepted all
enabled static/counter gates and continued to reject performance claims. The
cross-language process workload remains disabled until it owns a
self-contained cross-platform child fixture and a fair pinned-Go comparison.

This completes the Unix P2-PROC-B slice only. Windows IOCP process pipes,
browser pre-evaluation/release-WASM evidence, async MCP composition,
saturation/low-memory stress, and claim-eligible RFC 0034 measurements remain
P2-PROC-C through P2-PROC-E. The RFC therefore remains `Proposed`.

## 12. Alternatives and Risks

| Alternative | Why it is not selected |
| --- | --- |
| keep synchronous `next_event` in suspend code | blocks unrelated tasks and violates RFC 0032 |
| run each child for life in the blocking pool | consumes scarce blocking workers for idle I/O |
| keep three Windows threads per child | thread/RSS cost scales with child count |
| separate blocking stdout/stderr reads | can deadlock when the other pipe fills |
| make `ProcessChild` Send or globally locked | hides owner affinity and serializes unrelated children |
| return raw fd/HANDLE values | exposes unsafe platform authority to applications |
| unbounded callback/background queues | violates backpressure and low-memory gates |

The main risks are spawn cancellation after the OS has created a child,
portable Unix exit notification, Windows late completion, and cleanup during
panic/runtime shutdown. Generation checks, stable completion storage, one
cleanup owner, native fault fixtures, exact counters, and the phased platform
gates are mandatory mitigations.

## 13. Proposed Decision

Adopt the owner-affine async process surface and explicit blocking migration
defined above. Start with the current-thread executor and bounded job queue;
do not place synchronous polling or per-child worker threads behind a suspend
signature.
