# Nomo RFC Process

> 语言 / Language: [中文](../zh-CN/README.md) | English

This directory collects the RFCs (Requests for Comments) for the Nomo programming language. RFCs are used for public discussion and record-keeping of **language, compiler, standard library, and toolchain issues that require formal decisions**.

An RFC document should be self-contained: it states the current design status, the problem, alternatives, the preferred recommendation, and the impact on the v0.1 delivery scope. RFCs may reference one another, but they do not depend on any other explanatory document as their index entry point.

---

## 1. Specification Baseline

The current v0.1 specification baseline is in [`SPEC-v0.1.md`](SPEC-v0.1.md). It describes the language, standard library, compiler, and acceptance scope that RFC discussions are based on.

The responsibility of an RFC is to discuss and amend the pending issues in this specification baseline; once an RFC is `Accepted`, the specification baseline and the implementation should be updated accordingly.

---

## 2. Status Field Definitions

Every RFC marks a `Status` field in its metadata, with the following possible values:

| Status | Meaning |
| --- | --- |
| `Draft` | Draft. The problem has taken shape and alternatives are listed, but no decision has been made yet. All RFCs currently in this directory are in this state. |
| `Proposed` | The draft is complete and has entered formal review, awaiting acceptance or rejection. |
| `Accepted` | Adopted; the language specification and implementation should be updated accordingly. |
| `Rejected` | Not adopted after discussion; the record and rationale are kept. |
| `Deferred` | The direction is endorsed, but the work is deferred to a later version (e.g. v0.2+). |

The typical status transition path: `Draft → Proposed → Accepted / Rejected / Deferred`.

---

## 3. Numbering Rules

- RFC file name format: `NNNN-hyphenated-english-title.md`, where `NNNN` is a four-digit zero-padded number.
- Numbers increment sequentially from `0001` and are never reused once assigned (even if `Rejected`).
- `0000-template.md` is the template, not an actual RFC.
- A new RFC takes the current maximum number + 1.

---

## 4. Submission Process

1. Copy [`0000-template.md`](0000-template.md) to `rfcs/NNNN-your-title.md` and fill in all sections.
2. Mark the related topics in the metadata, and reference relevant RFCs with Markdown links.
3. Set the initial status to `Draft`.
4. Register the RFC in the "Directory Index" table in Section 6 of this README (keep the table consistent with the actual files).
5. After entering review, update the `Status` field per the transitions in Section 2.
6. Once an RFC is `Accepted`, the corresponding updates to the language specification and implementation should be initiated.

> Constraint: this directory only holds RFC-related markdown files; do not modify other directories.

---

## 5. Template

See [`0000-template.md`](0000-template.md). The template includes: metadata (number, title, status, author, creation date, related topics, related RFCs), summary, motivation, status and problem, detailed design (syntax / semantics / C backend impact / diagnostics impact), alternatives, drawbacks and risks, impact on v0.1 scope, open questions, and references.

---

## 6. Directory Index

| Number | Title | Status | Related Topics | One-line conclusion / lean |
| --- | --- | --- | --- | --- |
| [0001](./rfcs/0001-error-propagation-and-conversion.md) | The experience tension between `?` propagation and the lack of automatic error conversion | Draft | error handling, `Result`, `?` propagation, C backend | Lean toward providing an explicit `std.result.map_err` in v0.1 first (making `?` usable), and leaving `From`-style automatic conversion for v0.2. |
| [0002](./rfcs/0002-match-wildcard-and-nesting.md) | `match` lacks the `_` wildcard arm and nested destructuring | Draft | pattern matching, exhaustiveness, nested destructuring | Lean toward keeping `_` disabled in `match` (to preserve exhaustiveness), and using `let else` / `if let` to flatten nested boilerplate. |
| [0003](./rfcs/0003-arc-cow-runtime-cost.md) | The runtime implementation cost of value semantics + ARC + COW | Draft | memory model, `string`, `Array<T>`, runtime | Lean toward "divide and conquer": `string` is reference-counted only (immutable, COW-free), `Array<T>` uses non-atomic RC + COW, with pure copying as an emergency fallback. |
| [0004](./rfcs/0004-mutable-borrow-uniqueness.md) | The real difficulty of mutable-borrow uniqueness checking | Draft | mutable borrow, aliasing check, escape check | Lean toward limiting the borrow's lifetime to "a single call expression", doing call-site aliasing + escape backstop (L1), without introducing lifetimes. |
| [0005](./rfcs/0005-newline-sensitivity-and-dot-resolution.md) | Significant-newline separation and `.` namespace resolution | Draft | lexical syntax, newline rules, name resolution, `.` resolution | Lean toward significant newlines + explicit continuation anchors; `.` is unified as postfix dot access, dispatched by name resolution as "value / module / type". |
| [0006](./rfcs/0006-option-result-lang-items.md) | The circular dependency between `Option`/`Result` and the compiler's built-in awareness | Draft | lang item, `Option`, `Result`, standard library boundary | Lean toward making `Option`/`Result` lang items: the definitions stay in the standard library, and the compiler recognizes them via the `#[lang]` attribute. |
| [0007](./rfcs/0007-unqualified-variant-access.md) | Whether `Enum.Variant` can be simplified to an unqualified `Variant` | Draft | enum variants, prelude, name resolution, ergonomics | Lean toward allowing unqualified form only for the prelude `Option`/`Result` variants (`Some/None/Ok/Err`), keeping all other enums qualified. |

> Note: `0000-template.md` is the template and is not counted in the table above.
