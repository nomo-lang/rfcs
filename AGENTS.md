# RFC Repository Instructions

## Scope

This repository owns bilingual RFCs, the English and Chinese v0.1
specifications, the roadmap, preview release/versioning gates, and the
non-normative whitepaper. It does not own compiler, Runtime, LSP, editor,
Playground, or website implementation.

## Before writing

1. Confirm the repository is on clean, synchronized `main`.
2. Confirm no active task is writing this checkout.
3. For a language or ecosystem change, merge the bilingual Proposed RFC before
   creating implementation branches in downstream repositories.
4. Work on an independent feature branch. Do not stash, overwrite, or commit
   another task's files.

## Bilingual and status rules

- `en/rfcs` and `zh-CN/rfcs` must have identical numbered inventories and
  matching design decisions.
- Update both locale indexes in the same pull request.
- Keep **Decision Status** independent from **Implementation Status**.
- `Accepted` requires linked implementation, tests, protected CI, and all
  applicable compiler/Runtime/LSP/editor/ecosystem evidence.
- Partial slices remain explicit; they do not justify a broad “implemented” or
  production-ready claim.
- Keep unfinished designs `Proposed`. Never use documentation edits to claim
  work that cannot be located in code and CI.

## Sources of truth

Use this order when resolving drift:

1. executable compiler/Runtime behavior and protected CI;
2. accepted RFC decisions;
3. bilingual SPEC text;
4. release/versioning gates;
5. roadmap and repository READMEs;
6. the non-normative whitepaper.

If code and an accepted RFC disagree, report the contradiction and correct it
through the RFC process; do not silently rewrite semantics.

## Cross-document consistency

Every accepted or implemented change must be checked against:

- both locale RFC files and indexes;
- `en/SPEC-v0.1.md` and `zh-CN/SPEC-v0.1.md`;
- `ROADMAP.md`, `RELEASE-GATE.md`, and `VERSIONING.md`;
- `WHITEPAPER-v0.1.md` when the architecture overview is affected;
- `DESIGN-CONSTITUTION.md` only when a design invariant needs calibration.

The whitepaper is orientation only and must not duplicate complete grammar,
standard-library APIs, or an RFC status table.

## Verification and delivery

Run:

```sh
python3 scripts/check_rfc_docs.py
python3 scripts/check_release_set.py
```

Also compile changed Nomo snippets with the reviewed compiler revision whenever
they are intended to be executable.

Use signed commits, a pull request, required CI, and merge. After merging,
return the repository to clean synchronized `main`. Status promotions belong in
a separate evidence PR when the RFC-first delivery plan requires one.
