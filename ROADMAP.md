# Nomo Preview Roadmap

This roadmap reports the current delivery sequence; it is not a promise of a
stable date or version. Nomo has no stable `v0.1.0`. The executable baseline is
the protected `main` branches and timestamped release sets, interpreted through
[`RELEASE-GATE.md`](RELEASE-GATE.md).

Last reviewed against `nomo`
[`085da513`](https://github.com/nomo-lang/nomo/commit/085da513ff6c042bd00571c49a6eb061722acf6f).

## Delivered implementation baseline

The current compiler/toolchain has executable coverage for:

- lexer, parser, AST, semantic/type/ownership checks, monomorphization, C99
  generation, native linking, and restricted browser WASM;
- `Option`, `Result`, postfix `?`, structs, enums, arrays, ordered maps,
  constrained generics, static interfaces, C FFI, and explicit `unsafe`;
- manifest/workspace graphs, dependency aliases, lockfiles, registry sources,
  signing/provenance, target selection, vendor/offline/frozen modes;
- project CLI commands, formatter, test runner, documentation generator, JSON
  diagnostics, shared LSP semantic APIs, examples, and release packaging;
- bounded standard-library slices for files, process, JSON/JSON-RPC, networking,
  HTTP/SSE, SQLite, cron, tasks, channels, and selected async operations.

RFCs 0001–0030 retain Accepted decisions and are recorded as implemented for
their declared preview scope. This does not make the release production-ready;
platform, installer, performance, editor, ecosystem, and external-use gates
remain in [`RELEASE-GATE.md`](RELEASE-GATE.md).

## Syntax convergence

The implementation for manifest-derived module roots and canonical implicit
void declarations has landed in `nomo`
[`085da513`](https://github.com/nomo-lang/nomo/commit/085da513ff6c042bd00571c49a6eb061722acf6f)
and `nomo-lsp`
[`f855514`](https://github.com/nomo-lang/nomo-lsp/commit/f8555148617efbc3b21fabd75f94773c3bccd959),
with synchronized grammar/editor/Playground/website surfaces.

RFCs 0021 and 0041 are `Accepted` / `Implemented` for their declared Preview
scope. Their evidence records the compiler, migration, platform, C99/WASM,
LSP, grammar/editor, Playground, website, and executable documentation gates.
The current `.main` root compatibility branch remains limited to one
development snapshot and must not become permanent syntax. Acceptance does
not imply stable `v0.1.0` or production readiness.

## Async Runtime: Proposed decisions with executable slices

RFCs 0031–0040 remain Proposed. Their implementation status is independent:

| RFC | Current executable evidence | Remaining gate |
| --- | --- | --- |
| 0031 direct-style suspend | suspend effect checking, stackless lowering, scopes, cancellation, deadlines, loop-carried state | complete decision/cleanup matrix and stabilization evidence |
| 0032 executor/reactor/pool | current-thread executor, bounded lazy pool, epoll, kqueue, IOCP foundations | per-core sharding, cross-shard transfer, broader platform matrix |
| 0033 ownership transfer | compiler-known Send/publication moves for current channel/task slices | full Send/Sync/Freeze/shared-value model |
| 0034 acceptance gates | P0/P1 controls, P2 TCP/process evidence, P3 channel/select counters | P4–P6 matrix and controlled-host performance evidence |
| 0035 monotonic timers | owner-local suspend timers and blocking-operation quarantine | compatibility-window closure and full acceptance promotion |
| 0036 channels/select | P3-A moves, P3-B bounded current-thread channels, P3-C receive/timer select | send/join select and cross-shard publication |
| 0037 async TCP | native Unix/Windows connect/read/write/DNS/half-close and browser unsupported boundary | host-driven browser TCP and full benchmark/stabilization matrix |
| 0038 async process | P2-PROC-A–E native pipes, browser boundary, MCP loop, stress/resource report | decision acceptance and broader controlled-host repetition |
| 0039 loop-carried state | first bounded owned-mutable suspending loop slice used by MCP | full borrow/guard/error/panic/browser matrix |
| 0040 async HTTP/SSE | P2-HTTP-A public suspend ABI and explicit blocking migration | native transport/streaming, Windows, browser, Agent examples, resource report |

No row changes the semantics of those RFCs. A partial implementation must
continue to reject unsupported control flow or capabilities explicitly.

## Next delivery order

1. Close the syntax-convergence acceptance PR with complete cross-repository
   evidence.
2. Continue RFC 0040 P2-HTTP-B through P2-HTTP-F as focused signed PRs.
3. Complete RFC 0036 send/join select before cross-shard publication.
4. Add RFC 0032/0033 shard and ownership-transfer slices only with bounded
   lifecycle and low-memory evidence.
5. Run the full RFC 0034 platform/performance matrix on controlled hosts.
6. Close installer, editor, packaging, external-use, and ecosystem release
   gates before any stable-version claim.

## Stability boundary

Before v1.0, Nomo must stabilize syntax, core types, standard-library APIs,
diagnostic codes and JSON shape, package/manifest/lockfile contracts, C99/WASM
semantics, Runtime ownership/cancellation, documentation, and the RFC process.

Timestamped Preview snapshots may intentionally break compatibility, but every
break requires a documented migration, synchronized ecosystem update, and a
named removal condition.
