# RFC 0009: Reproducible Workspace, Package, and Module Graphs

> 语言 / Language: [中文](../../zh-CN/rfcs/0009-reproducible-workspace-and-package-graphs.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0009 |
| Title | Reproducible workspace, package, and module graphs |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Landed: `WorkspaceGraph -> PackageGraph -> ModuleGraph`, stable topological order, workspace lockfiles, checksums, locked/offline/frozen, vendor, and cycle/conflict tests |
| Related topics | workspace, dependency graph, lockfile, checksum, offline build |
| Related RFCs | [RFC 0008](./0008-canonical-package-identity-and-aliases.md), [RFC 0013](./0013-registry-protocol-and-package-integrity.md) |

---

## 1. Summary

Nomo uses three explicit graph layers: workspace discovery, canonical package resolution, and source-module imports. Traversal is stable and dependency-first. Resolution is recorded in the workspace-root `nomo.lock`, and available sources are pinned with `sha256:` checksums.

## 2. Motivation

Combining workspace, source resolution, and module imports into one recursive routine produces unstable ordering, vague cycle diagnostics, divergent CLI/LSP behavior, and no precise locked or offline contract.

## 3. Graph Model

- `WorkspaceGraph`: members, defaults, inherited fields, root lockfile, and member dependency order.
- `PackageGraph`: canonical packages, sources, versions/revisions, checksums, and transitive edges.
- `ModuleGraph`: Flat+Dir modules, visibility, import edges, and cycle paths within a package.

Shared graph utilities provide stable topological order and cycle paths that include the closing node. Duplicate workspace identities, member path cycles, and conflicting external package sources or versions are rejected while building the graphs.

## 4. Lockfile and Modes

- A workspace has one root lockfile. `[[root]]` records member direct edges and `[[package]]` de-duplicates shared dependencies.
- Path, Git, and fetched registry sources receive content checksums. Registry archive checksums remain distinct from unpacked source checksums.
- `--locked` rejects a missing or stale lockfile; `--offline` forbids network access; `--frozen` combines both.
- Vendor directories are portable copies of locked sources and may satisfy locked/offline builds when original sources or caches are absent.

## 5. Alternatives

| Option | Problem | Decision |
| --- | --- | --- |
| Command-local recursion | Duplicated logic, unstable order and diagnostics | Rejected |
| One lockfile per member | Cannot unify shared workspace dependencies | Rejected |
| Typed three-layer graphs + root lockfile | Clear boundaries reusable by CLI, LSP, and docs | Accepted |

## 6. Drawbacks and Risks

- v0.1 rejects multi-source or multi-version conflicts rather than solving them.
- A missing source can be displayed as an offline locked entry, but compilation still needs cache or vendor content.
- Checksum and archive formats are compatibility surfaces and require versioned changes.

## 7. Impact on v0.1 Scope

`check/build/run/test/doc/deps` share the same workspace/package/module facts. `nomoc` remains a manifest-free single-file boundary and does not load these graphs.

## 8. Decision

Accept typed three-layer graphs, stable dependency-first traversal, a workspace-root lockfile, verifiable source checksums, and locked/offline/frozen/vendor behavior as v0.1 tooling contracts.

## 9. Follow-up Questions

- Semantic version ranges and multi-version solving.
- Target-specific dependencies and lockfile representation.
- Versioning the lockfile and archive formats.

## 10. References

- `nomo-graph`, `nomo-lockfile`, workspace/package/module graph APIs, and resolver CLI tests.
- [RFC 0008](./0008-canonical-package-identity-and-aliases.md), [RFC 0013](./0013-registry-protocol-and-package-integrity.md).
