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
| Implementation | Not implemented; compiler and LSP share semantic APIs, but workspace queries still use full recomputation as the baseline |
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

1. Query keys, fingerprints, dependency edges, and invalidation engine.
2. In-memory incremental parsing, name resolution, and type queries.
3. LSP overlays, cancellation, concurrent snapshots, and latency benchmarks.
4. Persistent cache, schema behavior, clean-build equivalence, and fault-injection tests.

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
