# Nomo RFCs

This repository is the bilingual decision and specification record for the
[Nomo programming language](https://github.com/nomo-lang/nomo). It owns RFC
governance, the English and Chinese specification baseline, preview release
gates, versioning policy, and the non-normative architecture overview.

本仓库是 Nomo 编程语言的双语决策与规格记录，负责 RFC 治理、中英文 SPEC 基线、
Preview 发布门禁、版本政策与非规范架构总览。

## Status / 状态

Nomo is in **Preview**. There is no stable `v0.1.0` release. Timestamped
snapshots are evaluation artifacts and may contain breaking changes.

The most recent recorded release set is
[`v0.0.0-20260721120555`](releases/v0.0.0-20260721120555/RELEASE.md).
Current documentation is newer and was reviewed against:

- `nomo` [`085da513`](https://github.com/nomo-lang/nomo/commit/085da513ff6c042bd00571c49a6eb061722acf6f)
- `nomo-lsp` [`f855514`](https://github.com/nomo-lang/nomo-lsp/commit/f8555148617efbc3b21fabd75f94773c3bccd959)

Do not treat an RFC's decision status, a passing internal test, or a benchmark
slice as a production-readiness claim. Read
[`RELEASE-GATE.md`](RELEASE-GATE.md) for the remaining gates.

## Start here / 从这里开始

| Need | Source of truth |
| --- | --- |
| English language and toolchain contract | [`en/SPEC-v0.1.md`](en/SPEC-v0.1.md) |
| 中文语言与工具链契约 | [`zh-CN/SPEC-v0.1.md`](zh-CN/SPEC-v0.1.md) |
| English RFC process and index | [`en/README.md`](en/README.md) |
| 中文 RFC 流程与索引 | [`zh-CN/README.md`](zh-CN/README.md) |
| Non-normative vision / 非规范愿景 | [`WHITEPAPER-v0.1.md`](WHITEPAPER-v0.1.md) |
| Current delivery sequence | [`ROADMAP.md`](ROADMAP.md) |
| Preview acceptance evidence | [`RELEASE-GATE.md`](RELEASE-GATE.md) |
| Snapshot compatibility policy | [`VERSIONING.md`](VERSIONING.md) |
| Design constraints | [`DESIGN-CONSTITUTION.md`](DESIGN-CONSTITUTION.md) |
| Submit or update an RFC | [`CONTRIBUTING-RFCS.md`](CONTRIBUTING-RFCS.md) |

The initial June 18 whitepaper is preserved only as historical material:
[`archive/initial-whitepaper-2026-06-18.zh-CN.md`](archive/initial-whitepaper-2026-06-18.zh-CN.md).

## Syntax quick start / 语法快速验证

The documentation gate compiles this canonical project snippet with the pinned
`nomo` revision:

<!-- nomo-check: package=hello-world -->
```nomo
package hello_world

import std.io

fn main() {
    io.println("Hello, Nomo")
}
```

The manifest name `hello-world` becomes source root `hello_world`; the entry
does not append `.main`, and the void-return declaration omits `-> void`.

## Governance model / 治理模型

Every RFC has two independent metadata fields:

- **Decision Status**: `Draft`, `Proposed`, `Accepted`, `Rejected`, or
  `Deferred`.
- **Implementation Status**: `Not implemented`, `Partially implemented`, or
  `Implemented`.

`Accepted` means the design decision passed its evidence gate; it does not mean
the implementation is complete. `Implemented` means executable evidence exists;
it does not by itself accept the design. A change to syntax, semantics,
diagnostics, standard library, Runtime, package model, or shared tooling lands
as a bilingual Proposed RFC before implementation begins.

每篇 RFC 独立记录决策状态与实现状态。`Accepted` 不自动等于已实现，`Implemented`
也不自动把决策提升为 Accepted。语法、语义、诊断、标准库、Runtime、包模型或共享
工具链变更必须先合并双语 Proposed RFC。

## Verified repository checks

Run from this repository:

```sh
python3 scripts/check_rfc_docs.py
python3 scripts/check_nomo_snippets.py --nomo ../nomo/target/release/nomo
```

The checks verify:

- exact English/Chinese RFC inventory parity;
- metadata and index coverage;
- local Markdown links;
- canonical Nomo snippets against the reviewed compiler.

Code snippets and implementation claims must additionally be checked against the
pinned compiler/runtime commit and protected CI in the owning repository.

When preparing one coordinated release checkout, also run:

```sh
python3 scripts/check_release_set.py --workspace .. --require-clean
```

This release-set command is expected to reject a workspace whose repositories
are intentionally on different Preview snapshots; it is not a general docs
lint command.

## Repository boundary / 仓库边界

This repository does not own compiler behavior, Runtime code, editor binaries,
Playground deployment, or website deployment. Those live in their respective
repositories. RFC evidence links to those implementations; it does not copy
their source or replace their release gates.

Generated Paraglide/Inlang localization READMEs are not maintained here and
must not be hand-edited as part of RFC governance.

## Contribution rules

- Keep English and Chinese RFCs in sync in the same pull request.
- Update both locale indexes whenever RFC metadata or inventory changes.
- Keep unfinished decisions `Proposed`.
- Move a decision to `Accepted` only with code, tests, protected CI, and the
  relevant specification/editor/ecosystem evidence.
- Use signed commits, a feature branch, pull request, required CI, and merge;
  never commit directly to protected `main`.

See [`AGENTS.md`](AGENTS.md) for repository-local automation rules and
[`CONTRIBUTING-RFCS.md`](CONTRIBUTING-RFCS.md) for the human RFC process.
