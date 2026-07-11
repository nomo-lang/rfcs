# RFC 0004: The Real Difficulty of Mutable-Borrow Uniqueness Checking

> 语言 / Language: [中文](../../zh-CN/rfcs/0004-mutable-borrow-uniqueness.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0004 |
| Title | What checking strength should mutable-borrow uniqueness achieve in v0.1 |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-06-18 |
| Implementation | Landed: declaration/call-site `mut` pairing, within-call path alias checks, field-prefix conflicts, and immutable-value rejection are covered by tests |
| Related topics | mutable borrow, aliasing check, escape check, diagnostics, C backend |
| Related RFCs | [RFC 0003](./0003-arc-cow-runtime-cost.md) (ARC+COW), [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md) (syntax resolution) |

---

## 1. Summary

This RFC accepts a restricted call-site borrow model: a `mut` borrow is active only for one call expression. The compiler checks declaration/call-site `mut` pairing, immutable-value borrowing, repeated paths, and overlapping field prefixes without introducing regions or lifetimes. Current syntax cannot create a storable or returnable named borrow, so borrows do not escape a call expression.

---

## 2. Motivation

The delivery boundary lists "mutability" checking as a must-deliver type-checking item; the acceptance test matrix requires "Mutability tests: illegal modification, repeated mutable borrows are rejected". That is, "repeated mutable borrows are rejected" is a hard acceptance metric. But the current specification only gives the rule text, without clarifying the checking-algorithm strength. If done too weakly (syntactic layer only), it will miss real aliasing; if done too strongly (regions/lifetimes), it violates the promise of "avoiding exposing Rust's explicit lifetime complexity early", with high slippage risk. The error-code range `E0500-E0599` is already reserved; it needs clarifying which situations these codes specifically cover.

---

## 3. Status and Problem

### 3.1 Current Specification Status

The current mutable-borrow semantics:

- `mut p: Point` is a mutable borrow within the current call stack, not a copy.
- A mutable borrow must not escape the current function.
- Within the same scope a value can have only one active mutable borrow at a time.
- v0.1 does not expose a general raw-reference type, to avoid introducing a full lifetime system.

Call syntax requires `mut` at both ends (declaration `fn move_point(mut p: Point)`, call `move_point(mut pt)`). An early issue list considered changing `mut p: T` to `borrow mut p: T`; this RFC keeps the existing `mut` syntax, and the implementation now provides matching diagnostics and tests.

### 3.2 Problem Analysis

To reject "repeated active mutable borrows", we must at least answer:

1. **Two `mut`s on the same value within one call**: e.g. `swap_fields(mut p, mut p)` or passing the same value via two parameters — the pure syntactic layer cannot recognize "is it the same value", which requires expression/path aliasing determination.
2. **Cross-statement liveness**: "active" means knowing where a mutable borrow starts and where it ends. v0.1 borrows "do not escape" and cannot be stored as references (no raw-reference type), so the borrow lifetime can be approximated as "during the call expression" — this greatly simplifies the problem, but it still requires confirming there is no path to stuff a `mut` borrow into a struct/array/return value.
3. **Escape**: forbid `return mut p`, forbid writing a mutable borrow into longer-lived storage. Since v0.1 has no reference type, the escape surface is in fact very narrow, but this point must be formalized as a checking rule.

The tension: 3.6 wants "a small part of Rust-style aliasing safety" but "not Rust-style lifetimes". This is feasible, but the prerequisite is to strictly limit the mutable borrow's lifetime to "a single call expression", thereby compressing the flow analysis to extremely lightweight.

---

## 4. Detailed Design

### 4.1 Checking-Strength Tiers

- **L0 pure syntactic layer**: only check that the `mut` keyword appears in pairs at the declaration/call ends, with no aliasing analysis.
- **L1 call-site aliasing check (accepted core)**: within a single call expression, perform path-conflict checks on all `mut` arguments, rejecting the same mutable path being passed more than once (e.g. `f(mut p, mut p)`, `f(mut p, mut p.x)` are treated as conflicts).
- **L2 intra-function flow-sensitive**: track the "active interval" of a mutable borrow across a statement sequence, handling cross-statement overlap (only needed if v0.1 allows binding a borrow to a local variable — currently not allowed).
- **L3 regions/lifetimes**: the full lifetime system. The current specification explicitly **does not** do this.

### 4.2 Accepted: L1 + Restricted Path Checking

- **Semantics**: a mutable borrow's active period is defined as "during the evaluation of the call expression that produces it". Since v0.1 has no reference type and cannot store a borrow in a variable/field/array (this itself is guaranteed by the type system — there is no nameable type like `&mut T`), then:
  - Same-frame aliasing conflicts can only occur between **multiple `mut` arguments of the same call** → covered by L1.
  - Escape can only be "treating the borrow as a return value" → directly blocked by "no reference type, `mut p` is not a returnable value type", with an L2-level rule as a backstop diagnostic.
- **C backend**: `mut p: T` degrades to "pass `T*` by pointer" (taking `&pt`). After the check passes, codegen safely passes the address; there is no runtime check.
- **Diagnostics** (`E0500-E0599`):
  - `E0501` the same value is mutably borrowed more than once (within one call).
  - `E0502` a mutable borrow escapes the current function (e.g. attempting to return it).
  - `E0503` the call site is missing the `mut` marker / the declaration and call sites' `mut` are inconsistent.
  - `E0510` initiating a mutable borrow on an immutable binding (`let` without `mut`).

### 4.3 The Relationship with Value Semantics/COW

L1's compile-time uniqueness lets `Array.push(mut self)` safely modify in place when "the borrow is unique"; but since value semantics still allows another place to hold a read-only copy of the same underlying storage (read sharing), the runtime still needs a refcount + COW backstop (see [RFC 0003](./0003-arc-cow-runtime-cost.md)). That is: **compile-time unique ≠ runtime exclusive ownership of the underlying storage** — the two solve different aliasing layers; v0.1 needs both, and the boundary must be locked down between [RFC 0003](./0003-arc-cow-runtime-cost.md) and this RFC.

---

## 5. Alternatives

| Option | Approach | Advantages | Disadvantages |
| --- | --- | --- | --- |
| L0 pure syntactic | Only check `mut` pairing | Easiest to implement | Misses `f(mut p, mut p)`, fails acceptance |
| L1 + restricted path checking (accepted) | Call-site aliasing; syntax prevents named-borrow escape | Meets acceptance, controllable cost, no lifetimes needed | Needs path-aliasing determination (medium complexity) |
| L3 regions/lifetimes | Full borrow checking | Strongest guarantee | Violates the 3.6 promise, severe slippage |

---

## 6. Drawbacks and Risks

- "Path-aliasing determination" requires canonicalized comparison of lvalue paths (`p`, `p.x`, `items` vs some element of `items`); for subscript paths such as `Array` elements, v0.1 can conservatively treat "any two mutable borrows of the same array" as a conflict, avoiding subscript-aliasing analysis.
- If binding a mutable borrow to a local variable (named borrow) is allowed in the future, L1 is immediately insufficient and must be upgraded to true L2 active-interval analysis — this is a potential rework point and should be stated in the documentation as "v0.1 does not support named mutable borrows".
- Reintroducing a `borrow` keyword later requires a new RFC and synchronized diagnostics, formatter, LSP, and examples; it is not part of the current v0.1 decision.

---

## 7. Impact on v0.1 Scope

- **Landed in v0.1**: L1 call-site aliasing plus restricted path-conflict rules, with `E0501-E0511` diagnostics; no region/lifetime implementation.
- **Explicitly not doing**: named mutable borrows, storing a borrow in a struct/array, cross-function borrows.
- **Acceptance impact**: the acceptance test matrix's "Mutability tests" need to cover: `f(mut p, mut p)` is rejected, initiating `mut` on a `let` (non-mut) is rejected, missing the call-side `mut` is rejected, and (restricted) escape is rejected.

---

## 8. Decision

Accept **L1 + restricted path checking**: a mutable borrow is active for exactly one call expression; repeated root paths and prefix overlaps such as `p`/`p.x` are rejected. v0.1 keeps the `fn f(mut p: T)` / `f(mut value)` syntax and does not introduce a `borrow` keyword, named borrows, or a lifetime/region system.

---

## 9. Follow-up Questions

- The details of the canonicalization rules for lvalue-path aliasing (does a field-path prefix overlap count as a conflict, e.g. `p` vs `p.x`).
- Whether array elements are worth more fine-grained subscript-aliasing analysis, or should be handled conservatively in the long term.
- If indexed lvalues or named borrows are introduced later, a separate RFC must extend the current call-site model.

---

## 10. References

- The current mutable-borrow parameters, error-code range (E0500-E0599), compiler pipeline and IR, examples, and tests.
- [RFC 0003](./0003-arc-cow-runtime-cost.md) (the boundary between compile-time uniqueness and runtime COW), [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md) (`mut`/`.` syntax resolution).
