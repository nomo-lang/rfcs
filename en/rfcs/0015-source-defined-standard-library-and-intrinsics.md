# RFC 0015: Source-Defined Standard Library and Controlled Intrinsic Identities

> Language: [中文](../../zh-CN/rfcs/0015-source-defined-standard-library-and-intrinsics.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0015 |
| Title | Source-Defined Standard Library and Controlled Intrinsic Identities |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Prerequisites are partial: a canonical `nomo-lang/std` package and public module metadata exist, while core types still come from the compiler/runtime |
| Topics | standard library, intrinsic, lang item, bootstrap, ABI |
| Related RFCs | [RFC 0003](./0003-arc-cow-runtime-cost.md), [RFC 0006](./0006-option-result-lang-items.md), [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md) |

---

## 1. Summary

Move standard-library APIs and implementations expressible in Nomo into a versioned `nomo-lang/std` source package. The compiler retains only the minimal intrinsic set that ordinary language constructs cannot express. A toolchain-owned, versioned manifest binds special identities to canonical declarations; user-defined `#[lang]` remains unavailable.

## 2. Motivation

Public modules are stable today, but key facts for `Option`, `Result`, `string`, and `Array` are spread across compiler and runtime code. Source definitions let docs, LSP, package checksums, and ordinary tests see the library while avoiding bootstrap cycles and forged lang items.

## 3. Proposed Design

- The toolchain ships a locked `nomo-lang/std` source package resolved as a special read-only dependency.
- `Option`/`Result` declarations and expressible methods move to Nomo source; layout, `?`, ARC/COW, and low-level IO remain controlled intrinsics.
- A built-in `intrinsics.toml` binds canonical package/module/declaration plus schema version. User manifests cannot override it.
- Bootstrap validates required declarations, generic shapes, variants, and ABI; missing or duplicate identities are toolchain errors.
- Existing `std.*` imports, diagnostic codes, and generated C ABI remain compatible during migration.

## 4. Implementation Slices

1. Intrinsic-manifest schema, loader, and consistency diagnostics.
2. Move `Option`/`Result` declarations and pure Nomo methods, with dual-path conformance tests.
3. Move the `string`/`Array` public surface and freeze the runtime ABI.
4. Documentation/LSP source navigation, distribution packaging, and bootstrap acceptance.

## 5. Alternatives

| Option | Problem | Direction |
| --- | --- | --- |
| Permanently inject all standard types | Ordinary tools cannot inspect, test, or version them well | Reject |
| Expose a general `#[lang]` | Third parties could forge compiler-special identities | Reject |
| Toolchain manifest plus source declarations | Auditable with a controlled bootstrap boundary | Proposed |

## 6. Drawbacks and Risks

Migration touches shared identity across parser, type checker, codegen, runtime, docs, and LSP. Drift between manifest and source could prevent toolchain startup.

## 7. Compatibility and Migration

Retain the current compiler-carrier path as a conformance oracle until both implementations pass the same matrix. Do not rewrite public APIs and low-level representation in one change.

## 8. Acceptance Gate

This RFC may become `Accepted` only after at least `Option`/`Result` are source-defined and intrinsic validation, ABI conformance, doc/LSP navigation, and packaging tests pass.

## 9. Open Questions

- Is the manifest pinned by compiler version or a toolchain manifest?
- Which runtime operations must remain permanent intrinsics?
- May the standard library ship patch releases independently from the compiler?

## 10. References

- [RFC 0003](./0003-arc-cow-runtime-cost.md), [RFC 0006](./0006-option-result-lang-items.md).
