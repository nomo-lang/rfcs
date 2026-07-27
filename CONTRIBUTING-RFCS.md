# Contributing RFCs

Use an RFC for compatibility-affecting language, compiler, Runtime, standard
library, package-management, diagnostic, formatter, LSP, or editor decisions.
Small implementation details that do not change a public contract belong in the
owning code repository.

## Required bilingual shape

Create the English and Chinese files together:

```text
en/rfcs/NNNN-hyphenated-title.md
zh-CN/rfcs/NNNN-hyphenated-title.md
```

Use the next unused four-digit number and update both locale indexes. The two
documents must express the same decision, compatibility policy, diagnostics,
test plan, and evidence even when the prose is not a sentence-by-sentence
translation.

Every RFC includes:

- title and metadata;
- summary, motivation, and current problem;
- detailed syntax and semantics;
- type-checking and ownership rules;
- C99/WASM/Runtime impact as applicable;
- standard-library, formatter, doc, LSP, grammar, and editor impact;
- diagnostics and migration behavior;
- positive and negative examples;
- compatibility window and removal condition;
- test and acceptance plan;
- alternatives, risks, unresolved questions, and final recommendation.

## Two independent statuses

### Decision Status

| Value | Meaning |
| --- | --- |
| `Draft` | The proposal is incomplete and not ready for formal review. |
| `Proposed` | The contract is reviewable but not yet accepted. |
| `Accepted` | The decision passed its evidence gate and is normative. |
| `Rejected` | The proposal was not adopted; rationale remains historical record. |
| `Deferred` | The problem is real but the decision is postponed. |

Typical flow:

```text
Draft -> Proposed -> Accepted
                  -> Rejected
                  -> Deferred
```

### Implementation Status

| Value | Meaning |
| --- | --- |
| `Not implemented` | No conforming implementation has merged. |
| `Partially implemented` | Named slices have merged, with remaining gates stated. |
| `Implemented` | The RFC's declared implementation scope has executable evidence. |

Decision and implementation statuses do not imply one another. A Proposed RFC
may have an experimental or phased implementation. An Accepted RFC may still be
partially implemented. Indexes display both fields.

## RFC-first gate

For a new public contract:

1. merge a bilingual RFC as `Proposed` and `Not implemented`;
2. create downstream implementation branches only after that merge;
3. implement in the owning repositories with tests and protected CI;
4. update SPEC, examples, docs, formatter/LSP/editor surfaces, and compatibility
   gates;
5. use a separate evidence pull request to update implementation status and,
   when all acceptance conditions pass, decision status.

Do not mark work `Accepted` merely because internal tests pass. The relevant
platform, C99/WASM, packaging, editor, documentation, and external-use gates
must be represented honestly.

## Acceptance evidence

An acceptance PR links:

- implementation pull requests and merge commits;
- positive, negative, migration, and compatibility tests;
- protected CI runs for supported platforms;
- C99 and WASM evidence when affected;
- formatter, `nomo doc`, LSP, grammar, and editor evidence when syntax changes;
- updated bilingual SPEC and indexes;
- release/readiness caveats that remain.

Performance claims require reproducible benchmark artifacts and must state
host, toolchain, workload, sample count, and exclusions. A benchmark slice does
not establish production readiness.

## Validation

Run:

```sh
python3 scripts/check_rfc_docs.py
python3 scripts/check_release_set.py
```

Follow [`AGENTS.md`](AGENTS.md) for repository-local automation and delivery
rules. Submit signed commits through a feature branch and pull request; never
commit directly to protected `main`.
