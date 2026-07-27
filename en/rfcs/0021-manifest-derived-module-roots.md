# RFC 0021: Manifest-Derived Module Roots and Dependency Alias Mapping

> Language: [中文](../../zh-CN/rfcs/0021-manifest-derived-module-roots.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0021 |
| Title | Manifest-derived module roots and dependency alias mapping |
| Decision Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-23 |
| Implementation Status | Not implemented |
| Related topics | package declaration, module identity, dependency alias, manifest migration, LSP |
| Related RFCs | [RFC 0008](./0008-canonical-package-identity-and-aliases.md), [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md), [RFC 0020](./0020-manifest-v2-workspace-and-project-configuration.md) |

## 1. Summary

A package's source module root is derived from its own `nomo.toml`
`[package].name`, not from an arbitrary `app` placeholder in
`src/main.nomo`. The entry file declares `package <root>` and other source
files declare `package <root>.<path>`.

A dependency alias exists only in the consumer's imports. The compiler maps
that alias to the dependency's own source module root without requiring the
dependency source to use a consumer-selected name.

## 2. Motivation

Examples currently tend to declare `package app.main`. `app` is neither the
manifest package name nor the canonical package id. More importantly, the
current loader conflates dependency aliases with source declarations. The same
`nomo-lang/utils` source cannot declare both `utils.path` and
`local_utils.path` for two consumers. That contradicts RFC 0008.

## 3. Name derivation

The source root is a deterministic `lower_snake_case` projection of
`[package].name` only. The package `namespace`, canonical `owner/package`
identity, and every consumer-selected dependency alias are excluded.

For an already validated Manifest v2 package name, the projection:

1. converts `-` to `_`;
2. inserts `_` before an ASCII uppercase letter when the preceding character
   is lowercase/digit, or when an uppercase run is followed by lowercase;
3. lowercases ASCII uppercase letters;
4. collapses repeated `_`; and
5. validates the result as one non-reserved Nomo identifier.

Manifest v2 continues to prefer lowercase kebab names. CamelCase handling is
deterministic migration behavior, not permission to broaden the manifest
grammar.

Examples:

| Manifest name | Module root |
| --- | --- |
| `hello` | `hello` |
| `hello-world` | `hello_world` |
| legacy `HelloWorld` | `hello_world` |
| legacy `HTTPServer` | `http_server` |

The manifest is rejected before source loading when the projection cannot
produce a valid identifier.

## 4. File mapping

For `name = "hello-world"`:

| File | Declaration |
| --- | --- |
| `src/main.nomo` | `package hello_world` |
| `src/math.nomo` | `package hello_world.math` |
| `src/http/client.nomo` | `package hello_world.http.client` |
| `src/http/main.nomo` | `package hello_world.http` |

The compiler computes the expected declaration by removing the `src/` prefix
and `.nomo` suffix:

- `src/main.nomo` maps directly to the manifest root;
- a nested `main.nomo` maps to the containing directory path; and
- every other file maps to its relative directory path plus file stem.

The entry file therefore does not append `.main`. Project discovery loads the
manifest before validating any source declaration. The compiler must not
infer or replace the project root from the first segment written in
`src/main.nomo`.

`E0904` covers both entry and imported-module mismatches. Its diagnostic
includes the manifest-derived expected declaration, actual declaration, source
path, manifest path, and safe fixes for updating the declaration or moving the
file. The CLI, compiler, docs, formatter, and LSP use the same mapping helper.

## 5. Dependency alias mapping

A package named `utils` always declares source such as `package utils.path`.
A consumer may declare alias `local_utils` and write
`import local_utils.path`.

Resolution maps `local_utils` to canonical package `nomo-lang/utils`, then
validates the loaded source as `utils.path`. Internal semantic identity uses
the canonical package id plus source module path, so equal source roots in two
different canonical packages do not share type identity.

A dependency alias may not collide with the current package's module root or
the reserved `std` root.

## 6. Migration

Implementation order:

1. Provide one package-name-to-module-root function in the manifest crate.
2. Carry canonical package id, source module root, and consumer alias as
   separate module-graph fields.
3. Share file mapping across CLI, compiler, LSP, docs, and formatting.
4. Add `nomo fix module-roots [path] [--check]` with atomic updates.
5. Accept the legacy entry declarations `package app.main` and
   `package <root>.main`, plus the corresponding `app.<relative-path>` package
   layout, for exactly one development snapshot with migration diagnostic
   `W0904`.
6. Migrate the standard library, examples, Playground, LSP fixtures, and
   editor documentation.

The migration command discovers exactly one current package from `path`
(default `.`), computes all changes before writing, and then atomically
replaces that package's Nomo source files. If any file cannot be read,
validated, formatted, or staged, no source file changes. `--check` performs the
same discovery and validation, writes nothing, exits successfully when no
changes are needed, and exits unsuccessfully with the files that require
migration otherwise. A second normal run is a no-op.

Only declarations and self-imports that resolve to the current package are
eligible. Dependency source trees, dependency aliases, generated/vendor/cache
directories, and imports resolved through dependency aliases are never
rewritten. Workspace invocation migrates only the selected member unless each
member is explicitly selected.

The compatibility window begins with the first snapshot containing both the
new validator and `nomo fix module-roots`. `W0904` names the accepted legacy
form, canonical replacement, migration command, and removal snapshot. The
following development snapshot removes the compatibility path only after the
standard library, templates, examples, fixtures, benchmark probes,
`nomo-hello`, Playground, LSP, and editor surfaces are canonical and the
repository gate finds no legacy declaration outside intentionally negative
fixtures.

## 7. Alternatives

| Alternative | Result | Decision |
| --- | --- | --- |
| Keep `app` permanently | Source identity remains unreadable and detached from manifests | Reject |
| Use canonical `owner/package` in source | `/` conflicts with module syntax and organization changes leak into source | Reject |
| Use the consumer alias in source | One package cannot be reused under different aliases | Reject |
| Manifest-derived source root plus alias mapping | Stable source, locally named imports, unambiguous internal identity | Proposed |

## 8. Risks

- This is a source compatibility change and requires mechanical migration.
- Module graphs must distinguish display paths from canonical identity rather
  than applying a string replacement.
- Dependencies may share a manifest name. Different aliases plus canonical
  package ids must keep them distinct.

## 9. v0.1 impact

This should land before v0.1 Preview 1, but it does not require publishing that
preview immediately. It repairs a mismatch between an accepted package identity
decision and its implementation without adding language expressiveness.

## 10. Acceptance

- `nomo new hello-world` generates `package hello_world`.
- `src/main.nomo`, `src/math.nomo`, and `src/http/main.nomo` map to
  `hello_world`, `hello_world.math`, and `hello_world.http`.
- A mismatched entry or imported module produces `E0904` from the manifest
  mapping, even when the entry's first segment looks internally consistent.
- Workspace members derive roots from their own manifests.
- Two consumers can use different aliases for unchanged dependency source,
  while canonical identities still keep equal source roots distinct.
- Navigation, rename, and docs remain correct across local modules,
  dependencies, and workspace members.
- Migration `--check` writes nothing, normal migration is idempotent, an
  injected failure leaves no partial writes, and dependency source/alias
  imports remain byte-for-byte unchanged.
- Legacy entry forms compile only during the documented compatibility snapshot
  and emit `W0904`; a removal-gate fixture proves the next snapshot rejects
  them.
- C99 and browser-WASM example gates compile canonical module roots.

## 11. Decision and implementation gate

This RFC remains `Proposed` and `Not implemented` while the contract is under
review. It may move to `Accepted` only in a separate evidence PR after the
compiler, migration command, formatter, scaffolder, docs, LSP, grammars,
editors, examples, standard library, C99/WASM paths, and documentation gates
above pass protected CI. Acceptance records the relevant merged commits and
snapshot/removal condition; internal tests alone are not production-readiness
evidence.
