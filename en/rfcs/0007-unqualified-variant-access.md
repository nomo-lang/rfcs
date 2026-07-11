# RFC 0007: Whether Qualified Variant Access Can Be Simplified to the Unqualified Form

> 语言 / Language: [中文](../../zh-CN/rfcs/0007-unqualified-variant-access.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0007 |
| Title | Whether `Enum.Variant` can/should be simplified to an unqualified `Variant` |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-06-18 |
| Implementation | Landed: `Some`/`None`/`Ok`/`Err` may be unqualified; local names win; user enums remain qualified; qualified core variants stay compatible |
| Related topics | enum variants, prelude, name resolution, `Option`, `Result`, ergonomics |
| Related RFCs | [RFC 0002](./0002-match-wildcard-and-nesting.md) (match readability), [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md) (`.` resolution), [RFC 0006](./0006-option-result-lang-items.md) (core carrier identities) |

---

## 1. Summary

This RFC accepts unqualified access only for the core prelude `Option`/`Result` variants: `Some`, `None`, `Ok`, and `Err` may be used in constructors and patterns, while user-defined enums still require `Enum.Variant`. A local binding or function with the same name wins through lexical scope; callers can use `Option.Some` or `Result.Ok` to disambiguate. The formatter does not force qualified forms into unqualified forms, so both core spellings remain compatible.

---

## 2. Motivation

`Option`/`Result` are the backbone of v0.1 error handling and optional values; almost every function writes `Result.Ok(...)` / `Result.Err(...)` / `Option.Some(...)` / `Option.None`. The qualifying prefix appears verbose at these high-frequency spots, especially in the double-nested `match` (the array-swap example) where `Option.Some`/`Option.None` appear repeatedly, hurting both readability and writing cost. Whether to simplify, and to what scope, directly relates to daily ergonomics and the AI-generation experience, and is worth deciding with an RFC.

---

## 3. Status

The current specification **uniformly uses the qualified form throughout**, both in construction and in patterns:

- Construction and `match`: `Color.Red`, `Option.Some(T)` / `Option.None`.
- `Result` construction and the file-reading example: `Result.Ok(text)`, `Result.Err(AppError.ReadFailed(err.message))`, with `Result.Ok(text) => ...` in `match`.
- `?` semantics: the `?` semantics are described in terms of `Result.Ok`/`Result.Err`.
- The array-swap example: `Option.Some` / `Option.None` appear four times in the double `match`.

For imports, the current module system supports `import std.result.Result` (importing the **type**), but the current specification does **not** show importing a single variant (e.g. `import std.result.Ok`), and explicitly states "no wildcard imports". Therefore, under the current model, variants can only be accessed qualified by their type name.

---

## 4. Simplification Options

### 4.1 Option (a): Allow variant imports (an explicit version of Rust's `use Enum::*`)

- **Approach**: allow `import std.option.{Some, None}` or `import std.result.{Ok, Err}`, after which the unqualified `Some(x)` / `None => ...` in `match` can be written.
- **Advantages**: the origin is traceable (consistent with 3.1 "the origin of every symbol must be traceable"), brought in on demand, conflicts controllable (same-name conflicts are reported at the import site).
- **Disadvantages**: every file must write an import line; it needs to be clearly distinguished from "no wildcard imports" (this is a **named** import, not a wildcard, so it does not violate it).

### 4.2 Option (b): Global pre-import of core-type variants (prelude, accepted)

- **Approach**: the compiler implicitly pre-imports a set of prelude symbols for every package, including `Option`'s `Some`/`None` and `Result`'s `Ok`/`Err` (based on the compiler-owned carrier identities from [RFC 0006](./0006-option-result-lang-items.md)). Users can write the following without importing:

```rust
fn read_config(path: string) -> Result<string, AppError> {
    match fs.read_to_string(path) {
        Ok(text) => Ok(text)
        Err(err) => Err(AppError.ReadFailed(err.message))
    }
}
```

- **Advantages**: eliminates the highest-frequency prefix redundancy; the names (`Some/None/Ok/Err`) are de facto unique within the ecosystem, with extremely low conflict probability; stacks well with the nesting relief of [RFC 0002](./0002-match-wildcard-and-nesting.md).
- **Disadvantages**: introduces "implicitly visible symbols", in some tension with "traceable origin" (but the prelude is a fixed, documentable small set, similar to language built-ins, and acceptable); the prelude list and override rules need to be clarified (how to handle a user-defined same-named `Ok`).

### 4.3 Option (c): Infer the variant by the matched value's type in `match` context (omit qualification)

- **Approach**: in `match x { ... }`, given `x: Option<i32>`, the arm patterns may omit the qualification and write `Some(n)` / `None`, and the compiler resolves the variant by the type of `x`; construction still needs qualification or inference when the type is known.
- **Advantages**: only opened in contexts where the type is determined, so conflicts hardly exist; exhaustiveness checking is unaffected (still validated against all variants of that enum).
- **Disadvantages**: at construction sites (`return Ok(...)`) there is not necessarily enough type context, so the simplification is incomplete; the rule "when can it be omitted" is less intuitive for users and AI than the prelude; name resolution needs to introduce "expected-type-driven variant lookup".

### 4.4 Option (d): Keep the status quo (fully qualified)

- **Approach**: unchanged, all `Enum.Variant`.
- **Advantages**: zero ambiguity, the most explicit origin, most consistent with the explicit-origin principle, simplest name resolution (the `.` rules of [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md) suffice).
- **Disadvantages**: high-frequency prefix redundancy, with nesting like 11.4 being especially verbose.

---

## 5. Necessity Assessment

### 5.1 Whether necessary: conclusion

**Partially necessary**. Un-qualifying the variants of `Option`/`Result` (`Some/None/Ok/Err`) has **strong benefit and low risk**, and is worth doing; globally un-qualifying **user-defined enums** is **unnecessary** and should stay qualified or be enabled only via explicit named imports.

### 5.2 Trade-off Analysis

- **Naming-conflict risk**: multiple enums may have same-named variants (e.g. multiple enums all called `Red`/`Pending`). Global un-qualifying would make the bare `Red` ambiguous, requiring resolution rules or conflict reporting. `Some/None/Ok/Err`, by contrast, are nearly exclusive in practice, with extremely low conflict risk — this is the key reason to **confine the simplification to core types**.
- **Exhaustiveness and readability**: exhaustiveness checking enumerates all variants based on "the type of the matched value", **independent** of whether variants are qualified, so un-qualifying does not weaken exhaustiveness ([RFC 0002](./0002-match-wildcard-and-nesting.md)). For readability, the qualified form makes "which enum's arm is this" clear at a glance; but for universally known types like `Ok/Err/Some/None`, the prefix is noise instead. Conclusion: un-prefix core types to improve readability, keep the prefix on custom enums for clarity.
- **Impact on parser / name resolution (compiler architecture)**:
  - Status quo (d): name resolution suffices with the `.` rules of [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md), the simplest.
  - prelude (b) / import (a): name resolution supports a "bare identifier → variant" lookup path; the current priority is local binding/parameter/function > prelude variant.
  - Type inference (c): needs to introduce expected-type-driven variant resolution, the most complex.
- **AI-friendliness (avoiding multiple ways to write the same semantics)**: this is the **biggest objection**. If both `Result.Ok` and `Ok` are allowed, "two ways to write the same semantics" appears, violating 2.2. Mitigation: **keep only one recommended way** — uniformly recommend the unqualified form for core types (`Ok`/`Err`/`Some`/`None`) and converge it via the formatter/lint; uniformly qualify custom enums. That is "one form per domain", rather than "two forms everywhere".
- **Consistency with "no wildcard imports"**: Option (a) is a **named** import, not a `*` wildcard, and does not violate 3.1; Option (b) prelude is a fixed set built into the language, similar to keyword-level visibility, and is also not a wildcard import. Both are compatible with 3.1; what really must be avoided is "`import std.option.*`-style wildcards".

---

## 6. Detailed Design (accepted option: prelude-only)

- **Syntax**: `Some`/`None`/`Ok`/`Err` may be used unqualified in construction and in `match` patterns; all other enum variants stay `Enum.Variant`.
- **Semantics/name resolution (compiler architecture)**:
  - The pre-imported set (prelude) = `Result.{Ok, Err}` + `Option.{Some, None}`, based on the compiler-owned carrier identities accepted by [RFC 0006](./0006-option-result-lang-items.md).
  - The order for resolving a bare identifier is local binding/parameter > current-package symbol > prelude variant. A same-named user symbol shadows the prelude; no extra lint is emitted today.
  - Exhaustiveness, codegen, and the qualified form are fully equivalent (the same variant).
- **Diagnostics**:
  - `E0340` ambiguous bare variant name (only if a future prelude expansion causes a conflict).
  - No mandatory style lint is emitted today; qualified core forms remain available for compatibility and explicit disambiguation.
- **C backend**: no impact; after resolution it generates the same code as the qualified form.
- **Relationship with (a)**: the named variant import of Option (a) can be kept alongside as an explicit outlet for "custom enums that want to drop the prefix", but v0.1 can do only the prelude first, leaving (a) for v0.2.

---

## 7. Impact on v0.1 Scope

- **Landed in v0.1**: the minimal form of Option (b) — only the four `Option`/`Result` variants enter the core prelude, with lexical shadowing rules.
- **Compatibility policy**: qualified core variants remain valid; the formatter currently performs no mandatory rewrite or style lint.
- **Defer**: Option (a) named variant imports and Option (c) type-inference omission are left for v0.2.
- **Acceptance impact**: the name-resolution tests in the acceptance test matrix need to cover "bare `Ok`/`None` resolves correctly", "a user same-named symbol shadows the prelude", and "a bare variant of a custom enum still reports unresolved".

---

## 8. Decision

Accept **unqualified forms only for the core prelude `Option`/`Result` variants (`Some`/`None`/`Ok`/`Err`), with all other enums remaining qualified**. Lexical names take precedence over the prelude; qualified core variants remain available for explicit disambiguation and compatibility. This decision does not require the formatter or a lint to enforce a single spelling.

---

## 9. Follow-up Questions

- Whether the precise prelude list is limited to `Option`/`Result`, or includes more core types in the future.
- Whether to provide Option (a)'s named variant imports in the future.
- Whether to add an optional style lint without changing the semantic compatibility of the two core spellings.

---

## 10. References

- The current AI-friendliness principle, module import rules, enum design, `Result` semantics, name resolution, file-reading and array-swap examples.
- [RFC 0002](./0002-match-wildcard-and-nesting.md) (match nesting readability), [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md) (`.` resolution and bare-identifier resolution), [RFC 0006](./0006-option-result-lang-items.md) (compiler-owned carriers as the prelude basis).
