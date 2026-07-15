# RFC 0016: Incremental Semantic Graph and Persistent Cache

> Language: [中文](../../zh-CN/rfcs/0016-incremental-semantic-graph-and-cache.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0016 |
| Title | Incremental Semantic Graph and Persistent Cache |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Partial: compiler-owned query keys, content fingerprints, dependency edges, transitive invalidation, statistics/snapshots, conservative incremental semantic checks/symbols, and LSP session caches with edit benchmarks are implemented; persistent storage and fine-grained type queries remain |
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
2. **Partial:** `IncrementalSemanticSession` caches complete project check and
   symbol results from conservative project/external-source fingerprints and
   has clean-result equivalence tests. Fine-grained parser, name-resolution,
   and type-query reuse remains.
3. **Partial:** the LSP caches diagnostics, completion, document symbols, and
   semantic tokens; open overlays participate in fingerprints, edits invalidate
   declared dependencies, and diagnostics carry document versions. The release
   gate now measures cold/warm completion and edit-to-diagnostics latency and
   requires observable hits/invalidations. Request cancellation and direct use
   of the new compiler session await the next pinned compiler revision.
4. **Pending:** persistent values, atomic disk writes, capacity eviction,
   corruption recovery, and randomized clean/incremental fault-injection tests.

## 5. Alternatives

| Option | Problem | Direction |
| --- | --- | --- |
| Cache ASTs by file only | Cross-module type dependencies still force broad recomputation | Insufficient |
| Let the LSP own a separate cache | Recreates two semantic truth systems | Reject |
| Compiler-owned query graph | CLI and editors share correctness and performance | Proposed |

## 6. Drawbacks and Risks

Incorrect invalidation can produce stale success, which is more dangerous than a build failure. Disk schemas, concurrency, and cancellation add substantial complexity.

## 7. Compatibility and Migration

The cache is neither a build input nor a portable artifact and must always be rebuildable after deletion. An incompatible schema is discarded rather than semantically migrated.

## 8. Acceptance Gate

This RFC requires incremental/clean equivalence under randomized edits, safe recovery from cross-process cache corruption, and agreed LSP/rebuild benchmarks before becoming `Accepted`.

## 9. Open Questions

- Must declaration identities survive cross-file moves?
- Should the first version persist codegen intermediates?
- Are cache capacity and privacy cleanup project or global policy?

## 10. References

- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md), [RFC 0012](./0012-shared-semantic-identities-and-verified-rename.md).
