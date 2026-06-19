# RFC NNNN: <Title>

> 语言 / Language: [中文](../zh-CN/0000-template.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | NNNN |
| Title | <one-line title> |
| Status | Draft |
| Author | <author> |
| Created | YYYY-MM-DD |
| Related topics | <e.g. error handling, pattern matching, name resolution> |
| Related RFCs | <e.g. [RFC 0001](./rfcs/0001-example.md), none> |

> Status field values: `Draft` / `Proposed` / `Accepted` / `Rejected` / `Deferred`.
> The meaning of each status is in [`README.md`](./README.md). This template defaults to `Draft`.

---

## 1. Summary

Summarize in 3-5 sentences: what problem this RFC aims to solve, what it leans toward doing, and its impact on v0.1. A reader who reads only this section should still grasp the key points.

---

## 2. Motivation

Why is this matter worth deciding with an RFC? What are the consequences of not addressing it (developer experience, implementation risk, delivery risk, conflict with the design philosophy, etc.)? Reference real usage scenarios, example code, or existing RFCs where possible.

---

## 3. Status and Problem

- **Current design status**: Describe what the current specification, draft implementation, or example code prescribes.
- **Problem analysis**: Point out where the current status is inconsistent, incomplete, too expensive, or in conflict with other design principles.

---

## 4. Detailed Design

For each alternative or the final lean, cover at least the following four dimensions:

- **Syntax**: What changes at the source level; give Nomo-style examples.
- **Semantics**: How behaviors such as type checking, name resolution, evaluation, and exhaustiveness are defined.
- **C backend impact (Codegen)**: The impact on C99 transpilation (structs / tagged unions, runtime functions, symbol mangling, etc.).
- **Diagnostics impact**: New/changed error codes, hints, and fix suggestions.

---

## 5. Alternatives

List 2-3 candidate options one by one, each with: approach, advantages, disadvantages, trade-offs. Include the "keep the status quo" option.

| Option | Approach | Advantages | Disadvantages |
| --- | --- | --- | --- |
| A | … | … | … |
| B | … | … | … |
| C (status quo) | … | … | … |

---

## 6. Drawbacks and Risks

The drawbacks, complexity, migration cost, and potential rollback risks that remain even if the preferred option is adopted.

---

## 7. Impact on v0.1 Scope

State clearly:

- Whether it affects the v0.1 delivery boundary.
- The minimal subset recommended to land in v0.1, and the parts that can be deferred to v0.2+.
- The impact on the acceptance test matrix.

---

## 8. Recommendation (remains Draft, not decided)

Give the currently preferred option and rationale, but keep it as a discussion draft, awaiting a review decision before changing the status.

---

## 9. Open Questions

List the questions this RFC has not yet answered and that need further discussion or handling by a follow-up RFC.

---

## 10. References

- Related RFCs.
- Similar designs in other languages (for comparison only, not as a basis for conclusions).
