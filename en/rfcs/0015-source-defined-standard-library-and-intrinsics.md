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
| Implementation | First through seventh slices implemented: the intrinsic manifest, validated source contracts, core, extension, network, and HTTP source-defined APIs, source-backed docs/LSP navigation, and release packaging are present; representation-sensitive ABI still comes from the compiler/runtime |
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

### 4.1 First slice: intrinsic manifest

The first implementation slice adds `std/intrinsics.toml` with schema version,
canonical package identity, source module mapping, binding kind, ABI label, and
required identities. `nomo-std` exposes a parser and validator; compiler
lowering and `nomo doc --std` invoke the validator. Duplicate bindings,
unknown modules, source mapping drift, unsupported kinds, and missing required
`Option`/`Result`/`?` identities report stable `E0800` diagnostics. This slice
does not move carrier declarations or runtime lowering yet.

### 4.2 Second slice: carrier source contract

`std/src/option.nomo` and `std/src/result.nomo` now define the canonical enum
shapes and pure `is_some`/`is_none`/`is_ok`/`is_err`/`unwrap_or` helpers. The
toolchain parses and type-checks those files as library modules, and compiler
tests compare their shapes with the compatibility carrier injection used by
normal projects. `map`, `map_err`, and `and_then` stay intrinsic-backed because
the current language has no function-value type.

### 4.3 Third slice: `Array` and `string` source surface

`std/src/array.nomo` and `std/src/string.nomo` now declare the complete v0.1
public helper surface. Their bodies delegate representation-sensitive work to
the existing compiler lowerings, so source signatures and generated C behavior
remain aligned during migration. The intrinsic manifest requires the canonical
`Array` and `string` layout bindings and pins the current ABI labels:
`array-header` uses typed `len`/`cap`/`data` storage with non-atomic reference
counting and copy-on-write on writes; `string-header` uses immutable `data` plus
non-atomic reference-counted ownership. Source parsing, type checking, manifest
identity, and standard-library documentation all cover this contract.

### 4.4 Fourth slice: source-backed tooling and distribution

Compiler semantic queries, `nomo doc --std`, and `nomo-lsp` now read the
canonical `std/src/*.nomo` files for public signatures, documentation, hover,
workspace symbols, and definition targets. `Array` remains a compiler-owned
special type during this migration, so its navigation symbol is source-anchored
while its representation is still supplied by the runtime ABI. Standard-library
source is included in both compiler and LSP release archives; installed binaries
resolve it from `NOMO_STD_SOURCE_ROOT` or the archive's adjacent `std/src`
directory. Bootstrap acceptance covers source parsing, manifest identity,
semantic queries, documentation output, and release-package layout.

### 4.5 Fifth slice: core source-defined API surface

The canonical source files for `std.io`, `std.fs`, `std.path`, `std.env`,
`std.process`, `std.time`, `std.num`, `std.math`, `std.char`, and `std.os` now
declare their public structs, functions, signatures, and doc comments. The
toolchain validates each source package declaration and compares its public
top-level names with the standard import registry. Host-sensitive calls still
lower through the existing compiler/runtime builtin implementations, preserving
the current behavior while making source the public documentation and semantic
surface. Numeric overload-like behavior remains a compiler intrinsic boundary
until constrained generic interfaces can express it directly.

### 4.6 Sixth slice: extension source-defined API surface

The source package now also declares `std.collections`, `std.hash`, `std.crypto`,
`std.json`, `std.regex`, `std.debug`, `std.log`, and `std.testing`. Public
structs, functions, contextual `debug.panic`, and documentation are parsed from
source and checked against the import registry. Their host/runtime behavior
continues to use the existing builtin lowerings. `panic` is accepted as a
contextual function declaration name because it is both an expression keyword
and a required standard-library API name.

### 4.7 Seventh slice: network and HTTP source-defined API surface

The source package now also declares `std.net` and `std.http`. Their public error,
response, datagram, and opaque handle types plus blocking client/server functions
are checked against the standard import registry. TCP, UDP, and HTTP handles expose
source-level methods or close helpers matching the existing builtin lowering. The
runtime remains responsible for sockets, HTTP parsing, and host errors; these source
files define the public signatures and documentation. Callers can combine `defer`
with postfix `?` to close accepted exchanges, servers, and other handles on both
normal returns and propagation paths.

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
