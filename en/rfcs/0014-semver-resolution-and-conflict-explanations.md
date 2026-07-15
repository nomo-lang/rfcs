# RFC 0014: Semantic Version Resolution and Conflict Explanations

> Language: [中文](../../zh-CN/rfcs/0014-semver-resolution-and-conflict-explanations.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0014 |
| Title | Semantic Version Resolution and Conflict Explanations |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Landed: strict constraints, deterministic project/workspace single-version selection, stable minimal conflicts, registry-index caching, exact lockfile output, range-aware locked validation, constrained precise updates, and locked/offline/yank/prerelease/conflict tests |
| Topics | semver, resolver, lockfile, registry, diagnostics |
| Related RFCs | [RFC 0008](./0008-canonical-package-identity-and-aliases.md), [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md), [RFC 0013](./0013-registry-protocol-and-package-integrity.md) |

---

## 1. Summary

Allow exact, caret, tilde, and bounded comparison ranges in manifests. The resolver selects the highest non-yanked version satisfying every constraint for one canonical package and records that exact result in the workspace-root lockfile. An unsatisfiable graph must produce a minimal explanation traceable to dependency edges.

## 2. Motivation

Exact versions are reproducible but push compatible upgrades and coordination onto users. Ranges without deterministic solving, locking, and diagnostics would undermine the stable graph model established by RFC 0009.

## 3. Proposed Design

- Support `1.2.3`, `^1.2.3`, `~1.2.3`, and `>=1.2, <2.0`; no wildcard strings or implicit `latest`.
- The first solver uses single-version selection: one canonical id has one version in a resolved graph.
- Choose the highest candidate under a stable total order; fresh resolution excludes yanked releases while locked resolution may reuse a verified one.
- A pre-release participates only when a constraint explicitly includes one.
- The lockfile still stores exact version, source, and checksum. `--locked` never solves again; `update` may change selections.
- Conflict diagnostics name the package, incompatible constraints, the dependency path introducing each constraint, and actionable suggestions.

## 4. Implementation Slices

1. A standalone version/constraint parser and normalizer with property tests.
2. Registry-index candidate loading, a deterministic single-version solver, and a conflict graph.
3. Resolver/lockfile/CLI integration including precise `update -p`.
4. Offline, locked, yank, pre-release, and conflict snapshot tests.

### 4.1 Implemented behavior

`nomo-manifest` owns the shared SemVer types so manifests, the resolver, and
lockfiles use one interpretation. Bare complete versions are exact; caret,
tilde, and bounded comparison ranges are explicit. Wildcards, alternatives,
implicit `latest`, and `=` exact syntax are rejected. Timestamped snapshots such
as `0.0.0-20260713145859` are ordinary explicit prereleases.

`nomo-resolver` loads package indexes in stable order, excludes yanked and
implicit prerelease candidates, selects one highest version, caches HTTP index
metadata for offline resolution, and emits a deterministic irreducible
constraint set with dependency paths on conflict. Project resolution repeats
the graph pass when a later transitive or workspace-member constraint changes
an earlier selection, so the complete workspace can converge on a lower
compatible version instead of using a greedy first-edge result. Lockfiles
continue to store only the selected exact version, and locked validation checks
that exact version against the current manifest requirement without solving
again. `nomo deps update --precise` rejects versions outside the declared
manifest requirement.

## 5. Alternatives

| Option | Problem | Direction |
| --- | --- | --- |
| Remain exact-only | Continues shifting upgrade cost to users | Reject |
| Permit multiple versions immediately | Greatly complicates codegen, type identity, and linking | Later RFC |
| Deterministic single-version solving | Preserves simple canonical identity and graphs | Accepted |

## 6. Drawbacks and Risks

Single-version selection rejects some graphs that coexistence could solve. Unstable conflict explanations would make CI snapshots and user debugging unreliable.

## 7. Compatibility and Migration

Existing exact manifests and lockfiles remain valid. Ranges affect fresh resolution only; an old lockfile need not change while its selected version still satisfies all constraints.

## 8. Acceptance Gate

Accepted after the solver, workspace convergence, conflict explanations,
lockfile compatibility, and locked/offline/update end-to-end tests landed.

## 9. Open Questions

- Should a later model permit multiple instances of one canonical id?
- How should lockfile format versions represent solver-semantic upgrades?
- Does the registry protocol need a batched version-metadata endpoint?

## 10. References

- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md), [RFC 0013](./0013-registry-protocol-and-package-integrity.md).
