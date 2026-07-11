# RFC 0017: Target Triples, Conditional Dependencies, and Cross Compilation

> Language: [中文](../../zh-CN/rfcs/0017-target-triples-and-cross-compilation.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0017 |
| Title | Target Triples, Conditional Dependencies, and Cross Compilation |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Prerequisites are partial: the C99 backend, native linker metadata, and multi-platform release workflow exist; a unified target model does not |
| Topics | target triple, cross compilation, conditional dependency, linker, sysroot |
| Related RFCs | [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md), [RFC 0011](./0011-c-ffi-safety-and-link-boundary.md) |

---

## 1. Summary

Define canonical target triples and make compiler, resolver, lockfile, standard-library selection, and native linker metadata share one target context. Host and target are distinct, and conditional dependencies use only restricted, statically evaluable target predicates.

## 2. Motivation

A C backend aids portability, but emitting C is not reproducible cross compilation. If target means different things during dependency solving, ABI selection, standard-library loading, and linking, the same lockfile may produce different graphs or invalid binaries.

## 3. Proposed Design

- Triples use `arch-vendor-os-env` with explicit canonicalization and unsupported-target diagnostics.
- The CLI accepts `--target`; omission resolves the host triple. Target participates in cache and artifact identity.
- Manifests may condition dependencies, C sources, libraries, search paths, and flags on restricted equality/set predicates over `target.os/arch/env`.
- Lockfiles record the complete known dependency set and conditions rather than silently deleting edges for the current host.
- A toolchain target bundle provides ABI facts, C compiler/linker configuration, and standard-library/runtime artifacts. Environment variables enter only through explicit configuration layers.
- Build scripts and arbitrary code execution are outside the first version.

## 4. Implementation Slices

1. Target parser, canonicalization, host detection, and ABI table.
2. Manifest predicates, graph filtering, and lockfile representation.
3. C compiler/linker/sysroot configuration and FFI target metadata.
4. Host plus cross CI on at least Linux and macOS, including artifact inspection.

## 5. Alternatives

| Option | Problem | Direction |
| --- | --- | --- |
| Depend entirely on the host C environment | Irreproducible and detects errors too late | Reject |
| General script conditions | Prevent static graph analysis and expand supply-chain execution | Reject |
| Restricted predicates plus target bundles | Analyzable, cacheable, and testable | Proposed |

## 6. Drawbacks and Risks

The target matrix grows quickly. Incorrect ABI facts or linker flags are harder to diagnose than ordinary syntax errors.

## 7. Compatibility and Migration

Projects without target configuration retain host-build behavior. Existing global native metadata applies to every target and gains staged migration diagnostics.

## 8. Acceptance Gate

This RFC requires verified host/target graph consistency, conditional lockfiles, FFI linking, cache isolation, and at least one real cross-build CI path before becoming `Accepted`.

## 9. Open Questions

- What support tiers and release promises apply to official targets?
- May users define custom JSON targets?
- May target-specific sources replace a module with the same name?

## 10. References

- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md), [RFC 0011](./0011-c-ffi-safety-and-link-boundary.md).
