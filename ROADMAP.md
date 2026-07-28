# Nomo Preview Roadmap

This roadmap reports the current delivery sequence; it is not a promise of a
stable date or version. Nomo has no stable `v0.1.0`. The executable baseline is
the protected `main` branches and timestamped release sets, interpreted through
[`RELEASE-GATE.md`](RELEASE-GATE.md).

Last reviewed against `nomo`
[`c6712c1`](https://github.com/nomo-lang/nomo/commit/c6712c1da1f65fcbdf0ce037224d11482b6a7e35).

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

## Proposed Windows ARM64 platform contract

RFC 0042 is `Proposed` / `Not implemented`. It defines Windows 11 ARM64 as a
candidate Preview target using `aarch64-pc-windows-msvc`, the LLVM Clang
GNU-style driver, the MSVC ABI, and ARM64 Visual Studio/Windows SDK inputs.

No Windows ARM64 platform or release gate is recorded as delivered. Acceptance
requires native ARM64 compiler, generated-application, Runtime, LSP, installer,
ZIP/checksum, and attestation evidence. Windows x64-to-ARM64 cross-build is a
separate compile/link gate and cannot replace native runtime tests. Existing
Windows-wide path, Regex, and large-file limitations remain explicit.

## Proposed C99 optimization and performance contract

RFC 0043 is `Proposed` / `Not implemented`. It defines the public
`nomo build/run/test --release` and `nomoc build --release` contract, fixed
portable C optimization flags, and a typed IR/HIR to CFG MIR path for
proof-based optimization without weakening bounds, overflow, division, COW,
evaluation-order, ownership, or cleanup semantics.

Its performance target is deliberately narrow: the three frozen scalar
Benchmarks Game workloads must satisfy separate C, equivalent C++20, and
candidate/main log-ratio gates in two qualified canonical-host batches. Shared
CI validates correctness and the measurement machinery but does not gate PRs on
runner wall time. The existing exploratory baseline is not implementation or
parity evidence, and no general C/C++ performance or release-readiness claim is
recorded as delivered.

## Async Runtime: Proposed decisions with executable slices

RFCs 0031–0040 remain Proposed. Their implementation status is independent:

| RFC | Current executable evidence | Remaining gate |
| --- | --- | --- |
| 0031 direct-style suspend | suspend effect checking, stackless lowering, scopes, cancellation, deadlines, loop-carried state | complete decision/cleanup matrix and stabilization evidence |
| 0032 executor/reactor/pool | current-thread executor, bounded lazy pool, epoll, kqueue, IOCP foundations | per-core sharding, cross-shard transfer, broader platform matrix |
| 0033 ownership transfer | compiler-known Send/publication moves for current channel/task slices | full Send/Sync/Freeze/shared-value model |
| 0034 acceptance gates | P0/P1 controls, P2 TCP/process evidence, P3 channel/select counters | P4–P6 matrix and controlled-host performance evidence |
| 0035 monotonic timers | owner-local suspend timers and blocking-operation quarantine | compatibility-window closure and full acceptance promotion |
| 0036 channels/select | P3-A moves, P3-B bounded current-thread channels, P3-C receive/timer select, P3-D send/join select | P4 cross-shard publication |
| 0037 async TCP | native Unix/Windows connect/read/write/DNS/half-close and browser unsupported boundary | host-driven browser TCP and full benchmark/stabilization matrix |
| 0038 async process | P2-PROC-A–E native pipes, browser boundary, MCP loop, stress/resource report | decision acceptance and broader controlled-host repetition |
| 0039 loop-carried state | first bounded owned-mutable suspending loop slice used by MCP | full borrow/guard/error/panic/browser matrix |
| 0040 async HTTP/SSE | P2-HTTP-A public suspend ABI and explicit blocking migration | native transport/streaming, Windows, browser, Agent examples, resource report |

No row changes the semantics of those RFCs. A partial implementation must
continue to reject unsupported control flow or capabilities explicitly.

## Next delivery order

1. Implement RFC 0043's public release profile and semantics-preserving
   HIR/MIR optimizer as independently reviewed slices.
2. After the release path exists, implement the independent benchmark v2
   harness and collect canonical evidence without shared-runner timing gates.
3. Continue RFC 0040 P2-HTTP-B through P2-HTTP-F as focused signed PRs.
4. Implement RFC 0036 P4 cross-shard publication together with the required
   RFC 0032/0033 private-atomic-shim, owner-wakeup, and ownership-transfer
   slices.
5. Add further RFC 0032/0033 shard and ownership-transfer slices only with
   bounded lifecycle and low-memory evidence.
6. Run the full RFC 0034 platform/performance matrix on controlled hosts.
7. Close installer, editor, packaging, external-use, and ecosystem release
   gates before any stable-version claim.

## Stability boundary

Before v1.0, Nomo must stabilize syntax, core types, standard-library APIs,
diagnostic codes and JSON shape, package/manifest/lockfile contracts, C99/WASM
semantics, Runtime ownership/cancellation, documentation, and the RFC process.

Timestamped Preview snapshots may intentionally break compatibility, but every
break requires a documented migration, synchronized ecosystem update, and a
named removal condition.
