# Nomo RFC Process and Index

> 语言 / Language: [中文](../zh-CN/README.md) | English

This is the authoritative English index for Nomo RFC decisions. The normative
language/toolchain baseline is [`SPEC-v0.1.md`](SPEC-v0.1.md); repository-wide
governance is in [`../CONTRIBUTING-RFCS.md`](../CONTRIBUTING-RFCS.md).

Nomo is in Preview and has no stable `v0.1.0`. RFC metadata is not a release
readiness claim.

## Status model

Every RFC records two independent fields:

- **Decision Status**: `Draft`, `Proposed`, `Accepted`, `Rejected`, or
  `Deferred`.
- **Implementation Status**: `Not implemented`, `Partially implemented`, or
  `Implemented`.

`Accepted` makes a decision normative only after its evidence gate. It does not
assert complete implementation. `Implemented` identifies executable evidence
for the declared scope; it does not accept a Proposed decision.

## RFC-first workflow

1. Allocate the next unused number and create matching English and Chinese
   documents from [`0000-template.md`](0000-template.md).
2. Merge the bilingual RFC as `Proposed` and `Not implemented` before creating
   downstream implementation branches.
3. Keep implementation slices and remaining gates explicit.
4. Update the bilingual SPEC, examples, formatter/doc/LSP/grammar/editor
   surfaces, and release policy when affected.
5. Promote status in a separate evidence pull request with code, tests, and
   protected CI links.

Run `python3 scripts/check_rfc_docs.py` from the repository root to validate
inventory, metadata, indexes, and local links.

## Numbering

RFC files use `NNNN-hyphenated-title.md`. Numbers are monotonically assigned and
never reused. `0000-template.md` is not an RFC.

## Directory index

| Number | Title | Decision | Implementation | Related Topics | One-line conclusion / lean |
| --- | --- | --- | --- | --- | --- |
| [0001](./rfcs/0001-error-propagation-and-conversion.md) | The experience tension between `?` propagation and the lack of automatic error conversion | Accepted | Implemented | error handling, `Result`, `?` propagation, C backend | v0.1 uses explicit `std.result.map_err(named_converter)?`; `From`-style automatic conversion is deferred. |
| [0002](./rfcs/0002-match-wildcard-and-nesting.md) | `match` lacks the `_` wildcard arm and nested destructuring | Accepted | Implemented | pattern matching, exhaustiveness, nested destructuring | `match` keeps `_` disabled; `let else`, `if let`, and Option `?` are implemented to flatten nested boilerplate. |
| [0003](./rfcs/0003-arc-cow-runtime-cost.md) | The runtime implementation cost of value semantics + ARC + COW | Accepted | Implemented | memory model, `string`, `Array<T>`, runtime | `string` uses immutable non-atomic RC; `Array<T>` uses non-atomic RC+COW with lifecycle and write-separation tests. |
| [0004](./rfcs/0004-mutable-borrow-uniqueness.md) | The real difficulty of mutable-borrow uniqueness checking | Accepted | Implemented | mutable borrow, aliasing check, escape check | Borrows live for one call expression with call-site path-conflict checks and no lifetimes or named borrows. |
| [0005](./rfcs/0005-newline-sensitivity-and-dot-resolution.md) | Significant-newline separation and `.` namespace resolution | Accepted | Implemented | lexical syntax, newline rules, name resolution, `.` resolution | Significant newlines and continuation anchors are implemented; dot chains resolve by value/module/type and checked receiver ownership. |
| [0006](./rfcs/0006-option-result-lang-items.md) | The circular dependency between `Option`/`Result` and the compiler's built-in awareness | Accepted | Implemented | lang item, `Option`, `Result`, standard library boundary | Accept compiler-owned carrier identities plus `std.option`/`std.result` module contracts; v0.1 does not use a `#[lang]` attribute. |
| [0007](./rfcs/0007-unqualified-variant-access.md) | Whether `Enum.Variant` can be simplified to an unqualified `Variant` | Accepted | Implemented | enum variants, prelude, name resolution, ergonomics | Only core `Some/None/Ok/Err` may be unqualified; local names win, user enums stay qualified, and qualified core forms remain compatible. |
| [0008](./rfcs/0008-canonical-package-identity-and-aliases.md) | Separating canonical package identity from dependency aliases | Accepted | Implemented | package identity, manifest, import | Canonical id is `owner/package`; aliases only control local imports and sources are not language identity. |
| [0009](./rfcs/0009-reproducible-workspace-and-package-graphs.md) | Reproducible Workspace, Package, and Module graphs | Accepted | Implemented | workspace, dependency graph, lockfile | Use three typed graph layers, stable dependency order, a workspace-root lockfile, checksums, and locked/offline/vendor contracts. |
| [0010](./rfcs/0010-constrained-generics-and-static-interface-dispatch.md) | Constrained generics and static interface dispatch | Accepted | Implemented | interface, generics, monomorphization | At most one interface bound per type parameter, explicit concrete type arguments, monomorphized static dispatch. |
| [0011](./rfcs/0011-c-ffi-safety-and-link-boundary.md) | The safety, ownership, and link boundary of C FFI | Accepted | Implemented | FFI, unsafe, CString, Opaque | Extern calls require call-site `unsafe`, explicit CString/Opaque, and manifest linker metadata. |
| [0012](./rfcs/0012-shared-semantic-identities-and-verified-rename.md) | Shared semantic identities and type-checked rename | Accepted | Implemented | semantic API, LSP, rename | The compiler owns semantic facts; references use declaration/receiver identity and rename edits must type-check. |
| [0013](./rfcs/0013-registry-protocol-and-package-integrity.md) | Registry protocol, authentication, and package integrity | Accepted | Implemented | registry, metadata, checksum, auth | Exact-version `/api/v1`, deterministic archives, two checksum layers, yank, bearer tokens, and verified HTTPS. |
| [0014](./rfcs/0014-semver-resolution-and-conflict-explanations.md) | Semantic version resolution and conflict explanations | Accepted | Implemented | semver, resolver, lockfile | Deterministic project/workspace single-version solving, exact locks, offline index caching, and traceable minimal conflicts are implemented. |
| [0015](./rfcs/0015-source-defined-standard-library-and-intrinsics.md) | Source-defined standard library and controlled intrinsic identities | Accepted | Implemented | standard library, intrinsic, bootstrap | Canonical Nomo sources define the public standard-library surface while a toolchain manifest constrains representation-sensitive intrinsics. |
| [0016](./rfcs/0016-incremental-semantic-graph-and-cache.md) | Incremental semantic graph and persistent cache | Accepted | Implemented | incremental compilation, LSP, cache | Compiler-owned query graphs plus atomic, checksummed, bounded disk values provide verified invalidation and cross-process check/codegen reuse. |
| [0017](./rfcs/0017-target-triples-and-cross-compilation.md) | Target triples, conditional dependencies, and cross compilation | Accepted | Implemented | target, cross compilation, linker | Canonical target predicates drive complete lockfiles, filtered graphs, conditional FFI metadata, and verified macOS/Linux cross-builds. |
| [0018](./rfcs/0018-package-signing-provenance-and-transparency.md) | Package signing, provenance, and transparency | Accepted | Implemented | signing, provenance, registry | Ed25519 publisher authorization, provenance, pinned transparency keys, dual-signed log-key rotation, signed-head gossip, freshness policy, rollback/equivocation detection, and lockfile evidence are implemented. |
| [0019](./rfcs/0019-typed-ffi-handles-callbacks-and-bindings.md) | Typed FFI handles, callbacks, and bindings | Accepted | Implemented | FFI, callback, C ABI | Nominal handles, explicit nullability/ownership, restricted callbacks, target-checked C layout, and deterministic bindings are implemented. |
| [0020](./rfcs/0020-manifest-v2-workspace-and-project-configuration.md) | Manifest v2, workspace membership, and project configuration | Accepted | Implemented | manifest, workspace, migration, trust | Explicit schema v2, verified inheritance, strict package identity, project-local operating policy, and deterministic migration. |
| [0021](./rfcs/0021-manifest-derived-module-roots.md) | Manifest-derived module roots and dependency alias mapping | Accepted | Implemented | package declaration, module identity, dependency alias, migration | Source roots derive from each package name; consumer aliases only map imports while canonical package ids retain internal identity. |
| [0022](./rfcs/0022-structured-http-client-and-host-runtime.md) | Structured HTTP client and toolchain-owned host runtime | Accepted | Implemented | HTTP, HTTPS, TLS, standard library, host runtime | A bounded structured HTTPS client is implemented with native FFI contained inside the toolchain runtime. |
| [0023](./rfcs/0023-pull-based-http-streaming-and-sse.md) | Pull-based HTTP text streaming and SSE | Accepted | Implemented | HTTP, HTTPS, streaming, SSE, cancellation, timeout | Bounded synchronous text/SSE pulls, idle timeouts, and cooperative cancellation are implemented without introducing async syntax. |
| [0024](./rfcs/0024-controlled-child-processes-and-stdio.md) | Controlled child processes and multiplexed standard I/O | Accepted | Implemented | process, stdin, stdout, stderr, timeout, termination, MCP | Add a shell-free long-lived child handle with bounded queued stdin and multiplexed output/exit events. |
| [0025](./rfcs/0025-structured-json-values-and-construction.md) | Structured JSON values, access, and construction | Accepted | Implemented | JSON, standard library, Agent, Unicode, limits, C backend, browser WASM | Keep `JsonValue` opaque while adding bounded traversal and safe construction with native/browser parity. |
| [0026](./rfcs/0026-isolated-native-tasks-and-cooperative-cancellation.md) | Isolated native tasks and cooperative cancellation | Accepted | Implemented | concurrency, tasks, isolation, cancellation, C99 backend, Agent | Run bounded top-level native tasks with copied string boundaries and compile-time task-safety checks, without shared managed values or async syntax. |
| [0027](./rfcs/0027-bundled-sqlite-persistence-and-pull-queries.md) | Bundled SQLite persistence and pull-based queries | Accepted | Implemented | SQLite, persistence, database, standard library, C99 backend, Agent | Pin and selectively compile SQLite inside the toolchain, then expose bounded parameterized execution and pull-based rows without application FFI. |
| [0028](./rfcs/0028-bounded-json-rpc-and-newline-stdio-framing.md) | Bounded JSON-RPC and newline-framed standard I/O | Accepted | Implemented | JSON-RPC, MCP, stdio, framing, process, JSON, Agent | Validate bounded JSON-RPC 2.0 envelopes and decode newline-framed stdio incrementally with opaque value state. |
| [0029](./rfcs/0029-bounded-utc-cron-schedule-calculation.md) | Bounded UTC cron schedule calculation | Accepted | Implemented | cron, scheduling, time, Agent, bounds, browser WASM | Parse bounded five-field UTC schedules and calculate deterministic matching minutes without a process-global scheduler. |
| [0030](./rfcs/0030-collection-literals-indexing-and-ordered-map.md) | Collection literals, indexing, and ordered Map | Accepted | Implemented | arrays, indexing, COW, generics, map, determinism, Agent | Add inferred array literals, checked COW-safe indexing, and one insertion-ordered generic Map without duplicating it as HashMap. |
| [0031](./rfcs/0031-direct-style-suspend-functions-and-structured-concurrency.md) | Direct-style suspend functions and structured concurrency | Proposed | Partially implemented | suspend functions, effects, stackless coroutines, cancellation, C99 | Use explicit `suspend fn` with direct-style calls, lexical task scopes, and exactly-once stackless-frame cleanup. |
| [0032](./rfcs/0032-sharded-executor-reactor-and-blocking-pool.md) | Sharded executor, reactor, and blocking pool | Proposed | Partially implemented | executor, reactor, epoll, kqueue, IOCP, WASM, affinity | Start with a current-thread reactor, scale through owner-affine shards, and isolate blocking work in a bounded lazy pool. |
| [0033](./rfcs/0033-task-ownership-transfer-and-concurrent-values.md) | Task ownership transfer and concurrent values | Proposed | Partially implemented | Send, Sync, Local, Freeze, channels, locks, collections | Keep ordinary ARC/COW task-local; cross tasks by consuming move/detach or explicit frozen/shared/concurrent storage. |
| [0034](./rfcs/0034-async-runtime-acceptance-and-benchmark-gates.md) | Async runtime acceptance and benchmark gates | Proposed | Partially implemented | performance, memory, Go comparison, low-end devices, cross-platform | Require measurable unused/ready-path cost, correctness/leak gates, a platform matrix, and fair reproducible Agent benchmarks. |
| [0035](./rfcs/0035-monotonic-suspend-timers-and-blocking-sleep-migration.md) | Monotonic suspend timers and blocking sleep migration | Proposed | Implemented | suspend functions, timers, monotonic clock, blocking compatibility, C99 | Add one bounded `task.sleep(Duration)` timer and reject blocking `time.sleep*` on async workers without breaking legacy synchronous code. |
| [0036](./rfcs/0036-bounded-channels-publication-moves-and-static-select.md) | Bounded channels, publication moves, and static select | Proposed | Partially implemented | channel, select, move publication, Send, backpressure, cancellation, C99 | Fix the typed channel API, consuming publication boundary, deterministic static select syntax, and phased ownership/correctness gates before implementation. |
| [0037](./rfcs/0037-owner-affine-async-tcp-client-and-blocking-migration.md) | Owner-affine async TCP client and blocking migration | Proposed | Partially implemented | async TCP, reactor, owner affinity, bounded I/O, DNS | Define bounded suspend connect/read/write, generation-checked stream ownership, explicit blocking migration, and native platform gates. |
| [0038](./rfcs/0038-owner-affine-async-process-pipes-and-blocking-migration.md) | Owner-affine async process pipes and blocking migration | Proposed | Implemented | process, async pipe, reactor, MCP, owner affinity | Define bounded suspend process start/event progress, owner-local pipes, explicit blocking migration, and native platform gates. |
| [0039](./rfcs/0039-loop-carried-coroutine-state-and-suspension-safe-mutation.md) | Loop-carried coroutine state and suspension-safe mutation | Proposed | Partially implemented | suspend functions, loops, mutable locals, liveness, ARC, C99, MCP | Carry task-local owned mutable state through bounded suspending loops without allowing borrows or guards across suspension or adding atomic cost. |
| [0040](./rfcs/0040-owner-affine-async-http-and-sse-migration.md) | Owner-affine async HTTP/HTTPS, SSE, and blocking migration | Proposed | Partially implemented | HTTP, HTTPS, TLS, SSE, reactor, owner affinity, connection reuse | Migrate the bounded client and stream APIs to suspend operations with owner-local transport progress, explicit blocking compatibility, and native platform gates. |
| [0041](./rfcs/0041-canonical-implicit-void-return-declarations.md) | Canonical implicit `void` return declarations | Accepted | Implemented | function declarations, methods, suspend, interfaces, extern, formatter, LSP | Omit `-> void` canonically on declarations while preserving explicit parser compatibility and complete callable/type/value uses. |

> Note: `0000-template.md` is the template and is not counted in the table above.
