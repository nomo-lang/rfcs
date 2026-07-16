# RFC 0016: Incremental Semantic Graph and Persistent Cache

> Language: [中文](../../zh-CN/rfcs/0016-incremental-semantic-graph-and-cache.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0016 |
| Title | Incremental Semantic Graph and Persistent Cache |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Accepted baseline: compiler-owned query keys, content fingerprints, dependency edges, transitive invalidation, statistics/snapshots, conservative semantic/LSP caches, schema-versioned persistent check and C-codegen values, atomic writes, capacity eviction, corruption recovery, and randomized clean-equivalence tests are implemented |
| Topics | incremental compilation, semantic graph, cache, LSP, invalidation |
| Related RFCs | [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md), [RFC 0012](./0012-shared-semantic-identities-and-verified-rename.md) |

---

## 1. Summary

Add a content-addressed query cache over the current workspace/package/module graphs and compiler-owned declaration identities. Every semantic result records input fingerprints and dependency edges; changes to files, manifests, targets, or toolchains invalidate only transitively affected queries.

## 2. Motivation

Shared semantic facts establish one correctness source but do not remove repeated parsing, type checking, or large-workspace LSP latency. Incremental results must remain exactly equivalent to clean builds in diagnostics, symbol identity, and artifacts.

## 3. Proposed Design

- Query keys include toolchain/schema, target, package identity, module path, source hash, and relevant configuration.
- Cache parsing, name resolution, type facts, references, and reusable codegen inputs in layers; do not cache nondeterministic external-process results.
- Query execution records dependency edges; changes propagate invalidation over reverse edges.
- An in-memory cache serves editor sessions; disk storage uses atomic writes, versioned directories, and capacity eviction.
- Mutations such as rename are revalidated against a fresh semantic snapshot; a cache hit cannot bypass type-check gates.
- `nomo clean` clears project artifacts, with separate observable cache statistics and eviction controls.

## 4. Implementation Slices

1. **Landed:** schema/toolchain/target-aware query keys, framed SHA-256 content
   fingerprints, input/query dependency edges, transitive invalidation, cache
   statistics, and immutable generation snapshots.
2. **Landed:** `IncrementalSemanticSession` caches complete project check and
   symbol results from conservative project/external-source fingerprints and
   has clean-result equivalence tests. Finer parser, name-resolution, and type
   query reuse remains a performance optimization behind the same contract.
3. **Landed:** the LSP caches diagnostics, completion, document symbols, and
   semantic tokens; open overlays participate in fingerprints, edits invalidate
   declared dependencies, and diagnostics carry document versions. The release
   gate now measures cold/warm completion and edit-to-diagnostics latency and
   requires observable hits/invalidations. Request cancellation remains an LSP
   scheduling improvement rather than a cache-correctness prerequisite.
4. **Landed:** `.nomo/cache/incremental/v1` persists successful project-check
   values and target-specific generated C across processes. Entries use
   checksum-verified envelopes, synced temporary files and atomic replacement;
   corruption becomes a self-healing miss. A 512 MiB default capacity is
   configurable through `NOMO_INCREMENTAL_CACHE_MAX_BYTES`, while `nomo cache
   stats|prune|clean` provides explicit observability, eviction, and cleanup.
   Deterministic randomized edits compare persistent and clean diagnostics;
   CLI tests cover cold/warm processes, source invalidation, corruption
   recovery, codegen reuse, and forced eviction.

## 5. Alternatives

| Option | Problem | Direction |
| --- | --- | --- |
| Cache ASTs by file only | Cross-module type dependencies still force broad recomputation | Insufficient |
| Let the LSP own a separate cache | Recreates two semantic truth systems | Reject |
| Compiler-owned query graph | CLI and editors share correctness and performance | Selected |

## 6. Drawbacks and Risks

Incorrect invalidation can produce stale success, which is more dangerous than a build failure. Disk schemas, concurrency, and cancellation add substantial complexity.

## 7. Compatibility and Migration

The cache is neither a build input nor a portable artifact and must always be rebuildable after deletion. An incompatible schema is discarded rather than semantically migrated.

## 8. Acceptance Gate

This gate is met by deterministic randomized incremental/clean equivalence tests,
cross-process CLI recovery from corrupted entries, observable cold/warm cache
tests, and the existing LSP/rebuild latency gates. Cache deletion and forced
eviction are also exercised as normal clean misses.

## 9. Open Questions

- Cross-file declaration identity stability is deferred; a move invalidates the
  conservative source fingerprint in the accepted baseline.
- The first version persists successful check results and generated C, but not
  lower-level typed IR or linked binaries.
- Capacity and privacy cleanup are project/workspace policy, with an environment
  default override and explicit `nomo cache prune|clean` commands.

## 10. References

- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md), [RFC 0012](./0012-shared-semantic-identities-and-verified-rename.md).
