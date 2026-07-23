# Nomo Preview Snapshot v0.0.0-20260721120555

## Decision

This coordinated release set is approved as an installable development
snapshot and published through GitHub Releases as a prerelease. It is not a
stable release and makes no compatibility promise between snapshot timestamps.

The release-set check passed with clean worktrees at the revisions recorded in
[`release-set.json`](./release-set.json). Every change was made on a child
branch, passed its repository CI, and merged through a pull request. All seven
annotated tags and their target commits are verified by GitHub. The release
commits were signed for `fzpying@gmail.com` with the 1Password-backed ED25519
key fingerprint
`SHA256:BXYkFdyb65Rf6++LCK29wCXknooz/Z2Cj4NrHLItkiU`.

## Release set

| Component | Main revision and tag target | Pull request | CI and release evidence | Prerelease |
| --- | --- | --- | --- | --- |
| Nomo compiler and standard library | `3cbe436c9b666768cfd324baf68d67c8bf7d4548` | [nomo#6](https://github.com/nomo-lang/nomo/pull/6) | [CI 29831873498](https://github.com/nomo-lang/nomo/actions/runs/29831873498), [release 29832452746](https://github.com/nomo-lang/nomo/actions/runs/29832452746) | [release](https://github.com/nomo-lang/nomo/releases/tag/v0.0.0-20260721120555) |
| Nomo LSP | `02c14ec47efce1ec8a6c8ac4fafb891eab7e8c8a` | [nomo-lsp#2](https://github.com/nomo-lang/nomo-lsp/pull/2) | [CI 29831874074](https://github.com/nomo-lang/nomo-lsp/actions/runs/29831874074), [release 29832453117](https://github.com/nomo-lang/nomo-lsp/actions/runs/29832453117) | [release](https://github.com/nomo-lang/nomo-lsp/releases/tag/v0.0.0-20260721120555) |
| Tree-sitter grammar | `d30bce91e5c5770a86967db809750a7e1bac1952` | [tree-sitter-nomo#3](https://github.com/nomo-lang/tree-sitter-nomo/pull/3) | [CI 29831873179](https://github.com/nomo-lang/tree-sitter-nomo/actions/runs/29831873179), [release 29832452841](https://github.com/nomo-lang/tree-sitter-nomo/actions/runs/29832452841) | [release](https://github.com/nomo-lang/tree-sitter-nomo/releases/tag/v0.0.0-20260721120555) |
| VS Code extension | `ca50c780182bd4f6d38f5e3d7d268b6e8078a274` | [vscode-nomo#3](https://github.com/nomo-lang/vscode-nomo/pull/3) | [CI 29831874006](https://github.com/nomo-lang/vscode-nomo/actions/runs/29831874006), [release 29832452556](https://github.com/nomo-lang/vscode-nomo/actions/runs/29832452556) | [release](https://github.com/nomo-lang/vscode-nomo/releases/tag/v0.0.0-20260721120555) |
| Zed extension | `973868a43d671fd41724e4993d46d7f1bcd4b048` | [zed-nomo#2](https://github.com/nomo-lang/zed-nomo/pull/2) | [CI 29831874369](https://github.com/nomo-lang/zed-nomo/actions/runs/29831874369), [release 29832453102](https://github.com/nomo-lang/zed-nomo/actions/runs/29832453102) | [release](https://github.com/nomo-lang/zed-nomo/releases/tag/v0.0.0-20260721120555) |
| IntelliJ extension | `1e35f0bfae33c930e08d5fa9d9e8c613462d0b02` | [intellij-nomo#2](https://github.com/nomo-lang/intellij-nomo/pull/2) | [CI 29831874147](https://github.com/nomo-lang/intellij-nomo/actions/runs/29831874147), [release 29832452725](https://github.com/nomo-lang/intellij-nomo/actions/runs/29832452725) | [release](https://github.com/nomo-lang/intellij-nomo/releases/tag/v0.0.0-20260721120555) |
| setup-nomo | `9e17c6bdbc346a360e7bf0cce304346c3a6fef61` | [setup-nomo#3](https://github.com/nomo-lang/setup-nomo/pull/3) | [CI 29831874245](https://github.com/nomo-lang/setup-nomo/actions/runs/29831874245) | [release](https://github.com/nomo-lang/setup-nomo/releases/tag/v0.0.0-20260721120555) |

## Automated gate evidence

- Nomo passed formatting, Clippy, its full workspace test suite, examples,
  release builds, the compiler performance gate, and real Linux x86-64 to
  arm64 and macOS arm64 to x86-64 cross-build jobs.
- Nomo and Nomo LSP produced Linux x86-64, macOS x86-64 and arm64, and Windows
  x86-64 archives. The platform jobs smoke-tested the packaged tools and
  published their release-gate measurements.
- Nomo LSP passed tests, formatting, Clippy, release build, protocol smoke and
  performance gates, and the four-platform release matrix.
- Tree-sitter regenerated without drift and passed all six corpus tests. VS
  Code passed tests, a zero-vulnerability npm audit, build, and VSIX packaging.
- Zed passed formatting, Clippy, tests, and its WASM release build. IntelliJ
  passed tests, plugin build, project validation, and Plugin Verifier against
  IC 2024.2 and IU 2026.1.4. setup-nomo passed on Linux, macOS, and Windows.

## Published artifact verification

The six public artifact repositories publish a `SHA256SUMS` manifest and SLSA
build provenance using GitHub artifact attestations. After publication, every
asset was downloaded independently:

- 20 archives, editor packages, and release-gate JSON reports passed
  `shasum -a 256 -c` against the published manifests;
- all 20 subjects passed `gh attestation verify` against their source
  repository;
- the tarballs and ZIP/VSIX files passed complete archive integrity checks;
- the released macOS arm64 toolchain created and ran a new project, printing
  `Hello, Nomo`.

The retained checksum manifests are
[`nomo-SHA256SUMS`](./nomo-SHA256SUMS),
[`nomo-lsp-SHA256SUMS`](./nomo-lsp-SHA256SUMS), and
[`editor-SHA256SUMS`](./editor-SHA256SUMS).

## Distribution policy

GitHub Releases are the canonical distribution channel for this snapshot.
Tree-sitter npm publication is now explicitly opt-in and requires both a valid
`NPM_TOKEN` and the repository variable `PUBLISH_NPM=true`; the npm job was
skipped for this release. Tracking remains in
[tree-sitter-nomo#2](https://github.com/nomo-lang/tree-sitter-nomo/issues/2).

VS Marketplace, Open VSX, and JetBrains Marketplace credentials were absent,
so their publication steps were skipped. setup-nomo is a signed source-only
release and has no binary artifact to attest. Its private-repository branch
protection limitation remains tracked in
[setup-nomo#2](https://github.com/nomo-lang/setup-nomo/issues/2).

## Post-release addendum — 2026-07-23

The statement above that npm publication was skipped remains an accurate record
of the coordinated release workflow. A later manual bootstrap published
`tree-sitter-nomo@0.0.0-20260721120555` from commit
`588f87886b11cf06ebff36f1e174ad9ac1fc52d2`, while the immutable release tag
points to `d30bce91e5c5770a86967db809750a7e1bac1952`. That registry version therefore
is not the artifact recorded by this release set and has no npm trusted-publish
provenance.

The correction preserved the original version and tag, then moved npm
publication into the release workflow so GitHub Releases and npm consume the
same package-job tarball. The first correction tag,
`v0.0.0-20260723104029`, produced an attested GitHub prerelease but npm rejected
an ambiguous tarball path. It remains as immutable evidence and was not
published to npm.

The final replacement is
[`tree-sitter-nomo@0.0.0-20260723110700`](https://www.npmjs.com/package/tree-sitter-nomo/v/0.0.0-20260723110700),
built from verified commit
`802dc8e8c89077a50cb8bddfc7e535dff570b2c6` and signed tag
`v0.0.0-20260723110700`:

- workflow fixes:
  [tree-sitter-nomo#6](https://github.com/nomo-lang/tree-sitter-nomo/pull/6)
  and
  [tree-sitter-nomo#7](https://github.com/nomo-lang/tree-sitter-nomo/pull/7);
- successful trusted-publish workflow:
  [run 30003042956](https://github.com/nomo-lang/tree-sitter-nomo/actions/runs/30003042956);
- canonical GitHub artifact:
  [release v0.0.0-20260723110700](https://github.com/nomo-lang/tree-sitter-nomo/releases/tag/v0.0.0-20260723110700);
- npm and GitHub tarballs are byte-identical with SHA-256
  `de7dead32a94db7b971bd622c2a33c8f96d02a16044fcf82e3ff17352ce8ffa1`;
- npm SLSA provenance records `release.yml`, the signed tag, commit
  `802dc8e8c89077a50cb8bddfc7e535dff570b2c6`, and workflow run
  `30003042956`; its SHA-512 subject matches the public registry tarball;
- an independent Node.js 22 consumer installed the exact public version and
  parsed representative Nomo source successfully.

The older bootstrap version is now deprecated with an explicit pointer to the
replacement. Both the `snapshot` and `latest` distribution tags resolve to
`0.0.0-20260723110700`; npm rejected removing `latest` entirely, so it was
retargeted to the verified replacement instead. The cleanup used npm's
Security Key flow without relaxing the package's publishing policy, which
continues to require two-factor authentication or the configured OIDC trusted
publisher and disallows access-token publication. All temporary access and
CLI-session tokens used for the correction were revoked after verification.
