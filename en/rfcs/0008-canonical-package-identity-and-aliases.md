# RFC 0008: Separating Canonical Package Identity from Dependency Aliases

> 语言 / Language: [中文](../../zh-CN/rfcs/0008-canonical-package-identity-and-aliases.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0008 |
| Title | Separating canonical package identity from dependency aliases |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Landed: standard TOML manifests, `owner/package` validation, dependency-alias imports, reserved namespaces, and legacy `std` compatibility have manifest and CLI coverage |
| Related topics | package identity, manifest, dependency alias, import, compatibility |
| Related RFCs | [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md), [RFC 0013](./0013-registry-protocol-and-package-integrity.md) |

---

## 1. Summary

A Nomo package has the stable identity `owner/package`. A dependency key is only a package-local import alias, while Git URLs, registries, paths, branches, tags, and revisions are sources. Source code depends on aliases and does not embed acquisition locations into language identity.

## 2. Motivation

If URLs, directory names, or aliases define identity, the same package becomes multiple type origins when acquired differently, and moving to a mirror or vendor directory changes imports. Stable identity, local naming, and physical source must be separate.

## 3. Current Implementation

- `[package]` uses `namespace`, `name`, `version`, and `edition`; the canonical id is `namespace/name`.
- A dependency key follows Nomo identifier rules and becomes the source import root.
- A dependency `package` is exactly two valid `owner/package` segments.
- `std`, `nomo`, and `core` are reserved namespaces. `std` is built in and is not a normal lockfile package.
- Legacy `std = "0.1.0"` declarations are accepted only as ignored compatibility input.

## 4. Detailed Design

```toml
[package]
namespace = "fynn"
name = "app"
version = "0.1.0"
edition = "2026"

[dependencies]
json = { package = "nomo-lang/json", version = "0.1.0" }
utils = { package = "fynn/utils", path = "../utils" }
```

Source imports `json.parser` and `utils.path`. Diagnostics, lockfiles, publishing, and conflict detection use canonical ids. Each dependency selects exactly one of the `path`, `git`, or `version` source classes.

## 5. Alternatives

| Option | Result | Decision |
| --- | --- | --- |
| URL as identity | Acquisition leaks into source and mirror changes alter type identity | Rejected |
| Alias as identity | Every dependent gives one package a different global identity | Rejected |
| `owner/package` + alias + source layers | Stable identity, local naming freedom, replaceable source | Accepted |

## 6. Drawbacks and Risks

- Namespace ownership needs registry governance.
- Diagnostics and lockfiles must clearly distinguish aliases from canonical ids.
- Legacy compatibility is a migration tool and must not prevent eventual cleanup.

## 7. Impact on v0.1 Scope

This fixes the common identity model for `nomo.toml`, imports, lockfiles, workspaces, and registries. v0.1 rejects one canonical id resolving to conflicting sources or versions instead of performing multi-version solving.

## 8. Decision

Accept namespace-first identity: canonical id is `owner/package`; aliases are package-local import names; source metadata is not language identity.

## 9. Follow-up Questions

- Namespace transfer, organization verification, and dispute handling.
- When to end legacy manifests and explicit `std` dependency compatibility.
- Whether and how multi-version dependencies enter a future resolver.

## 10. References

- `nomo-manifest`, project import validation, `nomo add/remove`, and namespace/reserved-name CLI tests.
- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md), [RFC 0013](./0013-registry-protocol-and-package-integrity.md).
