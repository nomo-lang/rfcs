# Nomo Versioning and Release Policy

Nomo separates continuously publishable development snapshots from versions
that carry a public compatibility promise.

## Development snapshots

All releasable components use this SemVer prerelease shape while they are under
active development:

```text
0.0.0-YYYYMMDDHHMMSS
```

The timestamp is UTC and records when the snapshot version was prepared. A
snapshot tag is the version prefixed with `v`, for example
`v0.0.0-20260713070000`.

Snapshot releases:

- may be published at any time;
- are marked as prereleases and must not replace a stable `latest` channel;
- make no compatibility promise between timestamps;
- use one timestamp across the compiler, standard library, language server,
  grammar, setup action, and editor integrations when they are released as one
  toolchain set.

The timestamp is part of the prerelease identifier. It is not SemVer build
metadata, because package registries and installers must be able to distinguish
and order published snapshots.

## Stable releases

After the stabilization gate is satisfied, public releases use ordinary SemVer,
for example `1.0.5`. Stable versions contain no timestamp or prerelease suffix.

- `MAJOR` changes when compatibility is intentionally broken.
- `MINOR` adds backward-compatible language or tooling capability.
- `PATCH` contains backward-compatible fixes.

A stable tag must exactly match the component manifest version, prefixed by
`v`. Published versions are immutable and are never reused.

## What owns a release version

The policy applies to independently publishable Nomo components. Example
projects, dependency-resolution fixtures, RFC code samples, and compatibility
tests may intentionally contain other versions; they are test data and are not
the version of the toolchain.

## Preparing a release

1. Choose one UTC timestamp for a coordinated snapshot, or choose the approved
   stable SemVer after the stabilization gate passes.
2. Update the releasable component manifests and generated lockfiles.
3. Run `python3 scripts/check_release_set.py --require-clean --output
   release-set.json` from this repository to verify component versions and
   record exact Git revisions.
4. Run each repository's complete validation workflow.
5. Tag each participating repository with the exact `v<version>` tag.
6. Verify that timestamped artifacts are prereleases and stable artifacts are
   normal releases.
