# RFC 0027: Bundled SQLite Persistence and Pull-Based Queries

> Language: [中文](../../zh-CN/rfcs/0027-bundled-sqlite-persistence-and-pull-queries.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0027 |
| Title | Bundled SQLite persistence and pull-based queries |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-25 |
| Topics | SQLite, persistence, database, standard library, C99 backend, Agent |
| Related RFCs | [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md), [RFC 0017](./0017-target-triples-and-cross-compilation.md), [RFC 0019](./0019-typed-ffi-handles-callbacks-and-bindings.md), [RFC 0024](./0024-controlled-child-processes-and-stdio.md), [RFC 0025](./0025-structured-json-values-and-construction.md), [RFC 0026](./0026-isolated-native-tasks-and-cooperative-cancellation.md) |

---

## 1. Summary

Nomo v0.1 should provide a bounded `std.sqlite` API for durable Agent state
without requiring application-side C FFI, platform package installation, or a
separate database service.

The toolchain pins the official SQLite 3.53.3 amalgamation and verifies the
published SHA3-256 digest before it enters the repository. The CLI carries the
amalgamation as toolchain data and materializes `sqlite3.c` and `sqlite3.h`
only when a program actually uses `std.sqlite`. The selected target C compiler
builds SQLite as a separate translation unit beside generated Nomo C. Programs
that do not use `std.sqlite` pay no SQLite compile or link cost.

The public API is intentionally pull-based. `execute` handles one bounded,
parameterized statement that produces no rows. `query` creates one opaque
prepared-query handle, and `next` copies at most one bounded row into Nomo
values. Database and query handles are runtime-owned, explicitly closed, and
unforgeable. SQL and bound values are never reproduced in diagnostics or
default logs.

This RFC distinguishes two requirements:

- Nomo Agent application code declares no C FFI, native source, linker flag,
  or system SQLite dependency.
- The toolchain may compile the upstream SQLite C amalgamation internally.

It does not claim that the toolchain itself is implemented only in Nomo.

## 2. Goals and Non-goals

### 2.1 Goals

1. Persist structured Agent state across native CLI processes on Linux, macOS,
   and Windows.
2. Keep the application API parameterized, bounded, pull-based, and explicit
   about handle lifetime.
3. Ship one reproducible SQLite implementation instead of accepting host
   library version and compile-option drift.
4. Preserve the existing C99 backend and target-conditioned cross-build model.
5. Prevent SQL text, paths, prompts, tokens, BLOBs, and bound values from
   leaking through default diagnostics.
6. Provide enough functionality for schema creation, transactions, inserts,
   updates, deletes, and incremental row reads.
7. Keep browser WASM behavior deterministic through explicit capability
   denial.

### 2.2 Non-goals

This RFC does not add:

- an ORM, migrations framework, query builder, schema language, or generated
  record mapping;
- a network database client, connection pool, replication, backup service, or
  distributed transaction protocol;
- automatic vector embeddings, vector search, FTS policy, or Agent memory
  ranking;
- application-defined SQLite functions, collations, virtual tables, loadable
  extensions, or raw `sqlite3_*` pointer access;
- arbitrary multi-statement execution;
- implicit transactions or automatic retry of writes;
- browser persistence through OPFS, IndexedDB, or SQLite WASM;
- task-safe database handles or concurrent use of one handle from
  `std.task`;
- an application storage quota. Deployment or operating-system quota remains
  responsible for total disk consumption.

## 3. Current Gap Audit

| Area | Current implementation | Gap |
| --- | --- | --- |
| Filesystem | Bounded file helpers and opaque `File` handles | Applications would have to invent locking, recovery, indexing, and transactions |
| JSON | Structured, bounded JSON construction and traversal | JSON alone does not provide durable indexing or atomic updates |
| Process | Long-lived shell-free child processes and framed I/O primitives | Driving a `sqlite3` executable is deployment-dependent and loses typed binding semantics |
| FFI | Explicit typed C boundary with manifest linker metadata | Every Agent would otherwise own unsafe SQLite declarations, allocation, and platform linkage |
| Build | Target-aware C99 emission plus application FFI sources | No toolchain-owned optional native source is selected by standard-library usage |
| Tasks | Isolated native workers with copied string boundaries | Database handles are thread-confined and not safe to transfer to workers |
| Browser WASM | Capability-denying interpreter with no host imports | No persistent native SQLite VFS is available |

Dynamic loading of a host `sqlite3` library is not sufficient for the first
portable contract. Library presence, version, compile options, extension
policy, and ABI availability vary across Windows and minimal Linux
installations. A shell command is also not a native standard-library contract.

## 4. Detailed Design

### 4.1 Canonical `std.sqlite` API

```rust
pub struct SqliteDatabase {
    handle: u64
}

pub struct SqliteQuery {
    handle: u64
}

pub struct SqliteError {
    pub code: string
    pub message: string
    pub native_code: i64
}

pub enum SqliteOpenMode {
    ReadOnly
    ReadWrite
    ReadWriteCreate
}

pub enum SqliteValue {
    Null
    Integer(i64)
    Real(f64)
    Text(string)
    Blob(Array<u32>)
}

pub struct SqliteColumn {
    pub name: string
    pub value: SqliteValue
}

pub struct SqliteRow {
    pub columns: Array<SqliteColumn>
}

pub struct SqliteExecuteResult {
    pub changes: u64
    pub last_insert_rowid: i64
}

pub fn open(
    path: string,
    mode: SqliteOpenMode,
    busy_timeout_millis: u64
) -> Result<SqliteDatabase, SqliteError>

pub fn open_memory(
    busy_timeout_millis: u64
) -> Result<SqliteDatabase, SqliteError>

pub fn execute(
    database: SqliteDatabase,
    sql: string,
    params: Array<SqliteValue>
) -> Result<SqliteExecuteResult, SqliteError>

pub fn query(
    database: SqliteDatabase,
    sql: string,
    params: Array<SqliteValue>
) -> Result<SqliteQuery, SqliteError>

pub fn next(
    query_value: SqliteQuery,
    max_row_bytes: u64
) -> Result<Option<SqliteRow>, SqliteError>

pub fn reset(
    query_value: SqliteQuery,
    params: Array<SqliteValue>
) -> Result<void, SqliteError>

pub fn close_query(
    query_value: SqliteQuery
) -> Result<void, SqliteError>

pub fn close(
    database: SqliteDatabase
) -> Result<void, SqliteError>
```

`SqliteDatabase` and `SqliteQuery` are opaque. Their fields are not public,
cannot be read or written, and cannot be constructed directly. Copying the
Nomo value only copies an integer capability; the runtime registry determines
whether that capability is still live.

`SqliteColumn` preserves result order and permits duplicate column names.
Applications that need name lookup can implement their own first/last/error
policy instead of receiving an ambiguous built-in mapping.

### 4.2 Open Semantics

`open` rejects an empty path, an embedded NUL, and the special `:memory:` name.
In-memory databases must use `open_memory` so persistent and ephemeral storage
cannot be confused accidentally.

The modes map to these `sqlite3_open_v2` policies:

- `ReadOnly`: `SQLITE_OPEN_READONLY`;
- `ReadWrite`: `SQLITE_OPEN_READWRITE` and fail if the file is absent;
- `ReadWriteCreate`: `SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE`.

Every connection also uses `SQLITE_OPEN_FULLMUTEX`,
`SQLITE_OPEN_PRIVATECACHE`, and extended result codes. URI filename handling
is not enabled, so query-string flags cannot silently change VFS, cache,
locking, immutable-file, or open-mode behavior.

Relative paths are resolved by SQLite from the process working directory.
Windows paths are passed as UTF-8 according to the upstream API. The first
slice follows normal host symbolic-link behavior; a later capability-based
filesystem design may add rooted or no-follow opens.

`busy_timeout_millis` must be in `0..=300_000`. Zero means SQLite reports
contention immediately. A nonzero value bounds lock waiting performed by
SQLite; it is not an execution deadline for arbitrary SQL.

After a successful open, the runtime enables extended result codes,
`foreign_keys`, and defensive/trusted-schema settings where the pinned SQLite
API supports them. Initialization failure closes the partial handle before
returning an error.

### 4.3 One Statement and Positional Binding

`execute` and `query` accept exactly one SQL statement. Empty SQL and a second
non-comment statement in the prepare tail are rejected. SQL text may contain
whitespace and comments but not an embedded NUL.

Parameters are positional and one-based at the SQLite boundary. The Nomo
array binds indices `1..=len`; its length must equal
`sqlite3_bind_parameter_count`. Ordinary `?`, numbered `?NNN`, and named
SQLite placeholders may be used, but sparse placeholder numbers still count
toward the exact array length and the 1024-parameter limit.

Text and BLOB parameters use `SQLITE_TRANSIENT`, so SQLite receives its own
copy before the Nomo call returns. An `Array<u32>` BLOB element must be in
`0..=255`; larger values produce `invalid_request`.

Applications should bind data rather than interpolate it into SQL. The API
does not provide an unsafe raw-binding escape hatch.

### 4.4 Execute

`execute` prepares, binds, and steps one statement internally. It succeeds
only when the first step is `SQLITE_DONE`. A statement that produces a row
returns `unexpected_row`; callers must use `query`.

On success it returns the per-connection `changes` count and
`last_insert_rowid` observed immediately after the statement. The internal
statement is finalized on every success and error path.

Transactions are explicit SQL:

```rust
sqlite.execute(db, "BEGIN IMMEDIATE", Array.new<SqliteValue>())?
sqlite.execute(db, "INSERT INTO memory(value) VALUES (?)", values)?
sqlite.execute(db, "COMMIT", Array.new<SqliteValue>())?
```

The runtime does not silently begin, commit, roll back, or retry a
transaction. Applications must issue `ROLLBACK` after a recoverable
transaction error when appropriate.

### 4.5 Pull-Based Queries

`query` prepares and binds one statement and stores the native prepared
statement in a runtime-owned query registry. It does not execute enough work
to produce a row.

`next` performs one `sqlite3_step`:

- `SQLITE_ROW` copies one row into `SqliteRow`;
- `SQLITE_DONE` returns `None`;
- contention, constraint, corruption, I/O, and other failures
  return a classified `SqliteError`.

Repeated `next` after `SQLITE_DONE` returns `None`. A row is constructed only
after all column names and values pass their bounds and encoding checks, so no
partial row escapes on failure.

`reset` calls `sqlite3_reset`, clears prior bindings, validates the new
parameter array, and binds it. It permits prepared-query reuse without
exposing a raw statement pointer. A reset after a step error returns the
classified reset/bind result rather than hiding the prior error.

### 4.6 Value Mapping and Copies

SQLite storage classes map as follows:

| SQLite storage class | Nomo value |
| --- | --- |
| `NULL` | `SqliteValue.Null` |
| 64-bit signed integer | `SqliteValue.Integer(i64)` |
| IEEE 754 double | `SqliteValue.Real(f64)` |
| UTF-8 text | `SqliteValue.Text(string)` |
| bytes | `SqliteValue.Blob(Array<u32>)` |

Text and BLOB results are copied into new Nomo-managed values on the caller
thread. SQLite pointers are never stored in a Nomo string or array. Invalid
UTF-8 in a SQLite `TEXT` value returns `encoding`; applications that need
arbitrary bytes must store and read a BLOB.

SQLite integer and real conversions use their native 64-bit APIs. No
string-based number conversion or locale-sensitive formatting occurs.

### 4.7 Exact Limits

The first implementation fixes these limits:

- 32 live, unclosed database handles per process;
- 256 live, unclosed query handles per process;
- 4096 UTF-8 bytes per persistent database path;
- 1 MiB per SQL statement;
- 1024 parameters per statement;
- 8 MiB per text or BLOB parameter;
- 16 MiB total encoded parameter bytes per statement;
- 256 result columns;
- 8 MiB per text or BLOB result value;
- caller-selected `max_row_bytes` in `1..=16 MiB`;
- `busy_timeout_millis` in `0..=300_000`.

The generated SQLite build lowers compatible engine limits to the same or
stricter values. Connection-local `sqlite3_limit` calls repeat the critical
length, SQL, column, expression-depth, variable-number, function-argument,
compound-select, and LIKE-pattern limits so future toolchain changes cannot
silently widen an existing public contract.

An oversized row makes that query terminal with `limit`; the query can still
be closed. Bounds are measured before constructing Nomo-managed output.

Total database file size is not a standard-library memory bound. Operating
systems, containers, deployment policy, and later storage-capability work may
enforce disk quotas. SQLite still reports `full` when the underlying
filesystem or configured database page limit refuses growth.

### 4.8 Lifecycle

`close_query` finalizes the prepared statement, removes the registry entry,
and invalidates the handle. Closing an already closed or stale query returns
`closed`.

`close(database)` succeeds only when no live query belongs to that database.
Otherwise it returns `busy_handle` and leaves the connection open. A
successful close removes the registry entry and invalidates all copied Nomo
capabilities for that handle.

Normal process return with live SQLite handles emits one generic lifecycle
diagnostic and performs best-effort finalization and close. The message
contains counts only, never paths, SQL, schema names, or values.

The browser interpreter never allocates these registries.

### 4.9 Error Contract

`SqliteError.code` is one of:

- `invalid_request`: invalid mode, timeout, path, SQL shape, parameter, or
  row limit;
- `limit`: a Nomo or configured SQLite resource limit was exceeded;
- `open`: the requested database could not be opened;
- `prepare`: the statement could not be compiled;
- `bind`: a parameter could not be bound;
- `step`: statement execution failed without a more specific classification;
- `busy`: the database is locked or busy;
- `constraint`: a constraint rejected the operation;
- `read_only`: a write was attempted through a read-only connection or file;
- `corrupt`: SQLite reported corrupt or invalid database content;
- `full`: storage growth was refused;
- `encoding`: a result marked as text was not valid UTF-8;
- `unexpected_row`: `execute` was used for a row-producing statement;
- `busy_handle`: a database still owns live queries;
- `closed`: a stale or closed database/query handle was used;
- `runtime_unavailable`: the current runtime cannot provide native SQLite;
- `internal`: a registry, allocation, or engine invariant failed.

`native_code` carries the SQLite extended numeric result code when one exists,
or zero for Nomo-side validation failures. Applications must branch on the
stable string code unless they intentionally depend on the pinned engine.

Messages are stable, bounded, and generic. They do not call
`sqlite3_expanded_sql`, enable tracing, or reproduce SQL, parameters, paths,
prompts, tokens, BLOBs, row content, or SQLite error strings that may contain
application identifiers.

### 4.10 Bundled SQLite Source and Reproducibility

The first accepted implementation pins:

- upstream version: SQLite 3.53.3;
- archive: `sqlite-amalgamation-3530300.zip`;
- upstream SHA3-256:
  `d45c688a8cb23f68611a894a756a12d7eb6ab6e9e2468ca70adbeab3808b5ab9`.

The repository records the upstream URL, version, digest, retrieval date,
public-domain notice, and the exact extracted-file digests. No generated
autoconf or shell build product is shipped.

Updating SQLite is a reviewed dependency update with:

1. verified upstream digests;
2. an isolated signed commit;
3. upstream release/security note review;
4. native, sanitizer, cross-build, and persistence-regression evidence;
5. updated provenance metadata.

There is no automatic fallback to a host `libsqlite3`. One pinned engine keeps
behavior and compile options reproducible across hosts.

### 4.11 C99 Backend and CLI Build

When typed IR contains a SQLite operation, generated C includes a stable
feature marker and the toolchain-owned wrapper. The CLI then:

1. writes the embedded pinned `sqlite3.c` and `sqlite3.h` into the
   target-scoped build directory;
2. verifies their embedded toolchain digest before invoking the compiler;
3. compiles SQLite as a separate translation unit with the selected target C
   toolchain;
4. links it beside generated Nomo C;
5. includes the SQLite version, source digest, and compile-option set in the
   persistent codegen/build cache key.

The SQLite translation unit uses reviewed options including serialized
threading, disabled double-quoted string literals, untrusted schema by
default, foreign keys by default, API armor, and reduced resource limits.
Loadable extensions and shared-cache mode are never enabled by the Nomo
wrapper.

`nomo build --emit-c` materializes `main.c`, `sqlite3.c`, `sqlite3.h`, and
provenance metadata when SQLite is used. Emitting only `main.c` would not be a
rebuildable C artifact.

Programs that do not use `std.sqlite` do not materialize, compile, or link
SQLite.

### 4.12 Concurrency and `std.task`

The pinned engine is built in serialized mode for defensive safety, but Nomo
SQLite handles remain runtime-owned and thread-confined. `std.sqlite` is in
the forbidden task-safe set for RFC 0026. A handle cannot cross the task
string boundary, and a worker cannot open its own database in the first
slice.

Future work may allow one independent connection per isolated task after
registry ownership, process-exit cleanup, busy policy, and deterministic test
fixtures have a separate acceptance gate. This RFC does not imply that change.

### 4.13 Browser WASM

The browser interpreter type-checks the same API, but `open` and
`open_memory` return `runtime_unavailable`. No SQLite WASM, OPFS, IndexedDB,
host import, network fetch, or memory-limit increase is added.

Operations on invalid browser handles return `closed`. Arguments are
validated without reading files or invoking any host capability.

## 5. Compatibility and Migration

This proposal is additive. Existing filesystem, JSON, process, FFI, task, and
manifest behavior does not change.

The SQLite amalgamation is a toolchain implementation dependency, not a Nomo
package dependency and not application `[ffi]` metadata. Lockfiles therefore
do not gain a fake `sqlite3` package entry. Reproducibility evidence belongs to
the compiler/toolchain version and emitted C provenance.

The API intentionally uses opaque handles rather than public native layouts,
so a future storage backend or SQLite update does not change Nomo value ABI.

## 6. Alternatives

| Alternative | Benefit | Cost / reason rejected |
| --- | --- | --- |
| Application C FFI to SQLite | Minimal toolchain work | Repeats unsafe declarations, ownership, compile flags, and platform linkage in every Agent |
| Dynamically load host `libsqlite3` | Small release artifact | Host presence, version, features, and security options are not reproducible, especially on Windows/minimal Linux |
| Run the `sqlite3` CLI through `std.process` | Uses existing process API | Executable is optional, framing is fragile, and safe typed binding is lost |
| Pure Nomo append-only JSON store | No native dependency | Reimplements locking, crash recovery, indexes, transactions, and compaction poorly |
| Rust database inside `nomo` CLI | Mature Rust crates | Compiled Nomo executables would require a sidecar RPC runtime or lose standalone behavior |
| Bundle SQLite into every generated C file | Simple single-file output | Adds megabytes and large compile cost even when unused, and makes codegen snapshots impractical |
| Toolchain-owned optional amalgamation | Reproducible, standalone, cross-target, no application FFI | Increases toolchain size and SQLite-using build time; accepted for the native persistence slice |

## 7. Drawbacks and Risks

- The compiler/toolchain release grows by the compressed and embedded
  amalgamation.
- The first build of a SQLite-using target compiles a large C translation
  unit.
- Vendoring requires an explicit upstream update and security-review process.
- Pull-based rows are lower level than an ORM and require application mapping.
- A copied BLOB representation as `Array<u32>` is not a compact Nomo byte
  type; a future byte-buffer RFC may improve it.
- Total on-disk growth is not bounded by this API.
- SQLite handles are deliberately unavailable inside isolated tasks.
- Generic error messages protect secrets but provide less raw engine detail.

## 8. Impact on the Native CLI Agent Goal

Together with RFCs 0022 through 0026, this slice allows a Nomo CLI Agent to:

1. create its schema and durable state database without application FFI;
2. store conversations, tool metadata, checkpoints, and JSON documents using
   bound parameters;
3. update multiple records atomically through explicit SQL transactions;
4. pull bounded rows without loading an entire result set;
5. restart and recover the persisted state in another process;
6. keep prompts, tokens, and row content out of default diagnostics.

It does not add semantic memory ranking, vector search, or a complete Agent
product.

## 9. Acceptance Gate

This RFC remains `Proposed` until all gates pass:

1. Both v0.1 specifications, standard-library docs, and this RFC define the
   exact API, limits, lifecycle, error, task-safety, and browser contracts.
2. Canonical `std.sqlite` source and the standard-module registry expose every
   type and function above with LSP/doc navigation.
3. Compiler lowering and typed IR validate exact database/query/value types,
   reject forged or field-accessed opaque handles, and select SQLite runtime
   support only when used.
4. The official SQLite 3.53.3 amalgamation, public-domain notice, upstream
   SHA3-256, extracted-file digests, and provenance metadata are committed and
   independently verified.
5. Build, run, test, and `--emit-c` paths materialize and compile the same
   target-scoped SQLite sources; cache keys include version, digests, and
   compile options.
6. Compiler/codegen tests prove mode, timeout, SQL, parameter, value, and
   return-type validation for every operation.
7. Native integration tests cover persistent reopen, in-memory isolation,
   schema creation, all five value classes, parameter binding, execute
   metadata, row order, duplicate names, repeated `None`, reset/rebind, and
   explicit transactions.
8. Tests cover exact handle, path, SQL, parameter, value, column, row, and
   timeout limits, including cleanup after every limit failure.
9. Lifecycle tests cover busy database close, query close, stale and copied
   handles, process-exit cleanup, prepare/bind/step errors, and every
   finalization path.
10. Failure fixtures cover contention timeout, read-only writes, constraints,
    corrupt database input, full storage, invalid UTF-8 text, and a
    row-producing statement passed to `execute`.
11. Secret sentinels in paths, SQL, parameters, BLOBs, rows, and schema values
    never appear in compiler diagnostics, runtime errors, lifecycle warnings,
    or default logs.
12. AddressSanitizer/LeakSanitizer and repeated open/query/reset/close stress
    find no wrapper or cross-boundary lifetime errors. Upstream SQLite is not
    modified by Nomo patches.
13. The conformance suite runs on Linux, macOS, and Windows. Real macOS
    arm64-to-x86_64 and Linux x86_64-to-arm64 builds compile and link the
    pinned amalgamation for the target.
14. Browser WASM returns `runtime_unavailable`, adds no imports, and preserves
    the existing memory gate.
15. A Nomo example implements a small durable Agent-memory/checkpoint store,
    uses parameter binding and an explicit transaction, restarts in a second
    process, and declares no application FFI.
16. Formatting, Clippy, unit/CLI integration, release, WASM, cross-build, and
    platform smoke checks pass on the signed implementation PR and post-merge
    `main`.
17. Implementation lands from a signed child branch through a reviewed PR.
    Acceptance evidence and links are recorded here before the status changes
    to `Accepted`.

## 10. Deferred Follow-up

- A compact `bytes` type and zero-copy bounded BLOB reads.
- Typed row decoding and schema-derived mappings.
- Schema migration helpers and a migration journal policy.
- Online backup, integrity-check, and recovery APIs.
- FTS5 and an Agent-memory retrieval policy.
- Vector-search extension evaluation.
- Per-task independent connections and a bounded connection pool.
- Storage quotas and capability-rooted paths.
- Browser persistence through a separately gated SQLite WASM/VFS design.

## 11. References

- `std/src/sqlite.nomo` (proposed)
- `crates/nomo_compiler/src/builtins/builtins_sqlite.rs` (proposed)
- `crates/nomo_codegen_c/src/runtime/host_sqlite.c` (proposed)
- `crates/nomo/src/project/build.rs`
- [SQLite 3.53.3 download and amalgamation digest](https://www.sqlite.org/download.html)
- [SQLite amalgamation](https://www.sqlite.org/amalgamation.html)
- [SQLite public-domain statement](https://www.sqlite.org/copyright.html)
- [SQLite threading modes](https://www.sqlite.org/threadsafe.html)
- [SQLite implementation limits](https://www.sqlite.org/limits.html)
- [SQLite compile-time options](https://www.sqlite.org/compile.html)
- [`sqlite3_open_v2`](https://www.sqlite.org/c3ref/open.html)
- [`sqlite3_prepare_v3`](https://www.sqlite.org/c3ref/prepare.html)
- [SQLite parameter binding](https://www.sqlite.org/c3ref/bind_blob.html)
