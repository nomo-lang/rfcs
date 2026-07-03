# RFC 0005: Newline-Sensitive Syntax and `.` Namespace Resolution

> 语言 / Language: [中文](../../zh-CN/rfcs/0005-newline-sensitivity-and-dot-resolution.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0005 |
| Title | Significant-newline separation and the polysemy-resolution rules of `.` |
| Status | Draft |
| Author | Nomo Language Working Group |
| Created | 2026-06-18 |
| Related topics | lexical syntax, significant newlines, dot access, name resolution, module path |
| Related RFCs | [RFC 0006](./0006-option-result-lang-items.md) (lang items), [RFC 0007](./0007-unqualified-variant-access.md) (simplified variant access) |

---

## 1. Summary

There is no comma or semicolon between the current struct-field and enum-variant syntax; they rely on newlines for separation, meaning Nomo is a **newline-sensitive** language. But the keyword/grammar rules only list keywords and do not define newline/separation rules, so the parser implementation lacks a basis. Meanwhile `.` simultaneously carries three semantics: module path (`std.io`), variant access (`Result.Ok`), and field/method access (`self.email`, `items.get`); name resolution needs explicit resolution rules. This RFC proposes writing the newline rules and the `.` resolution rules into the specification, leaning toward "significant newlines as the statement/member separator + explicit continuation rules" and "`.` unified as postfix dot access, dispatched by name resolution based on the kind of the left-hand entity", remaining Draft.

---

## 2. Motivation

All examples in the current specification rely on the layout of "one field per line / one variant per line / one statement per line", yet no section defines:

- When a newline is a "separator", and when continuation is allowed (e.g. long expressions, `match` arms).
- Whether a `match` arm `Pattern => Expr` is also separated by newlines (the examples are so, but not stated explicitly).
- How `.` is distinguished among `std.result.Result` (module path + type), `Result.Ok` (type + variant), `self.email` (value + field), and `items.get(i)` (value + method).

Without these rules, the Lexer/Parser cannot be implemented stably, and the lexical/syntax error codes (E0100-E0299) cannot give consistent diagnostics for "missing separator" and "illegal continuation". This directly threatens the "Lexer/Parser golden tests stable" acceptance.

---

## 3. Status and Problem

### 3.1 Current Specification Status

Struct fields have no separator:

```rust
pub struct User {
    pub id: string
    email: string
}
```

Enum variants have no separator:

```rust
pub enum Color {
    Red
    Green
    Blue
}
```

`match` arms have no separator, with one `Pattern => Expr` per line. The multiple uses of `.` are scattered throughout: `std.io`, `std.result.Result`, `Result.Ok(text)`, `self.email`, `items.get(i)`, `fs.read_to_string(path)`.

The keyword/grammar rules only give keywords/reserved words/literals, with **no** provisions for newlines, indentation, separators, or continuation.

### 3.2 Problem Analysis

1. **Newline semantics undefined**: is it "newline is a separator" (like Go/Swift automatic semicolons) or "indentation-sensitive" (like Python)? The examples look like the former, but the continuation rules for long expressions, chained calls `a\n.b()\n.c()`, and multi-arm `match` are missing.
2. **`.` polysemy**:
   - In `A.B`, `A` may be a module (`std`), a module alias (`fs`), a type/enum (`Result`), or a value/variable (`self`, `items`).
   - `std.result.Result` is "module.module.type"; `Result.Ok` is "enum.variant"; both are dot chains, distinguished by name resolution.
   - Strongly related to [RFC 0007](./0007-unqualified-variant-access.md): if unqualified variants (`Ok` instead of `Result.Ok`) are introduced, the semantic determination of the left side of `.` will change; this RFC first fixes the resolution rules for the qualified form.
3. **Ambiguous example**: `a.b.c` could be "member c of module b of module a", "field c of field b of value a", "type a...". Layered parsing is needed: first determine the kind of the leftmost identifier by the in-scope binding/import, then advance segment by segment.

---

## 4. Detailed Design

### 4.1 Newline Rules (preferred)

- **Significant newlines**: the newline character is the default "statement/member separator". Struct fields, enum variants, `match` arms, and statement sequences are all separated by newlines, not commas/semicolons.
- **Explicit continuation**: when a line is syntactically "clearly unfinished", it continues automatically; the determination anchors include:
  - The line ends with a binary operator, `=>`, `,` (within a parameter list), or an unclosed opening bracket `(`/`{`/`<`.
  - The next line starts with `.` (chained calls: `items\n  .get(i)`).
- **Block layout**: inside `{ ... }`, members are separated by newlines; blank lines are ignored.
- **Diagnostics** (E0100-E0199 / E0200-E0299):
  - `E0120` two members/statements appear on the same line without a separator (e.g. two fields written on one line).
  - `E0220` illegal continuation / a newline separator was expected but excess tokens were found.
- **Alternative**: explicit separators (mandatory commas/semicolons). Easier to parse, friendlier to tooling, but conflicts with the current example layout, requires rewriting all examples, and is more verbose relative to the "restrained" temperament. Lean toward significant newlines to keep the existing examples unchanged.

### 4.2 `.` Resolution Rules (preferred: unified postfix dot + name-resolution dispatch)

Unify `.` as a "postfix dot-access expression", with no syntactic distinction of purpose; the distinction is handed to **name resolution**, dispatching by the binding kind of the leftmost identifier:

1. When parsing `Head.Seg1.Seg2...`, first resolve `Head`:
   - If `Head` is a **value binding** in the current scope (variable, `self`, parameter) → subsequent `.Seg` is interpreted in turn as **field access** or **method call**.
   - If `Head` is an **imported module/module alias** → greedily consume consecutive "module" segments until a non-module item (type/function/constant) is encountered, after which it turns into member access.
   - If `Head` is a **type/enum name** → `.Seg` is interpreted as a **variant** or **associated function/constructor** (e.g. `Array.new`, `Result.Ok`).
2. Ambiguity resolution: a value binding has higher priority than a same-named type (to avoid a variable being mistaken for a type); a module path is enabled only when `Head` comes from an `import`.
3. **Diagnostics** (E0300-E0399 name resolution):
   - `E0320` the identifier to the left of `.` is unresolved (neither a binding nor an imported module/type).
   - `E0321` accessing a non-existent field/method on a value.
   - `E0322` accessing a non-existent variant on an enum.

- **C backend**: after resolution, the three kinds of dot access are lowered respectively to: struct member read (`v.field`), function call (`Pkg_func(...)`, mangled by package path per 12.3), and variant construction/tag determination (per the `Result_T_E` of 4.4). The polysemy of `.` is already eliminated in the HIR stage; the C IR has no ambiguity.

### 4.3 Connection with [RFC 0007](./0007-unqualified-variant-access.md)

This RFC fixes the resolution of the **qualified form** (`Enum.Variant`); if [RFC 0007](./0007-unqualified-variant-access.md) decides to introduce prelude/imported unqualified variants (`Ok`/`None`), name resolution needs to add a lookup path for "a bare identifier may be a variant" — this will be extended on top of this rule by [RFC 0007](./0007-unqualified-variant-access.md), not expanded here.

---

## 5. Alternatives

| Dimension | Option | Advantages | Disadvantages |
| --- | --- | --- | --- |
| Separation | Significant newlines (preferred) | Keeps existing examples, restrained style | Parser needs continuation rules, demanding on auto-formatting |
| Separation | Explicit commas/semicolons | Simplest to parse, no ambiguity | Rewrites all examples, more verbose |
| `.` | Unified postfix dot + name-resolution dispatch (preferred) | Simple syntax, consistent with existing style | Parsing depends on name-resolution info, needs priority definition |
| `.` | A different symbol for module paths (e.g. `::`) | Module paths distinguishable at the lexical level | Introduces a new symbol, deviates from the current unified `.` style |

---

## 6. Drawbacks and Risks

- Significant newlines + continuation rules place demands on the **auto-formatter** and AI generation: incorrect newlines change semantics, so diagnostics need to give clear fix suggestions (fitting 2.2).
- Unified postfix dot means the parser produces an "unresolved dot chain", which can only be settled at the name-resolution stage, increasing the AST→HIR processing load; but in exchange there is syntactic-level simplicity and example consistency.
- Although the `::` option can distinguish module paths at the lexical level, it would invalidate all current `std.io`/`Result.Ok` styles, at too high a cost.

---

## 7. Impact on v0.1 Scope

- **Recommended to land in v0.1**: formally write "significant newlines + continuation anchors" and "`.` unified postfix dot + name-resolution dispatch" into the specification (recommended to add to the keyword/grammar rules and the name-resolution details of the compiler architecture).
- **Acceptance impact**: the Lexer/Parser golden tests in the acceptance test matrix must cover: multiple members on one line are rejected, chained continuation is accepted, and each of the three resolution paths of `A.B.C` has a case.
- It does not affect the delivery boundary, but **is a prerequisite for whether the Lexer/Parser can be implemented stably**, with high priority.

---

## 8. Recommendation (remains Draft, not decided)

Lean toward: **significant newlines** as the member/statement separator with defined explicit continuation anchors; **`.` unified as postfix dot access**, dispatched by name resolution into the three kinds of left-hand entity "value / module / type", with value bindings prioritized. This option keeps all current existing examples unchanged while giving the parser and name resolution an implementable basis. Remains Draft.

---

## 9. Open Questions

- The complete list of continuation anchors (whether a leading binary operator continuation is allowed, e.g. the next line starts with `+`).
- Whether the newline rules for a `match` arm body as a block `{ ... }` and for a single-expression arm are unified.
- How to order the name-resolution priority conflict after [RFC 0007](./0007-unqualified-variant-access.md) introduces unqualified variants.

---

## 10. References

- The current file and module design, struct and enum syntax, `Result` usage, keyword/grammar rules, name-resolution pipeline, file-reading and array-swap examples.
- [RFC 0006](./0006-option-result-lang-items.md) (the impact of lang items on name resolution), [RFC 0007](./0007-unqualified-variant-access.md) (simplified variant access).
