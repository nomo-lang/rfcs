# RFC 0021: Manifest-Derived Module Roots and Dependency Alias Mapping

> Language: [中文](../../zh-CN/rfcs/0021-manifest-derived-module-roots.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0021 |
| Title | Manifest-derived module roots and dependency alias mapping |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-23 |
| Implementation | Not implemented; this RFC fixes the migration order and compatibility boundary |
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

The source root is a deterministic `lower_snake` projection:

- ASCII uppercase letters become lowercase, inserting `_` at a lower/digit to
  uppercase boundary;
- `-` becomes `_`;
- repeated `_` is collapsed;
- Manifest v2 continues to prefer lowercase kebab names. CamelCase conversion
  primarily serves legacy migration.

Examples:

| Manifest name | Module root |
| --- | --- |
| `hello` | `hello` |
| `hello-world` | `hello_world` |
| legacy `HelloWorld` | `hello_world` |

The result must be a valid Nomo identifier.

## 4. File mapping

For `name = "hello-world"`:

| File | Declaration |
| --- | --- |
| `src/main.nomo` | `package hello_world` |
| `src/math.nomo` | `package hello_world.math` |
| `src/http/client.nomo` | `package hello_world.http.client` |
| `src/http/main.nomo` | `package hello_world.http` |

The entry file does not append `.main`. A mismatch continues to use `E0904`,
with LSP quick fixes for updating the declaration or moving the file.

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
5. Accept legacy `app.*` for one development snapshot with a migration
   diagnostic, then remove compatibility in the following snapshot.
6. Migrate the standard library, examples, Playground, LSP fixtures, and
   editor documentation.

Dependency alias imports are not rewritten unless they actually refer to the
current package's legacy `app.*` root.

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
- A main declaration inconsistent with the manifest produces `E0904`.
- Two consumers can use different aliases for unchanged dependency source.
- Navigation, rename, and docs remain correct across local modules,
  dependencies, and workspace members.
- Migration supports `--check`, is idempotent, and leaves no partial writes.

