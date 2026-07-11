# RFC 0011: The Safety, Ownership, and Link Boundary of C FFI

> 语言 / Language: [中文](../../zh-CN/rfcs/0011-c-ffi-safety-and-link-boundary.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0011 |
| Title | The safety, ownership, and link boundary of C FFI |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Landed: `extern "C"`, call-site `unsafe`, primitive/CString/Opaque mappings, manifest linker metadata, package-relative C sources, and checksum/publish/vendor aggregation have tests |
| Related topics | FFI, unsafe, CString, Opaque, linker metadata, native source |
| Related RFCs | [RFC 0003](./0003-arc-cow-runtime-cost.md), [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md) |

---

## 1. Summary

Nomo places C FFI unsafety at the call site. `extern "C"` only declares a signature; invoking it requires an `unsafe` block. Strings cross through owned `CString`, unknown foreign handles use non-dereferenceable `Opaque`, and native link data belongs to package manifests and is aggregated through the dependency graph.

## 2. Motivation

Passing Nomo `string` or arbitrary pointers directly to C obscures NUL termination, lifetime, release responsibility, and aliasing. Marking only declarations unsafe would hide the point where risk actually occurs.

## 3. Type Boundary

- Primitive integers, floats, bool, char, and `void` map to supported C ABI types.
- `CString.from_string` creates an owned NUL-terminated copy and maps to `const char *` as a parameter. C cannot return `CString` because ownership is unknown.
- `Opaque` maps to `void *`; it may be returned, stored, and passed back to extern functions, but not dereferenced, compared, or used in operations.
- C struct auto-layout, raw-pointer arithmetic, and header binding generation remain out of scope.

## 4. Calls and Linking

```rust
import std.ffi

extern "C" { fn puts(message: CString) -> i32 }

let message: CString = CString.from_string("hello")
unsafe { puts(message) }
```

`[ffi]` supports `libraries`, `library_paths`, `sources`, `frameworks`, and `link_args`. Relative paths resolve against the declaring package. Build and test aggregate metadata from the root and source dependencies. Standalone scripts do not read manifests and receive no link metadata.

## 5. Alternatives

| Option | Problem | Decision |
| --- | --- | --- |
| Implicit `string -> char *` | Ownership and NUL semantics are unclear | Rejected |
| Declaration-only unsafe | Call-site risk is invisible | Rejected |
| Explicit CString/Opaque + call-site unsafe | Clear and statically checkable boundary | Accepted |

## 6. Drawbacks and Risks

- `link_args` is a raw escape hatch that may harm portability.
- `Opaque` does not distinguish handle families; foreign APIs remain responsible for matching them.
- ABI compatibility still depends on the platform C compiler and libraries.

## 7. Impact on v0.1 Scope

FFI source enters package checksums, archives, and vendor output. Dependency linker metadata participates in final linking. FFI and unsafe diagnostics use E1500-E1599.

## 8. Decision

Accept call-site `unsafe`, explicit `CString`/`Opaque`, and manifest-owned native link metadata as the v0.1 C boundary.

## 9. Follow-up Questions

- Typed opaque handles, nullable pointers, and callback ABIs.
- C struct layout, header import, and binding generation.
- Target-specific linker metadata and cross-compilation.

## 10. References

- FFI parser/compiler/codegen tests, `ffi_puts`/native source examples, and manifest link tests.
- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md).
