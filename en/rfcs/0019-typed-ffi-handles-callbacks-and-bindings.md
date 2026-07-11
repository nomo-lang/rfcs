# RFC 0019: Typed FFI Handles, Callbacks, and Bindings

> Language: [中文](../../zh-CN/rfcs/0019-typed-ffi-handles-callbacks-and-bindings.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0019 |
| Title | Typed FFI Handles, Callbacks, and Bindings |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Not implemented; the current boundary provides only general `Opaque`, `CString`, extern functions, and call-site `unsafe` |
| Topics | FFI, opaque handle, nullable pointer, callback, C layout, binding generation |
| Related RFCs | [RFC 0004](./0004-mutable-borrow-uniqueness.md), [RFC 0011](./0011-c-ffi-safety-and-link-boundary.md), [RFC 0017](./0017-target-triples-and-cross-compilation.md) |

---

## 1. Summary

Extend RFC 0011 with non-interchangeable typed opaque handles, explicit nullable values, restricted `extern "C"` callbacks, and target-validated C struct/header bindings. Ownership and threading rules remain visible at declarations, and library authors still write safe wrappers explicitly.

## 2. Motivation

General `Opaque` is sufficient for simple C calls but cannot prevent mixing unrelated handles or express null, callback lifetimes, or struct ABI. Exposing arbitrary pointer operations would bypass Nomo's currently checkable safety boundary.

## 3. Proposed Design

- `extern opaque type FileHandle` creates a nominal, unconstructable, non-interchangeable handle. Signatures may mark borrowed/owned returns and a release function.
- Nullable C pointers map to `Option<Handle>` or a dedicated nullable scalar; null never implicitly becomes an ordinary handle.
- Callbacks use only `extern "C" fn(...) -> ...` with ABI-safe parameters. Capturing closures do not cross directly; a context pointer pairs with an explicit trampoline/release protocol.
- `#[repr(C)]` records permit fixed-layout fields only and are checked against target size/alignment. Bitfields, unions, and flexible arrays are rejected initially.
- A binding generator reads a controlled C-header subset and emits ordinary Nomo source plus provenance. Generated output is reviewable and enters package checksums.
- Dereference, ownership transfer, and callback registration remain `unsafe`; safe wrappers are not generated automatically.

## 4. Implementation Slices

1. Nominal handles, nullability, ownership metadata, and type-check diagnostics.
2. Callback ABI, trampolines, panic/error containment, and lifetime tests.
3. `repr(C)` layout engine and cross-target ABI fixtures.
4. Header-subset parser, deterministic generator, provenance, and real-library integration tests.

## 5. Alternatives

| Option | Problem | Direction |
| --- | --- | --- |
| Keep every object as `Opaque` | Handle mixups remain runtime failures | Insufficient |
| Expose arbitrary C-style pointers | Breaks current ownership and safety-check boundaries | Reject |
| Staged typed FFI | Adds expression while keeping unsafety visible | Proposed |

## 6. Drawbacks and Risks

Callback lifetimes and foreign-thread entry can easily create use-after-free. C ABI varies across targets, and the generator must not claim complete C support.

## 7. Compatibility and Migration

Existing `Opaque` APIs remain valid but may receive a lint guiding libraries toward nominal handles. Generated bindings are source and do not introduce implicit build-time execution.

## 8. Acceptance Gate

This RFC requires rejection of wrong-handle mixing, invalid null use, and callback escape; layout fixtures on at least two targets; and one real callback plus one header-generated integration before becoming `Accepted`.

## 9. Open Questions

- Do owned handles need a language-level destruction protocol, or explicit `close` plus `defer`?
- May callbacks enter the Nomo runtime from foreign threads?
- Is the binding generator part of the core CLI or a separate tool?

## 10. References

- [RFC 0011](./0011-c-ffi-safety-and-link-boundary.md), [RFC 0017](./0017-target-triples-and-cross-compilation.md).
