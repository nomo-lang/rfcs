# RFC 0019: Typed FFI Handles, Callbacks, and Bindings

> Language: [中文](../../zh-CN/rfcs/0019-typed-ffi-handles-callbacks-and-bindings.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0019 |
| Title | Typed FFI Handles, Callbacks, and Bindings |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Implemented: nominal handles, explicit nullability and ownership metadata, restricted callbacks, target-aware `repr(C)` layout, deterministic header bindings, provenance, and real C integration tests are present |
| Topics | FFI, opaque handle, nullable pointer, callback, C layout, binding generation |
| Related RFCs | [RFC 0004](./0004-mutable-borrow-uniqueness.md), [RFC 0011](./0011-c-ffi-safety-and-link-boundary.md), [RFC 0017](./0017-target-triples-and-cross-compilation.md) |

---

## 1. Summary

Extend RFC 0011 with non-interchangeable typed opaque handles, explicit nullable values, restricted `extern "C"` callbacks, and target-validated C struct/header bindings. Ownership and threading rules remain visible at declarations, and library authors still write safe wrappers explicitly.

## 2. Motivation

General `Opaque` is sufficient for simple C calls but cannot prevent mixing unrelated handles or express null, callback lifetimes, or struct ABI. Exposing arbitrary pointer operations would bypass Nomo's currently checkable safety boundary.

## 3. Proposed Design

- `extern opaque type FileHandle release file_close` creates a nominal, unconstructable, non-interchangeable handle with an explicit release contract. `Owned<FileHandle>` and `Borrowed<FileHandle>` describe transfer and borrow boundaries; `.borrow()` is the only implicit-view operation.
- Nullable C pointers use `Nullable<Handle>`, including owned or borrowed handles. `is_null()` tests the value and `unwrap()` is the explicit checked conversion; null never implicitly becomes an ordinary handle.
- Callbacks use only `extern "C" fn(...) -> ...` with ABI-safe parameters. The initial implementation accepts exact-signature, non-capturing top-level functions and rejects callback storage, return, or other escape. Callback panic uses Nomo's fail-fast panic path and never unwinds through C.
- `#[repr(C)]` records permit fixed-layout fields only and are checked against target size/alignment. Bitfields, unions, and flexible arrays are rejected initially.
- `nomo ffi bindgen <header> --package <package> --output <file>` reads a controlled C-header subset and emits ordinary Nomo source plus a deterministic provenance file. Generated source is reviewable and enters package checksums when checked into a package.
- Dereference, ownership transfer, and callback registration remain `unsafe`; safe wrappers are not generated automatically.

## 4. Implementation Slices

1. Nominal handles, nullability, ownership metadata, release-contract validation, and wrong-handle diagnostics are implemented.
2. Exact-signature top-level callback ABI, escape rejection, fail-fast panic containment, and real callback execution are implemented. Capturing/context trampolines and retained callbacks are intentionally outside this accepted first slice.
3. The `repr(C)` layout engine and Linux GNU/Windows MSVC x86-64 ABI fixtures are implemented.
4. The controlled header parser, deterministic generator, SHA-256 provenance, core CLI command, and generated-binding C link/run integration are implemented.

## 5. Alternatives

| Option | Problem | Direction |
| --- | --- | --- |
| Keep every object as `Opaque` | Handle mixups remain runtime failures | Insufficient |
| Expose arbitrary C-style pointers | Breaks current ownership and safety-check boundaries | Reject |
| Staged typed FFI | Adds expression while keeping unsafety visible | Accepted |

## 6. Drawbacks and Risks

Callback lifetimes and foreign-thread entry can easily create use-after-free, so retained callbacks and foreign-thread entry are rejected by the accepted slice. C ABI varies across targets, and the generator deliberately rejects unions, bitfields, arrays, flexible arrays, variadics, multiple pointer indirection, and unknown scalar spellings rather than claiming complete C support.

## 7. Compatibility and Migration

Existing `Opaque` APIs remain valid but may receive a lint guiding libraries toward nominal handles. Generated bindings are source and do not introduce implicit build-time execution.

## 8. Acceptance Gate

Satisfied. Compiler tests reject wrong-handle mixing, invalid null use, and callback escape; layout fixtures pass for `x86_64-unknown-linux-gnu` and `x86_64-pc-windows-msvc`; `ffi_typed_handle` executes a real C callback; and the CLI suite generates bindings from a header, compiles them with C, links, and runs the result.

## 9. Open Questions

- Full linear ownership and automatic destruction remain future work; this slice validates ownership metadata and release signatures but uses explicit `close` plus optional `defer`.
- Callbacks may not be retained or enter from foreign threads in this slice. A later RFC must define runtime attachment, lifetime, and synchronization before enabling either behavior.
- The binding generator is part of the core CLI as `nomo ffi bindgen`; it performs no implicit build-time execution.

## 10. References

- [RFC 0011](./0011-c-ffi-safety-and-link-boundary.md), [RFC 0017](./0017-target-triples-and-cross-compilation.md).
