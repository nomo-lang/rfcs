# RFC 0010: Constrained Generics and Static Interface Dispatch

> 语言 / Language: [中文](../../zh-CN/rfcs/0010-constrained-generics-and-static-interface-dispatch.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0010 |
| Title | Constrained generics and static interface dispatch |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Landed: interface/impl validation, one-bound generics, explicit concrete type arguments, constrained-body checking, monomorphization, and static dispatch have parser/compiler/codegen/LSP coverage |
| Related topics | interface, generics, monomorphization, static dispatch, semantic owner |
| Related RFCs | [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md), [RFC 0012](./0012-shared-semantic-identities-and-verified-rename.md) |

---

## 1. Summary

v0.1 supports a minimal interface constraint: each type parameter may have at most one `T: Interface` bound; calls provide an explicit concrete type argument; the compiler permits only operations from that bound, verifies a matching impl on the concrete struct, then monomorphizes and statically dispatches the call.

## 2. Motivation

Unconstrained generics cannot safely invoke type-specific behavior, while a complete trait system adds multiple bounds, `where`, associated types, dynamic dispatch, and substantial coherence rules. v0.1 needs a checkable, C-generatable middle point.

## 3. Syntax

```rust
pub interface Display {
    fn to_string(self) -> string
}

fn render<T: Display>(value: T) -> string {
    return value.to_string()
}

let text: string = render<User>(user)
```

## 4. Semantics

- An interface impl provides every method and matches type parameters, parameter count, mutability, parameter types, and return type.
- A bound method call in a generic body resolves to the interface declaration, not an arbitrary concrete impl.
- A concrete call names a non-generic struct with a matching impl; type argument inference is not performed.
- Codegen monomorphizes the generic function and statically dispatches methods without a vtable or trait object.

## 5. Alternatives

| Option | Problem | Decision |
| --- | --- | --- |
| Unbounded generics | Cannot safely call type-dependent behavior | Insufficient |
| Full trait system | Too broad semantically and operationally | Deferred |
| One interface bound + static dispatch | Checkable, monomorphizable, C-friendly | Accepted |

## 6. Drawbacks and Risks

- Explicit concrete type arguments are verbose.
- One bound cannot express capability composition.
- Impl coherence currently covers the v0.1 package/module visibility model.

## 7. Impact on v0.1 Scope

Multiple bounds, `where`, associated types, blanket impls, trait objects, dynamic dispatch, specialization, and higher-kinded types remain unsupported. Formatter, docs, LSP signatures, and navigation preserve and understand bounds.

## 8. Decision

Accept one interface bound, explicit concrete type arguments, monomorphization, and static dispatch as the current abstraction boundary.

## 9. Follow-up Questions

- Type argument inference and multiple bounds.
- Cross-package orphan and coherence rules.
- Whether associated types or dynamic dispatch justify separate RFCs.

## 10. References

- Constrained-generic parser, interface validation, monomorphized codegen, and semantic-owner tests.
- [RFC 0012](./0012-shared-semantic-identities-and-verified-rename.md).
