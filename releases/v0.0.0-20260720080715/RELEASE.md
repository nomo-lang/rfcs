# Nomo Preview Snapshot v0.0.0-20260720080715

## Decision

This release set is approved as an installable **development snapshot** and
published as a GitHub prerelease. It is not a stable release and does not carry
the stable compatibility promise.

The coordinated release-set check passed with clean worktrees at the revisions
in [`release-set.json`](./release-set.json). Every release change was made on a
child branch and merged through a pull request. The seven release-change
commits and seven annotated tags verified successfully for
`fzpying@gmail.com` with ED25519 key fingerprint
`SHA256:7OSLQL33MshZ64YXwZ1RMmRnkMJQBcKB7EDBxAimnb4`.

## Release set

| Component | Main revision / signed release commit | Pull request | Release workflow | Prerelease |
| --- | --- | --- | --- | --- |
| Nomo compiler and standard library | `6c064e68ed3da437ffe16ba39ae7317b768b0fd3` / `a612aae23ac53d28a981c092740c9a1d5623d507` | [nomo#5](https://github.com/nomo-lang/nomo/pull/5) | [run 29729299649](https://github.com/nomo-lang/nomo/actions/runs/29729299649) | [release](https://github.com/nomo-lang/nomo/releases/tag/v0.0.0-20260720080715) |
| Nomo LSP | `7933b1073210997f62048f3bdf63925154969f95` / `406ef74f8986517f0fccb9cf863a2b0aaf299b9f` | [nomo-lsp#1](https://github.com/nomo-lang/nomo-lsp/pull/1) | [run 29729299457](https://github.com/nomo-lang/nomo-lsp/actions/runs/29729299457) | [release](https://github.com/nomo-lang/nomo-lsp/releases/tag/v0.0.0-20260720080715) |
| Tree-sitter grammar | `42a861683e838ffa6b2f290d02e465a0df37fecb` / `1b2845b322367c9dcb14faa84652359ac3aa74ee` | [tree-sitter-nomo#1](https://github.com/nomo-lang/tree-sitter-nomo/pull/1) | [CI 29728473880](https://github.com/nomo-lang/tree-sitter-nomo/actions/runs/29728473880), [release 29729299721](https://github.com/nomo-lang/tree-sitter-nomo/actions/runs/29729299721) | [release](https://github.com/nomo-lang/tree-sitter-nomo/releases/tag/v0.0.0-20260720080715) |
| VS Code extension | `fe7d0972164195b0e54ee62bc66955cdac5885e8` / `6918f40b31319ce83a8c141f063ea2d619efe595` | [vscode-nomo#1](https://github.com/nomo-lang/vscode-nomo/pull/1) | [run 29729299495](https://github.com/nomo-lang/vscode-nomo/actions/runs/29729299495) | [release](https://github.com/nomo-lang/vscode-nomo/releases/tag/v0.0.0-20260720080715) |
| Zed extension | `88be6c33864092fd4e362a047f70d34cfcb296aa` / `98c83420a8e323fb28770299b8c42446ae9a8462` | [zed-nomo#1](https://github.com/nomo-lang/zed-nomo/pull/1) | [run 29729299662](https://github.com/nomo-lang/zed-nomo/actions/runs/29729299662) | [release](https://github.com/nomo-lang/zed-nomo/releases/tag/v0.0.0-20260720080715) |
| IntelliJ extension | `410cadf41efe667ac2afae14c9db4e24897c4388` / `973b899f7f07670fe0b1bb1efe4752795064be4a` | [intellij-nomo#1](https://github.com/nomo-lang/intellij-nomo/pull/1) | [run 29729299964](https://github.com/nomo-lang/intellij-nomo/actions/runs/29729299964) | [release](https://github.com/nomo-lang/intellij-nomo/releases/tag/v0.0.0-20260720080715) |
| setup-nomo | `64abc90ac74a8ad1253d7088e40b78511c59d559` / `e5fa00437032429fe0594f2417ce6e03295a1dae` | [setup-nomo#1](https://github.com/nomo-lang/setup-nomo/pull/1) | [CI 29728432536](https://github.com/nomo-lang/setup-nomo/actions/runs/29728432536) | [release](https://github.com/nomo-lang/setup-nomo/releases/tag/v0.0.0-20260720080715) |

All seven signed tags resolve to the listed main revisions. Nomo LSP pins the
listed Nomo revision, and the Zed extension pins the listed tree-sitter
revision.

## Automated gate evidence

- Nomo CI passed formatting, Clippy, the full workspace test suite, release
  builds, examples, package-manager and standard-library checks.
- The Nomo release matrix built Linux x86-64, macOS x86-64 and arm64, and
  Windows x86-64 archives. Each archive was extracted and used to create,
  compile, and run a new project through the platform C compiler.
- Nomo LSP passed 90 tests, formatting, Clippy, release build, stdio protocol
  smoke tests, and the four-platform release matrix.
- Compiler release-gate JSON reported clean-build times from `198.666 ms` to
  `5436.745 ms` against a `10000 ms` threshold, and check p95 values from
  `5.083 ms` to `28.146 ms` against a `2000 ms` threshold.
- LSP release-gate JSON reported exactly one diagnostic and 28 completions on
  every target. All initialize, diagnostic, completion, warm completion,
  incremental-edit diagnostic, and post-edit completion measurements remained
  below their thresholds.
- Tree-sitter generation and six corpus tests passed. VS Code package tests,
  Zed WASM build/tests, IntelliJ tests/build/verifier, and setup-nomo's eight
  cross-platform installer tests passed.
- IntelliJ Plugin Verifier accepted the release ZIP against
  `IC-242.20224.300` and `IU-261.26222.65`.

The downloaded assets were independently checked after publication. All Nomo
and Nomo LSP archives and their gate JSON files passed `shasum -a 256 -c`.
The tree-sitter tarball passed its published checksum; the VSIX and IntelliJ
ZIP passed `unzip -t`; and the Zed tarball passed a complete archive listing.
Checksums are retained in [`nomo-SHA256SUMS`](./nomo-SHA256SUMS),
[`nomo-lsp-SHA256SUMS`](./nomo-lsp-SHA256SUMS), and
[`editor-SHA256SUMS`](./editor-SHA256SUMS).

## Hands-on installation and host smoke

The smoke fixture intentionally assigned a string to an `i64` so every editor
had to receive a real diagnostic from the matching released language server.

- **Installer:** the built setup-nomo action downloaded the public macOS arm64
  archive for the exact tag, verified its checksum and safe extraction, and
  installed the compiler. The installed binary created a new project and
  `nomo run` printed `Hello, Nomo`.
- **VS Code:** the public VSIX was installed into an isolated instance of the
  official Visual Studio Code application. The extension reported version
  `0.0.0-20260720080715`, activated in 19 ms, logged
  `nomo-lsp initialized`, and displayed one problem.
- **Zed:** the public source tarball was installed as a development extension
  in the Zed application. Zed compiled the released Rust extension and pinned
  grammar, started the released Nomo LSP, highlighted the file, and displayed
  one diagnostic.
- **IntelliJ:** the public plugin ZIP was installed in IntelliJ IDEA 2026.1.3.
  The IDE log loaded only `Nomo (0.0.0-20260720080715)`. Its Language Servers
  tool window showed `Nomo Language Server` started, the process command was
  `/tmp/nomo-lsp-host-20260720080715/nomo-lsp`, and the editor displayed one
  highlighted error.

## Snapshot waiver and distribution notes

The tree-sitter release built the npm tarball, attached Sigstore provenance,
and published the GitHub prerelease, but npm rejected the registry upload
because the `tree-sitter-nomo` package does not yet exist for the configured
publisher/token. This is the only release-workflow failure and is waived for
this development snapshot under `RELEASE-GATE.md`.

- Tracking issue: [tree-sitter-nomo#2](https://github.com/nomo-lang/tree-sitter-nomo/issues/2)
- Owner: `@fynntang`
- User impact: `npm install tree-sitter-nomo@0.0.0-20260720080715` is
  unavailable; consumers must use the checksum-verified GitHub tarball. The
  Zed snapshot remains reproducible because it pins the exact merged grammar
  revision.
- Deadline: resolve package ownership and registry credentials before the next
  preview snapshot.

VS Marketplace, Open VSX, and JetBrains Marketplace credentials were not
configured, so their optional store publication steps were skipped. The
checksum-verified GitHub prerelease assets are the canonical install source for
this snapshot. A future stable release must not retain the npm waiver and must
re-evaluate store distribution readiness.
