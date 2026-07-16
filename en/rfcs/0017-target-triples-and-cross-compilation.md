# RFC 0017: Target Triples, Conditional Dependencies, and Cross Compilation

> Language: [中文](../../zh-CN/rfcs/0017-target-triples-and-cross-compilation.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0017 |
| Title | Target Triples, Conditional Dependencies, and Cross Compilation |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Complete: canonical targets, restricted manifest predicates, complete conditional lockfiles, target-filtered workspace/package/module/FFI graphs, isolated artifacts, and real macOS and GNU/Linux cross-build CI paths are implemented |
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

1. **Landed:** target parser, canonicalization, host detection, and ABI table in
   the shared `nomo-target` crate.
2. **Landed:** dependency entries accept restricted `arch`, `os`, and `env`
   equality/set predicates. Resolution retains the complete known graph,
   conditional lockfile edges preserve canonical predicates, and workspace,
   package, module, and CLI tree views filter with one target context.
3. **Landed:** the target context reaches C emission, dependency selection,
   conditional C sources/libraries/search paths/flags, ABI validation, and
   native linking. Apple Clang and target-prefixed GNU compilers provide the
   first explicit compiler/linker/sysroot bundles.
4. **Landed:** arm64 macOS CI links and inspects a real x86-64 Mach-O. x86-64
   Linux CI links an AArch64 ELF, inspects it with `readelf`/`file`, executes it
   with QEMU against the target sysroot, and uploads target-scoped evidence.

Explicit `nomo build --target <triple>` places artifacts under
`build/<canonical-target>/{c,bin}`. `nomoc build --target` and
`nomo build --emit-c --target` embed canonical target macros in generated C.
Non-host native linking fails early unless a concrete toolchain path is
configured; merely recognizing a triple does not imply link support.

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

The acceptance gate is satisfied by canonical target unit tests, manifest and
lockfile round trips, target-filtered locked-build integration tests,
target-scoped artifacts and FFI metadata, and real macOS and GNU/Linux
cross-build jobs.

## 9. Future Extensions

- Formal support tiers and release promises for every recognized target.
- User-defined JSON targets and custom compiler/linker/sysroot bundles.
- Target-specific module replacement beyond conditional dependency and native
  metadata edges.

## 10. References

- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md), [RFC 0011](./0011-c-ffi-safety-and-link-boundary.md).
