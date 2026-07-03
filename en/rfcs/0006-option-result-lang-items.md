# RFC 0006: The Circular Dependency Between the `Option`/`Result` Standard Library and the Compiler's Built-in Awareness

> 语言 / Language: [中文](../../zh-CN/rfcs/0006-option-result-lang-items.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0006 |
| Title | Are `Option`/`Result` pure library types or compiler lang items |
| Status | Draft |
| Author | Nomo Language Working Group |
| Created | 2026-06-18 |
| Related topics | lang item, `Option`, `Result`, standard library boundary, C backend |
| Related RFCs | [RFC 0001](./0001-error-propagation-and-conversion.md) (`?` propagation), [RFC 0002](./0002-match-wildcard-and-nesting.md) (match exhaustiveness), [RFC 0007](./0007-unqualified-variant-access.md) (variant access) |

---

## 1. Summary

`std.option` and `std.result` are listed as standard-library packages in the current specification (standard-library design), but they are also the carriers of core language mechanisms: `?` propagation depends on the `Ok`/`Err` structure of `Result`, and `match` exhaustiveness and the C backend's `Result_T_E` layout also require the compiler to "recognize" these two types. The current specification does not point out this layer of coupling — it wants them to be ordinary libraries yet also wants the compiler to have built-in awareness of them, forming a circular dependency. This RFC discusses whether they should be set as compiler "known lang items" or pure libraries, leaning toward "declaring `Option`/`Result` as lang items: the definitions are still written in `std.option`/`std.result`, but the compiler recognizes them via an attribute/convention to support `?`, exhaustiveness, and codegen", remaining Draft.

---

## 2. Motivation

The delivery boundary requires both "`Result<T,E>`, `Option<T>`, postfix `?`" (language capabilities) and "`std.result`, `std.option`" (standard-library packages). These two things are listed separately in the current specification, but in implementation they refer to the same types. The problem is that the compiler must support:

- `?`: it must know "what is `Ok`, what is `Err`, and how to extract from / exit early on a `Result`".
- `match` exhaustiveness: doing exhaustiveness on `Option`/`Result` as ordinary enums is enough, but codegen's `Result_T_E` is a layout designed **specifically** for it.
- Variant construction `Result.Ok` / `Option.Some`: name resolution must be able to locate the variants of `std.result.Result`.

If we treat them as "ordinary library types the compiler knows nothing about", `?` and the dedicated layout of 4.4 are out of the question; if we treat them as "compiler built-in types", that contradicts the standard-library design's "they are standard-library packages". Without clarifying this, the compiler architecture (name resolution, type checking, codegen) will repeatedly struggle during implementation over "whether to special-case these two types".

---

## 3. Status and Problem

### 3.1 Current Specification Status

- Enum example: `Option<T>` is given as a payload-bearing enum example (`Some(T)` / `None`).
- `Result` definition: `Result<T,E>` is defined in `package std.result` (`Ok(T)` / `Err(E)`).
- `?` semantics: the semantics of `?` are described directly in terms of `Result.Ok`/`Result.Err`.
- C backend: the C backend gives a **dedicated** `Result_T_E` (`bool is_ok; union {ok; err;}`).
- Standard-library design: `std.option`, `std.result` are listed as v0.1 standard-library packages.
- Examples (the file-reading and array-swap examples) bring them in via `import std.result.Result` / `import std.option.Option`.

### 3.2 Problem Analysis

- **Circular dependency**: the standard library defines the type → the compiler must have built-in awareness of the type → only then can it compile the standard library itself (the definition of `Result` in `std.result`, and any library code that uses `?`).
- **`?` must have an anchor**: the expansion rule of `expr?` must be bound to a "known `Result`", otherwise can a user define any same-named `Result` and `?` it too? Or can only `std.result.Result` be `?`'d? The current specification does not answer.
- **codegen dedicated layout**: the `Result_T_E` of 4.4 shows that codegen does not use a "generic enum layout" for `Result` but a **special case**, which already treats it as a lang item, only without saying so.
- **The degree of `Option`'s built-in-ness**: `Option` has no `?` (4.3 only mentions `Result`), but `Array.get` (8.4) and `std.env.get` (8.3) both return `Option`, and [RFC 0002](./0002-match-wildcard-and-nesting.md) may add `?`-style early exit to `Option`; its degree of built-in-ness must be decided together with `Result`.

---

## 4. Detailed Design

### 4.1 Option A: Pure library (no compiler special-casing)

- **Approach**: `Option`/`Result` are ordinary generic enums; `?` changes to "take effect on any enum satisfying a certain structure" or simply requires standard pattern matching.
- **Advantages**: cleanest compiler, no special types.
- **Disadvantages**: `?` loses a clear anchor; the dedicated C layout loses its basis (either all enums use this layout, or the dedicated layout is abandoned); it is hard to guarantee "`?` takes effect only for error-propagation semantics". It basically cannot fulfill the existing promises of the current specification.

### 4.2 Option B: Fully built-in (compiler built-in types, the library only re-exports)

- **Approach**: `Option`/`Result` are defined built-in by the compiler, and `std.option`/`std.result` merely re-export.
- **Advantages**: `?`, exhaustiveness, and codegen all have stable anchors.
- **Disadvantages**: literally conflicts with the standard-library design's "they are standard-library packages"; when users read the standard-library source they do not see the real definition, violating the readability of "stable anchors".

### 4.3 Option C: lang item (preferred)

- **Approach**: the type **definitions are still written in** the `std.option`/`std.result` source (preserving the standard-library design's fact that "they are standard-library packages"), but the compiler recognizes them via a **lang-item annotation**, e.g. an internal attribute:

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

- **Semantics**:
  - `?` takes effect only on types annotated as `lang = "result"`, with a clear anchor.
  - `match` exhaustiveness treats them the same as ordinary enums (no special-casing needed), but codegen can recognize the lang item and apply the dedicated `Result_T_E` layout.
  - Name resolution treats `Result.Ok`/`Option.Some` as ordinary enum variants (consistent with [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md)), and [RFC 0007](./0007-unqualified-variant-access.md)'s prelude/unqualified variants also act on these two lang items.
- **Resolving the circular dependency**: when compiling `std.result` itself, the lang item is registered before use; the standard library can be split into two layers — the pure-definition layer (not depending on `?`) is compiled first, and library code that depends on `?` is compiled afterward.
- **C backend**: when codegen sees the lang item `result`, it applies the 4.4 layout; `option` uses a similar `Option_T` (`bool is_some; union{...}`).
- **Diagnostics**:
  - `N0330` the `result`/`option` lang item is not found (standard library missing or not annotated).
  - `?` used on a non-`result` lang item → type checking error (N04xx).
- **Attribute-syntax dependency**: a minimal internal attribute mechanism (`#[lang = "..."]`) is needed. This attribute can be made **available only to the compiler/standard library internally**, not exposed to users, to avoid introducing a full attribute system early.

---

## 5. Alternatives

| Option | Approach | Advantages | Disadvantages |
| --- | --- | --- | --- |
| A Pure library | No special-casing | Cleanest compiler | `?`/4.4 lose anchors, cannot fulfill the current specification |
| B Fully built-in | Compiler built-in, library forwards | Most stable anchors | Conflicts with "they are standard-library packages", source unreadable |
| C lang item (preferred) | Defined in the library, recognized by the compiler via annotation | Balances "library" and "built-in awareness", readable, clear anchors | Needs a minimal internal attribute mechanism |

---

## 6. Drawbacks and Risks

- Option C needs to introduce the internal attribute `#[lang = "..."]`. It must be made clear that it is **not** a general user-facing attribute system (that is a follow-up RFC), and is only for standard-library/compiler internal use, otherwise it would expand the v0.1 syntactic surface area.
- The layered compilation of the standard library (definition layer first, `?`-using layer later) needs to be reflected in the build order, to avoid a bootstrap-style cycle.
- The degree of built-in-ness of `Option` and `Result` must be aligned: both are set as lang items, and v0.1's `?` acts on both `Result` and `Option` through carrier-specific early return.

---

## 7. Impact on v0.1 Scope

- **Recommended to land in v0.1**: Option C. Declare `Option`/`Result` as lang items, with the definitions kept in `std.option`/`std.result`; the compiler uses this to support `?`, the codegen dedicated layout, and the (future) prelude.
- **Recommended current-specification supplement**: add a section to the standard-library design or compiler architecture pointing out that "`Option`/`Result` are lang items: both standard-library packages and recognized by the compiler", eliminating the current implicit coupling.
- **Acceptance impact**: the acceptance test matrix needs to add "report `N0330` when a lang item is missing/unannotated" and "`?` takes effect only on recognized `Result`/`Option` carriers" tests; codegen tests confirm the lang item applies the 4.4 layout.

---

## 8. Recommendation (remains Draft, not decided)

Lean toward **Option C (lang item)**: use the minimal internal `#[lang = "..."]` annotation to unify "standard-library package" and "compiler built-in awareness", preserving the fact of the standard-library design while giving `?` ([RFC 0001](./0001-error-propagation-and-conversion.md)), exhaustiveness ([RFC 0002](./0002-match-wildcard-and-nesting.md)), codegen, and variant simplification ([RFC 0007](./0007-unqualified-variant-access.md)) stable anchors. Remains Draft.

---

## 9. Open Questions

- The exact syntax and visibility of the internal attribute `#[lang]` (whether it is hidden from users).
- Beyond `Option`/`Result`, should `string`/`Array` ([RFC 0003](./0003-arc-cow-runtime-cost.md)) also be set as lang items to support dedicated runtimes?
- How to fix the standard-library layered-compilation order in `nomo build` and the compiler pipeline.

---

## 10. References

- The current `Option`/`Result` enum design, `?` propagation, C backend representation, standard library boundary, compiler architecture, file-reading and array-swap examples.
- [RFC 0001](./0001-error-propagation-and-conversion.md) (`?` anchor), [RFC 0002](./0002-match-wildcard-and-nesting.md) (exhaustiveness), [RFC 0007](./0007-unqualified-variant-access.md) (the prelude scope of variant simplification).
