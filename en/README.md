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
| `Draft` | Draft. The problem has taken shape and alternatives are listed, but no decision has been made yet. |
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
| [0001](./rfcs/0001-error-propagation-and-conversion.md) | The experience tension between `?` propagation and the lack of automatic error conversion | Accepted | error handling, `Result`, `?` propagation, C backend | v0.1 uses explicit `std.result.map_err(named_converter)?`; `From`-style automatic conversion is deferred. |
| [0002](./rfcs/0002-match-wildcard-and-nesting.md) | `match` lacks the `_` wildcard arm and nested destructuring | Accepted | pattern matching, exhaustiveness, nested destructuring | `match` keeps `_` disabled; `let else`, `if let`, and Option `?` are implemented to flatten nested boilerplate. |
| [0003](./rfcs/0003-arc-cow-runtime-cost.md) | The runtime implementation cost of value semantics + ARC + COW | Accepted | memory model, `string`, `Array<T>`, runtime | `string` uses immutable non-atomic RC; `Array<T>` uses non-atomic RC+COW with lifecycle and write-separation tests. |
| [0004](./rfcs/0004-mutable-borrow-uniqueness.md) | The real difficulty of mutable-borrow uniqueness checking | Accepted | mutable borrow, aliasing check, escape check | Borrows live for one call expression with call-site path-conflict checks and no lifetimes or named borrows. |
| [0005](./rfcs/0005-newline-sensitivity-and-dot-resolution.md) | Significant-newline separation and `.` namespace resolution | Accepted | lexical syntax, newline rules, name resolution, `.` resolution | Significant newlines and continuation anchors are implemented; dot chains resolve by value/module/type and checked receiver ownership. |
| [0006](./rfcs/0006-option-result-lang-items.md) | The circular dependency between `Option`/`Result` and the compiler's built-in awareness | Accepted | lang item, `Option`, `Result`, standard library boundary | Accept compiler-owned carrier identities plus `std.option`/`std.result` module contracts; v0.1 does not use a `#[lang]` attribute. |
| [0007](./rfcs/0007-unqualified-variant-access.md) | Whether `Enum.Variant` can be simplified to an unqualified `Variant` | Accepted | enum variants, prelude, name resolution, ergonomics | Only core `Some/None/Ok/Err` may be unqualified; local names win, user enums stay qualified, and qualified core forms remain compatible. |
| [0008](./rfcs/0008-canonical-package-identity-and-aliases.md) | Separating canonical package identity from dependency aliases | Accepted | package identity, manifest, import | Canonical id is `owner/package`; aliases only control local imports and sources are not language identity. |
| [0009](./rfcs/0009-reproducible-workspace-and-package-graphs.md) | Reproducible Workspace, Package, and Module graphs | Accepted | workspace, dependency graph, lockfile | Use three typed graph layers, stable dependency order, a workspace-root lockfile, checksums, and locked/offline/vendor contracts. |
| [0010](./rfcs/0010-constrained-generics-and-static-interface-dispatch.md) | Constrained generics and static interface dispatch | Accepted | interface, generics, monomorphization | At most one interface bound per type parameter, explicit concrete type arguments, monomorphized static dispatch. |
| [0011](./rfcs/0011-c-ffi-safety-and-link-boundary.md) | The safety, ownership, and link boundary of C FFI | Accepted | FFI, unsafe, CString, Opaque | Extern calls require call-site `unsafe`, explicit CString/Opaque, and manifest linker metadata. |
| [0012](./rfcs/0012-shared-semantic-identities-and-verified-rename.md) | Shared semantic identities and type-checked rename | Accepted | semantic API, LSP, rename | The compiler owns semantic facts; references use declaration/receiver identity and rename edits must type-check. |
| [0013](./rfcs/0013-registry-protocol-and-package-integrity.md) | Registry protocol, authentication, and package integrity | Accepted | registry, metadata, checksum, auth | Exact-version `/api/v1`, deterministic archives, two checksum layers, yank, bearer tokens, and verified HTTPS. |
| [0014](./rfcs/0014-semver-resolution-and-conflict-explanations.md) | Semantic version resolution and conflict explanations | Accepted | semver, resolver, lockfile | Deterministic project/workspace single-version solving, exact locks, offline index caching, and traceable minimal conflicts are implemented. |
| [0015](./rfcs/0015-source-defined-standard-library-and-intrinsics.md) | Source-defined standard library and controlled intrinsic identities | Accepted | standard library, intrinsic, bootstrap | Canonical Nomo sources define the public standard-library surface while a toolchain manifest constrains representation-sensitive intrinsics. |
| [0016](./rfcs/0016-incremental-semantic-graph-and-cache.md) | Incremental semantic graph and persistent cache | Proposed | incremental compilation, LSP, cache | A compiler-owned query graph provides verified invalidation and persistent caching to CLI and LSP. |
| [0017](./rfcs/0017-target-triples-and-cross-compilation.md) | Target triples, conditional dependencies, and cross compilation | Proposed | target, cross compilation, linker | Unify target context across resolution, ABI, standard-library selection, and linking. |
| [0018](./rfcs/0018-package-signing-provenance-and-transparency.md) | Package signing, provenance, and transparency | Accepted | signing, provenance, registry | Ed25519 publisher authorization, provenance, pinned transparency keys, inclusion proofs, rollback detection, and lockfile evidence are implemented. |
| [0019](./rfcs/0019-typed-ffi-handles-callbacks-and-bindings.md) | Typed FFI handles, callbacks, and bindings | Accepted | FFI, callback, C ABI | Nominal handles, explicit nullability/ownership, restricted callbacks, target-checked C layout, and deterministic bindings are implemented. |

> Note: `0000-template.md` is the template and is not counted in the table above.
