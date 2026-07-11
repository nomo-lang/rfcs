# RFC 0006: The Circular Dependency Between the `Option`/`Result` Standard Library and the Compiler's Built-in Awareness

> 语言 / Language: [中文](../../zh-CN/rfcs/0006-option-result-lang-items.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0006 |
| Title | Are `Option`/`Result` pure library types or compiler-owned carriers |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-06-18 |
| Implementation | Landed: the compiler owns the `Option`/`Result` carrier identities, variants, `?` semantics, and C layouts; `std.option`/`std.result` are stable public module contracts and do not depend on a `#[lang]` attribute |
| Related topics | compiler-owned identities, lang-item migration, `Option`, `Result`, standard library boundary, C backend |
| Related RFCs | [RFC 0001](./0001-error-propagation-and-conversion.md) (`?` propagation), [RFC 0002](./0002-match-wildcard-and-nesting.md) (match exhaustiveness), [RFC 0007](./0007-unqualified-variant-access.md) (variant access) |

---

## 1. Summary

`Option` and `Result` are both public standard-library APIs and core language carriers. The current implementation uses compiler-owned identities: the compiler directly provides their generic enum shapes, `?` semantics, core-prelude variants, and C layouts, while `std.option` and `std.result` remain stable user-facing module contracts. v0.1 does not parse or compile a Nomo standard library annotated with `#[lang]`, so it does not introduce an unimplemented internal attribute mechanism or standard-library bootstrap order.

---

## 2. Motivation

The delivery boundary requires both "`Result<T,E>`, `Option<T>`, postfix `?`" (language capabilities) and "`std.result`, `std.option`" (standard-library packages). These two things are listed separately in the current specification, but in implementation they refer to the same types. The problem is that the compiler must support:

- `?`: it must know "what is `Ok`, what is `Err`, and how to extract from / exit early on a `Result`".
- `match` exhaustiveness: doing exhaustiveness on `Option`/`Result` as ordinary enums is enough, but codegen's `Result_T_E` is a layout designed **specifically** for it.
- Variant construction `Result.Ok` / `Option.Some`: name resolution must be able to locate the variants of `std.result.Result`.

If we treat them as "ordinary library types the compiler knows nothing about", `?` and the dedicated layout of 4.4 are out of the question; if we treat them as "compiler built-in types", that contradicts the standard-library design's "they are standard-library packages". Without clarifying this, the compiler architecture (name resolution, type checking, codegen) will repeatedly struggle during implementation over "whether to special-case these two types".

---

## 3. Status and Problem

### 3.1 Current Implementation Status

- Enum example: `Option<T>` is given as a payload-bearing enum example (`Some(T)` / `None`).
- The public identities of `Result` and `Option` are exposed through `std.result` and `std.option`; the compiler injects the corresponding enum definitions when required.
- `?` semantics: the semantics of `?` are described directly in terms of `Result.Ok`/`Result.Err`.
- C backend: the C backend gives a **dedicated** `Result_T_E` (`bool is_ok; union {ok; err;}`).
- Standard-library design: `std.option`, `std.result` are listed as v0.1 standard-library packages.
- Examples may import `std.result.Result` / `std.option.Option` explicitly; use of core-prelude variants also causes the compiler to provide the required carrier.

### 3.2 Problem Analysis

- **The cycle is removed**: the v0.1 standard library is implemented through compiler-provided APIs and the C runtime, not by first compiling a Nomo standard-library source tree, so no layered bootstrap is required.
- **`?` has a stable anchor**: type checking accepts only the compiler-recognized `Result<T,E>` and `Option<T>` carriers; an ordinary user enum with the same short name cannot replace the standard type.
- **Codegen-specific layouts**: the C backend emits dedicated `Result`/`Option` layouts and early-return paths from the checked carrier type.
- **Built-in awareness is aligned**: `Option` and `Result` use the same class of compiler-owned identity and jointly support standard-library returns, `?`, and the core prelude.

---

## 4. Detailed Design

### 4.1 Option A: Pure library (no compiler special-casing)

- **Approach**: `Option`/`Result` are ordinary generic enums; `?` changes to "take effect on any enum satisfying a certain structure" or simply requires standard pattern matching.
- **Advantages**: cleanest compiler, no special types.
- **Disadvantages**: `?` loses a clear anchor; the dedicated C layout loses its basis (either all enums use this layout, or the dedicated layout is abandoned); it is hard to guarantee "`?` takes effect only for error-propagation semantics". It basically cannot fulfill the existing promises of the current specification.

### 4.2 Option B: Compiler-owned identities plus standard module contracts (accepted)

- **Approach**: the generic enum shapes and carrier semantics of `Option`/`Result` are compiler-owned; `std.option`/`std.result` are the public contracts for imports, documentation, and standard helpers. The compiler injects required standard types based on imports, type use, standard API return types, and core-prelude use.
- **Advantages**: `?`, exhaustiveness, and codegen all have stable anchors.
- **Disadvantages**: the normative type definitions currently live in the compiler and specification rather than independently compilable Nomo standard-library source; moving them out later requires a migration plan.

### 4.3 Option C: source-level `#[lang]` annotation (not adopted for v0.1)

- **Candidate approach**: keep the type definitions in `std.option`/`std.result` source and let the compiler recognize them through a lang-item attribute, for example:

```rust
package std.result

#[lang = "result"]
pub enum Result<T, E> {
    Ok(T)
    Err(E)
}
```

```rust
package std.option

#[lang = "option"]
pub enum Option<T> {
    Some(T)
    None
}
```

- **If adopted later, its semantics would be**:
  - `?` takes effect only on types annotated as `lang = "result"`, with a clear anchor.
  - `match` exhaustiveness treats them the same as ordinary enums (no special-casing needed), but codegen can recognize the lang item and apply the dedicated `Result_T_E` layout.
  - Name resolution treats `Result.Ok`/`Option.Some` as ordinary enum variants (consistent with [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md)), and [RFC 0007](./0007-unqualified-variant-access.md)'s prelude/unqualified variants also act on these two lang items.
- **Migration requirement**: this first needs compilable standard-library source, a controlled internal attribute, and a clear bootstrap order.
- **C backend (if adopted later)**: codegen would select the `Result`/`Option` layouts through the controlled lang-item identity.
- **Diagnostics (if adopted later)**: migration would need diagnostics for missing, duplicate, or incorrectly annotated standard carriers, plus `?` on a non-carrier type; a migration RFC would assign the exact codes.
- **Attribute-syntax dependency**: a minimal internal attribute mechanism (`#[lang = "..."]`) is required. The current parser exposes only supported user attributes, so v0.1 documentation must not assume this mechanism already exists.

---

## 5. Alternatives

| Option | Approach | Advantages | Disadvantages |
| --- | --- | --- | --- |
| A Pure library | No special-casing | Cleanest compiler | `?`/4.4 lose anchors, cannot fulfill the current specification |
| B Compiler-owned identity (accepted) | Compiler provides the carriers; `std.*` provides public module contracts | Matches the current runtime/type checker and has no bootstrap cycle | Standard type definitions are not yet independently compilable Nomo source |
| C Source lang item | Defined in the library, recognized by the compiler via annotation | Balances library source and built-in awareness | The attribute mechanism and standard-library bootstrap pipeline do not exist today |

---

## 6. Drawbacks and Risks

- Option B makes the compiler the source of truth for standard carrier shapes; the specification, diagnostic docs, and injected definitions must remain synchronized.
- If standard-library source is moved out later, recognition must not rely on a user-controlled short name; it needs a controlled package identity or internal annotation migration.
- The built-in degree of `Option` and `Result` must remain aligned, with carrier-specific early-return rules for `?`.

---

## 7. Impact on v0.1 Scope

- **Landed in v0.1**: Option B. The compiler owns the `Option`/`Result` carriers, while `std.option`/`std.result` retain their public module/API identities.
- **Specification treatment**: state the current built-in boundary without claiming a `#[lang]` attribute or independently compiled standard-library definition layer.
- **Acceptance coverage**: `?` accepts only compatible carriers; conflicting user types are rejected; codegen and lifecycle tests cover the dedicated `Result`/`Option` representations and early-return paths.

---

## 8. Decision

Accept **Option B (compiler-owned identities plus standard module contracts)**. This is the architecture implemented today: the compiler injects `Option`/`Result` and recognizes them across type checking, `?`, the prelude, and the C backend; `std.option`/`std.result` provide stable user-facing module identities. v0.1 does not introduce an unimplemented `#[lang]` attribute. A future move to Nomo-authored standard-library source may adopt a controlled lang-item mechanism through a separate RFC.

---

## 9. Follow-up Questions

- If the standard library moves to Nomo source, whether internal identity should use package paths, a controlled attribute, or a generated manifest.
- Whether other compiler/runtime-special types such as `string` and `Array` need a unified internal identity model.
- How to preserve the existing `std.option`/`std.result` APIs, diagnostic codes, and generated C ABI during such a migration.

---

## 10. References

- The current `Option`/`Result` enum design, `?` propagation, C backend representation, standard library boundary, compiler architecture, file-reading and array-swap examples.
- [RFC 0001](./0001-error-propagation-and-conversion.md) (`?` anchor), [RFC 0002](./0002-match-wildcard-and-nesting.md) (exhaustiveness), [RFC 0007](./0007-unqualified-variant-access.md) (the prelude scope of variant simplification).
