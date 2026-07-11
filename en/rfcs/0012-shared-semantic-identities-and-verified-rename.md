# RFC 0012: Shared Semantic Identities and Type-Checked Rename

> 语言 / Language: [中文](../../zh-CN/rfcs/0012-shared-semantic-identities-and-verified-rename.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0012 |
| Title | Shared semantic identities and type-checked rename |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Landed: compiler semantic APIs, declaration-aware references, receiver/member ownership, workspace references, dependency definitions, and post-edit rename checking have compiler/LSP tests |
| Related topics | semantic API, LSP, definition, references, rename, receiver type |
| Related RFCs | [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md), [RFC 0010](./0010-constrained-generics-and-static-interface-dispatch.md) |

---

## 1. Summary

Editors must not reimplement Nomo name resolution. Definition, references, hover, and rename use the compiler semantic API and identify symbols by declaration source, range, symbol kind, and member owner. Rename applies edits in memory and type-checks the resulting module graph before returning them.

## 2. Motivation

Textual same-name matching crosses shadows, receiver types, interface owners, and package boundaries incorrectly. If VS Code, Zed, IntelliJ, and the LSP each guess separately, tooling behavior diverges from the compiler.

## 3. Declaration Identity

- Parameters, `let`, pattern, and `for` bindings resolve through lexical scope.
- Fields, struct literal labels, and methods resolve through the receiver's checked nominal type.
- Same-named members on different types have distinct owners; a constrained generic method belongs to its declaring interface.
- Public dependency symbols may be definition targets; private symbols remain invisible.

## 4. References and Rename

- Project/workspace reference queries key on declaration identity, not text alone.
- Open-buffer overlays participate so unsaved source does not fall back to stale disk state.
- Rename edits only the current editable package/module graph and does not rewrite dependency source.
- If the original program checks, the overlay graph with proposed edits must check again or rename is rejected.

## 5. Alternatives

| Option | Problem | Decision |
| --- | --- | --- |
| Client regex/lexical matching | Wrong across shadows and member owners | Rejected |
| LSP-specific semantic model | Duplicates and drifts from the compiler | Rejected |
| Shared compiler semantic API | Single source of truth and reusable type facts | Accepted |

## 6. Drawbacks and Risks

- The semantic API becomes a cross-crate and cross-repository compatibility surface.
- Workspace queries need caching and incrementalization.
- Post-edit graph checking is more expensive than textual rename but prioritizes correctness.

## 7. Impact on v0.1 Scope

LSP completion, hover, symbols, definition, references, rename, code actions, semantic tokens, and inlay hints should reuse compiler facts. E1300-E1399 is reserved for semantic/LSP diagnostics.

## 8. Decision

Accept compiler-owned declaration identity, receiver-aware member owners, workspace semantic queries, and type-checked rename.

## 9. Follow-up Questions

- Incremental semantic graphs and cross-workspace caches.
- Explicit opt-in protocols for dependency rename.
- Cross-package move/refactor and stable source-map identity.

## 10. References

- `nomo_lsp_bridge` semantic types, compiler semantic APIs, receiver-aware navigation, and workspace reference tests.
- [RFC 0010](./0010-constrained-generics-and-static-interface-dispatch.md).
