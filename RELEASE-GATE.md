# Nomo Preview Stabilization Gate

The Preview is ready to promote to a stable public version only when every
required row below is green for the same source revisions and version set.

## Required gates

| Area | Required evidence |
| --- | --- |
| Compiler | `cargo test --workspace`, formatting, and lint checks pass |
| Native targets | Release archives build on Linux x86-64, macOS x86-64 and arm64, and Windows x86-64 |
| C backend | Generated C99 compiles and runs with the supported platform C compilers |
| Examples | The checked-in example matrix checks, builds, and runs without undocumented exceptions |
| Diagnostics | E-code registry, JSON shape, documentation links, and snapshots agree |
| Packages | Resolve, lock, locked/offline/frozen, update, vendor, publish, and authenticated registry smoke tests pass |
| Standard library | Source inventory, intrinsic manifest, docs, compiler registry, and runtime behavior agree |
| LSP | Diagnostics, completion, navigation, rename, formatting, semantic tokens, and workspace overlays pass |
| Editors | VS Code, Zed, and IntelliJ packages build and complete a launch/diagnostic smoke test against the matching LSP |
| Installation | `setup-nomo` installs every supported archive and verifies checksums |
| Compatibility | Manifest, lockfile, diagnostic JSON, package identity, and stable syntax changes are explicitly reviewed |
| Performance | Clean build and representative LSP latency baselines are recorded and have no unexplained regression |
| Documentation | English and Chinese specs, accepted RFCs, README files, examples, and CLI help describe the shipped behavior |

## Release decision

A green CI run is necessary but not sufficient. The release owner records the
exact compiler, standard library, LSP, grammar, editor, and installer revisions.
Any waived row must have a linked issue, owner, user impact statement, and
deadline. Stable releases must not waive compatibility, artifact integrity, or
installation verification.

Development snapshots use the policy in [VERSIONING.md](./VERSIONING.md) and
may be released before this gate is fully green. They remain prereleases and do
not imply the stable compatibility promise.

## Automated evidence map

The following checks are executable today and must be green on the candidate
revisions:

| Gate slice | Automated evidence |
| --- | --- |
| Coordinated versions | `rfcs/scripts/check_release_set.py` verifies every releasable manifest and generated lock version, records each repository revision, and can require clean worktrees. |
| Compiler | `nomo` CI runs formatting, Clippy, the full workspace test suite, release builds, examples, and standard-library checks with locked dependencies. |
| Native archives and C backend | The `nomo` release matrix builds Linux x86-64, macOS x86-64/arm64, and Windows x86-64 archives, then extracts each archive and runs a newly generated project through the platform C compiler. |
| Package manager | The compiler CLI suite covers resolve/lock/locked/offline/frozen/update/vendor/publish/auth, including SemVer ranges, workspace convergence, yanks, cached HTTP indexes, and minimal conflicts. |
| Language server | `nomo-lsp` CI and every release-matrix target perform an actual stdio initialize, invalid-document diagnostic, and completion exchange, enforce broad latency limits, and retain JSON evidence. |
| VS Code | CI tests the server-path/language contract, builds the extension, and packages a VSIX without test-only files. |
| Zed | CI checks crate/extension version agreement, grammar revision, language/LSP metadata, and the release WASM build. |
| IntelliJ | Gradle tests the platform server-command and language mapping contract; CI builds and verifies the plugin against the configured IDE range. |
| Installation | `setup-nomo` tests Linux, macOS, and Windows archive naming, checksums, safe extraction, bundled `std/`, and executable discovery. The compiler release matrix separately runs each extracted toolchain. |
| Performance | Compiler clean-build/check and LSP initialize/diagnostic/completion gates upload per-run JSON measurements and fail broad preview regression thresholds. |

Before a stable promotion, the release record must still attach the successful
workflow URLs, generated release-set JSON, archive checksums, and hands-on host
launch/diagnostic smoke results for VS Code, Zed, and IntelliJ. Those host
applications cannot be treated as covered solely by metadata/unit tests.
