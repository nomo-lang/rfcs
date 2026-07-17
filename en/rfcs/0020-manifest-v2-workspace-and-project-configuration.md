# RFC 0020: Manifest v2, Workspace Membership, and Project Configuration

> Language: [中文](../../zh-CN/rfcs/0020-manifest-v2-workspace-and-project-configuration.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0020 |
| Title | Manifest v2, Workspace Membership, and Project Configuration |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-17 |
| Related topics | manifest, package management, workspace, migration, registry trust |
| Related RFCs | [RFC 0008](./0008-canonical-package-identity-and-aliases.md), [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md), [RFC 0013](./0013-registry-protocol-and-package-integrity.md), [RFC 0018](./0018-package-signing-provenance-and-transparency.md) |

---

## 1. Summary

Introduce an explicitly versioned `nomo.toml` schema that separates
publishable package/workspace facts from project and organization operating
policy. Manifest v2 requires stable package identity, provides one explicit
workspace-inheritance switch, validates membership before inheritance, and
keeps dependency aliases separate from canonical package identity. Registry
trust, transparency gossip, and other environment policy move to
`.nomo/config.toml`; `nomo manifest migrate` performs the v1-to-v2 transition.

## 2. Motivation

The original manifest grew incrementally with package identity, workspace
defaults, source selection, target conditions, FFI metadata, and transparency
policy. It now has several undesirable properties:

- absent package fields silently fall back to directory name, `local`, `0.1.0`,
  and edition `2026`;
- `workspace.package.name` can be inherited even though member names must be
  distinct;
- `namespace.workspace = true` and similar per-field switches are repetitive;
- an ancestor containing `[workspace]` can be discovered before proving that
  the package is an included member;
- publishable `nomo.toml` files contain consumer-side registry trust and gossip
  paths;
- legacy top-level `name = "..."` files are accepted without an explicit schema
  boundary.

These behaviors make package identity and operational policy harder to audit.
The migration must happen before the preview stabilizes `nomo.toml` as a public
compatibility surface.

## 3. Status and Problem

RFC 0008 defines canonical package identity as `namespace/name`. RFC 0009
defines one workspace-root lockfile and typed workspace/package/module graphs.
The implementation already supports inherited workspace dependencies,
target-conditioned dependency edges, registry solving, signed releases, and
offline operation.

The problem is not missing graph capability; it is that schema detection,
inheritance, membership, and local policy remain coupled in a permissive
`toml::Value` parser. Tooling cannot reliably answer whether a file is legacy
input, a standalone package, a virtual workspace, or a combined root package.

## 4. Detailed Design

### 4.1 Schema selection and document kinds

Manifest v2 begins with:

```toml
manifest-version = 2
```

Absence of `manifest-version` selects the legacy v1 compatibility parser.
Unsupported values are errors and never fall back to v1. V2 accepts only the
top-level keys `manifest-version`, `package`, `workspace`, `dependencies`, and
`ffi`. `[trust]` is a targeted migration error pointing to
`.nomo/config.toml`.

A document is one of:

- package: `[package]` only;
- virtual workspace: `[workspace]` only;
- combined workspace root: both tables, with `"."` explicitly present in
  `workspace.members` when the root package participates.

### 4.2 Package identity and metadata

A standalone package declares all identity fields:

```toml
manifest-version = 2

[package]
namespace = "acme"
name = "calculator"
version = "1.2.0"
edition = "2026"
description = "A deterministic calculator"
license = "Apache-2.0"
repository = "https://example.com/acme/calculator"
publish = true
```

`namespace`, `name`, `version`, and `edition` have no v2 directory or version
fallback. `name` is always package-local and cannot be inherited. Descriptive
metadata is preserved by the typed manifest and archive tooling.

A member can opt into missing workspace defaults with one declaration:

```toml
manifest-version = 2

[package]
name = "cli"
inherit = "workspace"
publish = false
```

Explicit member values win. Missing `namespace`, `version`, or `edition` must
exist in `[workspace.package]`; otherwise parsing fails. `inherit` is valid only
after the package root has been proven to match `members` minus `exclude`.

### 4.3 Workspace topology

```toml
manifest-version = 2

[workspace]
members = ["apps/*", "packages/*"]
default-members = ["apps/cli"]
exclude = ["packages/legacy"]
resolver = "2"

[workspace.package]
namespace = "acme"
version = "0.1.0"
edition = "2026"
license = "Apache-2.0"

[workspace.dependencies]
json = { package = "nomo-lang/json", version = "^1.2.0" }
core = { path = "packages/core" }
```

Member and exclusion paths are normalized relative paths that cannot escape the
workspace root. Every selected member must contain a v2 package manifest.
`default-members` must be a subset of included members. Duplicate canonical
identity, duplicate canonical path, nested workspace ambiguity, and symlink
escape are errors.

The workspace dependency table is a source/version catalog, not an implicit
import grant. Members opt in:

```toml
[dependencies]
json = { workspace = true }
core = { workspace = true }
```

### 4.4 Dependencies

Dependency table keys remain package-local import aliases. Registry dependencies
require canonical package and a version constraint. A path dependency may omit
`package`; Nomo reads the target manifest and derives the canonical id. If the
field is present it is an assertion and must match. Git dependencies retain an
explicit canonical package because identity must be available before network
checkout.

```toml
[dependencies]
json = { package = "nomo-lang/json", version = "^1.2.0" }
core = { path = "../core" }
http = { package = "nomo-lang/http", git = "https://example.com/http.git", rev = "abc123" }
win = { package = "acme/windows", version = "1.0.0", target = { os = ["windows"], env = ["msvc"] } }
```

Exactly one source family is permitted: registry (`version`), `path`, or `git`.
Workspace inheritance cannot be combined with source fields. Existing
target-condition canonicalization and complete lockfile representation remain
unchanged.

### 4.5 Project and organization configuration

Operational policy moves to `.nomo/config.toml`:

```toml
config-version = 1

[registry]
policy = "signed+transparent"
transparency-keys = ["<32-byte-ed25519-public-key-hex>"]
proof-max-age-seconds = 86400
offline-proof-max-age-seconds = 604800
max-future-skew-seconds = 300
gossip-checkpoints = ["trust/peer-a.json"]
```

For a workspace member, the verified workspace-root configuration applies. A
standalone package uses its own project-root configuration. Dependency package
configuration never changes the consuming project's trust policy. Paths are
resolved relative to the project/workspace root, not the `.nomo` directory.
Credentials and private keys remain outside both files.

The v1 `[trust]` table remains readable only through the v1 compatibility
parser. V2 rejects it so newly published manifests cannot carry consumer-side
policy.

### 4.6 Lockfile and command scope

Standalone packages are treated as one-package resolution roots. Workspaces
continue to own exactly one root `nomo.lock`. Running a command inside a member
selects that member; running at a virtual workspace root selects
`default-members`; `--workspace` selects all members and `--package` selects one
canonical id or unique package name.

`nomo add` and `nomo remove` edit the selected member. A future explicit
workspace-catalog editing flag can be added without changing v2 parsing.

### 4.7 Migration

`nomo manifest migrate [path]`:

1. parses the v1 document;
2. writes `manifest-version = 2`;
3. materializes fields that previously came from defaults;
4. converts per-field workspace inheritance into `inherit = "workspace"`;
5. removes invalid `workspace.package.name`;
6. moves `[trust]` into `.nomo/config.toml`;
7. validates the resulting package/workspace graph;
8. atomically replaces files only after every output validates.

`--check` performs the same analysis without writing and fails when migration is
required. Already-v2 input is idempotent. The tool never rewrites `nomo.lock`
unless dependency semantics changed and the user subsequently resolves.

### 4.8 Typed API and diagnostics

`nomo-manifest` exposes a schema enum, a typed document kind, typed package and
workspace declarations, and typed project configuration. Consumers no longer
infer document kind from optional raw TOML tables.

Manifest failures continue through project diagnostic `E0901`, with messages
that include the file, schema, table/field, and an actionable migration hint.
Key negative cases include unknown fields, missing explicit identity, inheritance
outside membership, trust in a v2 manifest, path identity mismatch, and
unsupported schema versions.

### 4.9 Compiler, C backend, standard library, and runtime impact

There is no language or C ABI change. The compiler receives the same resolved
canonical package and target-filtered dependency graphs. The standard library
and runtime are unaffected except that the toolchain standard-library manifest
is migrated to v2 and its descriptive metadata becomes typed rather than
ignored.

### 4.10 Test plan

- v1 compatibility and deterministic migration snapshots;
- v2 positive/negative parser tests and unknown-field tests;
- standalone, virtual, and combined workspace discovery;
- non-member/excluded/nested/symlink membership rejection;
- workspace inheritance and dependency-catalog tests;
- derived path identity and asserted mismatch tests;
- `.nomo/config.toml` scope, trust, gossip-path, and dependency-isolation tests;
- CLI `manifest migrate` check/write/idempotence tests;
- existing resolver, lockfile, offline, vendor, target, signing, and cross-build
  suites.

## 5. Alternatives

| Option | Approach | Advantages | Disadvantages |
| --- | --- | --- | --- |
| Keep extending v1 | Add more optional tables and defaults | No migration command | Ambiguous identity and policy coupling become permanent |
| Split package and workspace into differently named manifests | Use `nomo.package.toml` and `nomo.workspace.toml` | Strong file-level distinction | More discovery rules and awkward combined roots |
| Explicit v2 plus project config | Version `nomo.toml`, validate kinds, move operations to `.nomo/config.toml` | Clear compatibility boundary and reproducible package semantics | Requires migration and a temporary dual parser |

## 6. Drawbacks and Risks

The implementation temporarily maintains two parsers and must not accidentally
apply v1 defaults to v2. Moving trust policy can surprise users if migration is
partial, so file replacement must be transactional. Strict membership can
reject directory layouts that previously inherited accidentally. Comment
preservation is limited unless the editing layer later adopts a lossless TOML
document model.

## 7. Impact on v0.1 Scope

Manifest v2 is preview-stabilization work and belongs before v1.0. This RFC does
not add features, build scripts, multiple binary targets, or dev/build
dependencies; those require separate compatibility decisions. Acceptance adds
manifest migration and strict workspace/configuration cases to the release
matrix while retaining all existing graph and cross-build gates.

## 8. Recommendation

Accept the explicit v2 schema, strict identity and document kinds, verified
workspace inheritance, dependency catalog semantics, project configuration
split, and deterministic migration command. Keep the v1 parser read-only
compatible during the preview, then remove it only through a later RFC.

## 9. Open Questions

- Whether a future release should use a lossless TOML editor to preserve
  comments during all CLI mutations.
- Whether named registries and per-registry trust policy should extend
  `.nomo/config.toml` in a follow-up RFC.
- Whether optional features, dev dependencies, and multiple build targets
  belong in one package-model RFC or separate proposals.

## 10. Implementation Status

Accepted and implemented on 2026-07-17. The implementation includes the typed
v1/v2 compatibility boundary, strict v2 package/workspace/config validation,
membership-before-inheritance, derived path dependency identities, workspace
root configuration, transactional `nomo manifest migrate`, v2 project
scaffolding, standard-library and representative example migration, and
documentation updates. The complete Cargo workspace test suite passes with the
new behavior while retaining v1 compatibility.

## 11. References

- [RFC 0008](./0008-canonical-package-identity-and-aliases.md)
- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)
- [RFC 0013](./0013-registry-protocol-and-package-integrity.md)
- [RFC 0018](./0018-package-signing-provenance-and-transparency.md)
