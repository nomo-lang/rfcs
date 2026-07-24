# RFC 0024: Controlled Child Processes and Multiplexed Standard I/O

> Language: [中文](../../zh-CN/rfcs/0024-controlled-child-processes-and-stdio.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0024 |
| Title | Controlled child processes and multiplexed standard I/O |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-24 |
| Implementation | Not yet accepted; `std.process` only has blocking shell-command helpers |
| Topics | process, child process, stdin, stdout, stderr, timeout, termination, MCP, C backend |
| Related RFCs | [RFC 0003](./0003-arc-cow-runtime-cost.md), [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md), [RFC 0017](./0017-target-triples-and-cross-compilation.md), [RFC 0023](./0023-pull-based-http-streaming-and-sse.md) |

---

## 1. Summary

Nomo v0.1 should add a shell-free, long-lived child-process API with explicit
arguments and environment, bounded queued stdin, multiplexed incremental
stdout/stderr events, exit observation, per-pull timeout, forced termination,
and idempotent cleanup.

The API remains synchronous and pull-based. It does not add language-level
`async`/`await`, Nomo threads, callbacks, PTYs, terminal emulation, or binary
I/O. Toolchain-owned native code may use platform polling or operating-system
worker facilities internally, while Nomo application code declares no C FFI.

## 2. Motivation

A native CLI Agent needs more than one-shot shell execution. In particular, an
MCP stdio client must start one server without invoking a shell, send several
JSON-RPC messages over stdin, consume stdout and stderr without deadlock,
observe its final status, time out stalled I/O, and terminate or clean up the
server.

The current `std.process` surface cannot form that loop:

- `process.spawn(command: string)` calls a shell and waits for completion, so
  its name does not represent a long-lived spawned child.
- `status` duplicates that behavior.
- `exec` captures only stdout and treats a non-zero status as an error.
- `output` captures stdout and stderr through unbounded temporary files.
- All commands are shell strings, so arguments, quoting, and injection behavior
  vary by platform.
- There is no child handle, stdin write, incremental output, timeout,
  termination, or stale-handle contract.

Reading stdout and stderr with two independent blocking functions is not
sufficient. A child can fill one pipe while the parent blocks on the other,
creating a deterministic deadlock. The first controlled API therefore needs
one multiplexed event operation.

## 3. Current Evidence and Gaps

| Surface | Current evidence | P1 gap |
| --- | --- | --- |
| Public API | `exit`, blocking `spawn`/`status`, `exec`, and `output` | No command model or long-lived handle |
| Invocation | `system`/`popen` consume one shell string | No shell-free program/argv boundary |
| Standard I/O | `exec` reads stdout; `output` redirects both streams to temporary files | No stdin, incremental output, fairness, or bounded pending data |
| Exit | Final integer status is returned after waiting | No non-consuming poll or exit event |
| Timeout | None | A stalled child or pipe can block forever |
| Termination | None | An Agent cannot stop or reap a server |
| Errors | `ProcessError` contains a platform-derived message | No stable code or secret-redaction contract |
| Native runtime | Generated C uses libc shell helpers | No registry, pipes, `poll`/`waitpid`, or Windows `CreateProcessW` adapter |
| Browser WASM | Existing process expressions return `NOMO-WASM-003` | Every new entry point must reject before argument evaluation |
| Tests | One native happy-path CLI test | No Windows execution, pressure, timeout, termination, UTF-8 split, or secret tests |

## 4. Detailed Design

### 4.1 Public Nomo API

The existing shell-command helpers remain source-compatible. The controlled
extension is:

```nomo
pub struct ProcessEnv {
    pub name: string
    pub value: string
}

pub struct ProcessCommand {
    pub program: string
    pub args: Array<string>
    pub cwd: Option<string>
    pub env: Array<ProcessEnv>
    pub inherit_env: bool
}

pub struct ProcessChild {
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

process.start(
    command: ProcessCommand
) -> Result<ProcessChild, ProcessControlError>

process.write_stdin(
    child: ProcessChild,
    data: string
) -> Result<void, ProcessControlError>

process.close_stdin(
    child: ProcessChild
) -> Result<void, ProcessControlError>

process.next_event(
    child: ProcessChild,
    max_chunk_bytes: u64,
    timeout_millis: u64
) -> Result<ProcessEvent, ProcessControlError>

process.try_wait(
    child: ProcessChild
) -> Result<Option<ProcessExit>, ProcessControlError>

process.terminate(
    child: ProcessChild
) -> Result<void, ProcessControlError>

process.close_child(child: ProcessChild) -> void
```

`start` never invokes a shell. `program` identifies the executable and each
`args` element is one argument. An empty `program`, embedded NUL, an invalid
environment name, duplicate environment names, or an invalid working
directory produces `invalid_request` or `spawn` without including the rejected
value in the error.

If `program` contains a path separator, it is resolved directly, relative to
the selected child cwd when it is not absolute. Otherwise the runtime searches
the `PATH` in the final child environment. An absent `PATH` makes a bare name a
`spawn` error. On Windows the search tries the exact name and then `.exe`; it
does not interpret `PATHEXT`.

`cwd = None` inherits the current working directory. When `inherit_env` is
true, entries in `env` override inherited names. When it is false, the child
receives only the explicit entries plus platform-required runtime variables.
An environment name must be non-empty and contain neither `=` nor NUL.
Names are case-sensitive on Unix-like targets and case-insensitive on Windows.
The only implicit v0.1 entry is Windows `SystemRoot` when the caller did not
provide it; Unix-like targets add none.

All three child streams are pipes. This deliberately keeps the first API small
and deterministic. Inheriting selected terminal streams, null streams, PTYs,
and binary handles require later extensions.

### 4.2 Bounded Queued Stdin

`write_stdin` copies one non-empty UTF-8 string, at most 1 MiB, into
toolchain-owned pending storage and returns after the payload has been
accepted. It does not claim that every byte has already reached the child.
Only one pending payload is permitted; another write returns `busy`.

`next_event` pumps the pending payload alongside stdout, stderr, and child-exit
observation. Once the complete payload has reached the child, it returns
`StdinFlushed` exactly once. A timeout leaves the unsent suffix in the
registry, so the caller must continue calling `next_event` rather than enqueue
the same payload again. This avoids the ambiguous partial-write behavior of a
blocking `write_stdin(..., timeout)`.

`close_stdin` is idempotent when stdin is already closed. It returns `busy` if
a payload is still pending; the caller first waits for `StdinFlushed`. Closing
stdin lets line-oriented or EOF-delimited children finish naturally.

### 4.3 Multiplexed Output and Backpressure

`next_event` waits for the next observable event across stdin progress,
stdout, stderr, and process exit. `timeout_millis` must be positive and no
greater than 15 minutes. Expiration returns `timeout` without closing the
child or discarding pending data.

`max_chunk_bytes` must be from 4 bytes through 1 MiB. `Stdout` and `Stderr`
payloads are non-empty UTF-8 strings and never split a UTF-8 scalar. Invalid
UTF-8 or embedded NUL returns `protocol`. Binary child protocols need a future
byte-buffer API.

A `protocol` failure forcibly terminates and closes the child registry entry,
because leaving an unread binary stream alive could deadlock the process. A
copied handle may still be passed safely to idempotent `close_child`.

Ordering is preserved independently within stdout and stderr. No cross-stream
ordering is promised because operating systems do not provide a common byte
clock for two pipes. When both streams are ready, the runtime alternates its
first choice so a noisy stream cannot permanently starve the other.

The runtime reads at most the requested chunk before returning to Nomo.
Operating-system pipe capacity supplies backpressure; the registry must not
accumulate an unbounded output buffer.

### 4.4 Exit, Termination, and Ownership

`try_wait` observes but does not consume child exit. It returns `None` while
the process is running and `Some(ProcessExit)` after the operating system has
reported termination.

`next_event` emits `Exited` only after the process status is known and both
stdout and stderr have reached EOF, so final output is not silently lost. A
normal exit has `signal = 0` and its platform exit code in `code`. On
Unix-like targets, signal termination sets `signal` to the signal number and
uses `128 + signal` as the normalized `code`; Windows always reports
`signal = 0`.

`terminate` requests immediate forced termination and is idempotent for a
child that has already exited. Unix-like targets use `SIGKILL`; Windows uses
`TerminateProcess`. Graceful application-level shutdown should first be sent
over stdin. Termination applies only to the direct child; process-group and
descendant-tree policy is deferred. A future API may add a separately
specified graceful signal.

`ProcessChild.handle` is an opaque registry identifier, never a native pointer.
Copied values identify the same child. `close_child` is idempotent; it closes
all pipes and, if the child is still running, forcibly terminates and reaps it.
Programs should register `defer process.close_child(child)` immediately after
`start`.

After `Exited` has been emitted, further `next_event` calls return
`invalid_request`; `try_wait`, `terminate`, and `close_child` remain safe until
the registry entry is closed.

### 4.5 Errors and Secret Handling

`ProcessControlError.code` is one of:

- `invalid_request`: malformed command, limit, timeout, or stale handle.
- `busy`: a prior stdin payload has not flushed.
- `spawn`: executable, working-directory, or environment setup failure.
- `io`: pipe creation, read, write, wait, or close failure.
- `timeout`: `next_event` made no caller-visible progress before its deadline.
- `protocol`: stdout/stderr was not valid supported text.
- `runtime_unavailable`: the target has no controlled-process adapter.

Errors and default diagnostics must not include `program`, arguments,
environment names or values, cwd, stdin payloads, received stdout/stderr, or
temporary native identifiers. This rule prevents tokens passed through
environment variables or JSON-RPC payloads from leaking into logs.

The existing `ProcessError` remains unchanged for source compatibility with
the legacy shell helpers. New code uses the stable `ProcessControlError`.

### 4.6 Toolchain-Owned Native Runtime

Applications declare no C FFI, native source, or linker metadata.

- Unix-like targets create close-on-exec pipes, use `fork` plus `execve` or an
  equivalent shell-free primitive, set nonblocking parent descriptors, and
  drive them with `poll` plus `waitpid(..., WNOHANG)`.
- Windows uses `CreateProcessW` with an explicit application name,
  deterministic argv quoting, a UTF-16 environment block, inherited child pipe
  ends, nonblocking/overlapped parent-side progress, and process-handle waits.
- Only native C buffers and operating-system handles cross any internal worker
  boundary. Nomo-managed strings and arrays are copied during `start` or
  `write_stdin` and are never retained by another thread.
- Every error, timeout, terminate, exit, and close path has a specified handle
  and buffer cleanup owner.

The browser WASM interpreter rejects `start`, `write_stdin`, `close_stdin`,
`next_event`, `try_wait`, `terminate`, and `close_child` with `NOMO-WASM-003`
before evaluating arguments.

### 4.7 Legacy Shell Helpers

`process.spawn`, `status`, `exec`, and `output` keep their accepted v0.1
behavior in this slice. Their documentation must explicitly call them legacy
blocking shell helpers and warn that untrusted text must not be concatenated
into a command.

`process.start` is the recommended API for Agent tools and MCP servers. This
RFC does not silently change `spawn(command: string)` into a handle-returning
function because that would be a source and semantic break.

## 5. Alternatives

| Option | Advantages | Disadvantages | Direction |
| --- | --- | --- | --- |
| Shell-free command plus multiplexed events | Deterministic argv, no dual-pipe deadlock, supports MCP stdio | Larger registry and platform adapter | Proposed |
| Separate blocking `read_stdout` and `read_stderr` | Superficially simple | Can deadlock when the unobserved pipe fills | Rejected |
| Blocking stdin write with timeout | Familiar API | Partial delivery makes retry corrupt message framing | Rejected; queue and emit `StdinFlushed` |
| Background Nomo task per stream | Natural concurrency | Requires a task model and thread-safe managed values | Deferred |
| Return raw OS handles | Minimal runtime work | Leaks unsafe, platform-specific ownership into applications | Rejected |
| Replace legacy `spawn` | Cleaner naming | Breaks existing code and accepted behavior | Rejected for v0.1 |

## 6. Drawbacks and Risks

- Windows overlapped pipe handling and argv quoting require substantial
  platform-specific tests.
- Text-only pipes cannot host binary protocols.
- A forced-only `terminate` is intentionally blunt.
- Cross-stream event order cannot reconstruct the exact write interleaving.
- One pending stdin payload requires the caller to wait for `StdinFlushed`
  before enqueueing another message.
- Opaque copied handles require stale-handle validation and idempotent cleanup.

## 7. Impact on v0.1 Scope

This RFC supplies the reusable process half of a native CLI Agent loop and the
transport needed by a later MCP stdio client. It does not implement an Agent,
JSON-RPC framing, MCP semantics, cron, PTYs, shell parsing, pipeline syntax,
background Nomo tasks, or async syntax.

JSON-RPC framing remains a later slice built on `ProcessEvent.Stdout`.
Structured JSON remains independently gated.

## 8. Acceptance Gate

This RFC remains `Proposed` until all gates pass:

1. Canonical `std.process` source, compiler lowering, generated C ABI, docs,
   and both v0.1 specifications expose the same API and semantics.
2. Existing blocking shell helpers remain source-compatible and their prior
   tests pass.
3. A Nomo example starts a shell-free local fixture, sends at least two framed
   stdin messages, receives interleaved stdout/stderr, observes exit, and uses
   no application-side C FFI.
4. Tests cover argv boundaries with spaces/quotes, cwd, inherited and replaced
   environment, invalid names, missing executable, and non-zero exit.
5. Pipe-pressure tests prove that multiplexed output does not deadlock and that
   each stream preserves its own order without starvation.
6. Tests cover split UTF-8 scalars, invalid UTF-8, 4-byte and 1-MiB chunk
   bounds, one pending stdin payload, `StdinFlushed`, close-stdin, and pending
   write survival across timeout.
7. Timeout leaves the child usable; terminate and close are idempotent; close
   forcibly reaps a running child; copied stale handles do not double-close.
8. Secret sentinels in argv, environment, cwd, stdin, stdout, and stderr never
   appear in errors, diagnostics, or default logs.
9. Browser WASM rejects every new process entry point before argument
   evaluation.
10. Formatting, Clippy, unit/CLI integration tests, Linux and macOS real
    cross-builds, and native Windows compile/run tests pass.
11. The implementation lands through signed commits, a child branch, PR
    review, required CI, and a green post-merge main run. Only then may this
    RFC change to `Accepted`.

## 9. Deferred Follow-Ups

- JSON-RPC line or content-length framing and an MCP stdio client.
- PTYs, terminal resize, inherited/null per-stream modes, and binary buffers.
- Graceful signal selection and process-group/tree termination policy.
- Background task integration after a task/concurrency model is accepted.
- Shell pipeline builders and shell-specific quoting helpers.

## 10. References

- `std/src/process.nomo`
- `crates/nomo_compiler/src/builtins/builtins_process.rs`
- `crates/nomo_codegen_c/src/runtime/host_env_process_helpers.rs`
- `crates/nomo/tests/cli_project.rs`
- `crates/nomo_wasm/src/interpreter.rs`
- [RFC 0003](./0003-arc-cow-runtime-cost.md)
- [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)
- [RFC 0017](./0017-target-triples-and-cross-compilation.md)
- [RFC 0023](./0023-pull-based-http-streaming-and-sse.md)
