# Contributing RFCs

Use RFCs for language, compiler, standard library, tooling, package-management,
or diagnostics decisions that affect compatibility or the v0.1 delivery loop.

## Required Sections

Every RFC must include:

- Title.
- Status.
- Background and motivation.
- Detailed design.
- Syntax examples.
- Type-checking rules.
- C backend impact.
- Standard library impact.
- Diagnostic impact.
- Test plan.
- Compatibility impact.
- Alternatives.
- Unresolved questions.
- Final decision.

## Acceptance Conditions

An RFC should not move to `Accepted` until it has:

- At least one positive example.
- At least one negative example.
- A diagnostic code or diagnostic strategy for key failures.
- A clear C99 backend impact statement.
- A standard library or runtime impact statement when relevant.
- A test plan.
- No contradiction with [Nomo Design Constitution](DESIGN-CONSTITUTION.md).

## Status Flow

```text
Idea
  -> Draft
  -> Review
  -> Accepted
  -> Implementing
  -> Implemented
  -> Stabilized
  -> Rejected / Deferred
```

The language-specific RFC indexes under `zh-CN/` and `en/` remain the source of
truth for numbered RFC files.
