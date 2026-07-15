# RFC 0013: Registry Protocol, Authentication, and Package Integrity

> 语言 / Language: [中文](../../zh-CN/rfcs/0013-registry-protocol-and-package-integrity.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0013 |
| Title | Registry protocol, authentication, and package integrity |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Landed: file/HTTP/HTTPS registries, TLS verification, metadata/index, archive checksums, cache, publish/search/yank/login/owner, and bearer-token tests |
| Related topics | registry, package archive, metadata, checksum, authentication, yank |
| Related RFCs | [RFC 0008](./0008-canonical-package-identity-and-aliases.md), [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md), [RFC 0014](./0014-semver-resolution-and-conflict-explanations.md) |

---

## 1. Summary

The registry protocol publishes, describes, and downloads exact versions using
deterministic `.nomo-package` archives and explicit metadata/checksums.
Endpoints may use `file://`, `http://`, or certificate-verified `https://`.
HTTP(S) operations use fixed `/api/v1` paths and endpoint-scoped bearer tokens.
RFC 0014 subsequently accepted manifest ranges and deterministic selection over
the package-index response without changing these exact-version artifact paths.

## 2. Motivation

Downloading an archive from a URL alone does not define identity, version, integrity, yank behavior, or authentication. The CLI, resolver, lockfile, and registry server need one minimal but verifiable protocol.

## 3. Metadata and Download

- Exact-version metadata contains `package`, `version`, archive `checksum`, and `yanked`.
- A package index returns a package id and versions array. RFC 0014 uses this
  response for range solving; implicit `latest` selection remains unsupported.
- Fresh resolution rejects yanked versions and verifies the archive checksum before unpacking.
- An existing lockfile may continue using an already verified cached or vendored yanked exact version.
- Unpacked source checksums are recorded separately from archive checksums.

## 4. Operations

- Publish: `PUT /api/v1/packages/<owner>/<package>/<version>`.
- Download/metadata: `GET` exact package/version paths.
- Search: `GET /api/v1/packages?query=<encoded>`.
- Yank: `POST .../<version>/yank`.
- Owner add/remove: `PUT`/`DELETE .../owners/<user>`.
- Login writes a token to `$NOMO_HOME/credentials.toml` or `$HOME/.nomo/credentials.toml`; requests to that endpoint attach `Authorization: Bearer`.

## 5. Archive and Transport

An archive contains `nomo.toml` and `src/`, cannot escape its target path, and validates each file header and content checksum. HTTPS verifies certificates through the client trust chain and has no default insecure mode. A base endpoint cannot contain a query or fragment.

## 6. Alternatives

| Option | Problem | Decision |
| --- | --- | --- |
| Git-only distribution | No publish/yank/owner/metadata protocol | Insufficient |
| HTTP download without checksums | Package can be corrupted or replaced | Rejected |
| Exact version + metadata + checksum + TLS | Reproducible, authenticated, bounded | Accepted |

## 7. Drawbacks and Risks

- The protocol has no interactive OAuth, token refresh, or batched metadata endpoint.
- Credential files hold bearer secrets and must not leak through permissions or logs.
- Registry servers still need to implement the same metadata and error semantics.

## 8. Decision

Accept the exact-version `/api/v1` protocol, deterministic archives, two checksum layers, yank retention, endpoint-scoped bearer tokens, and verified HTTPS.

## 9. Follow-up Questions

- Protocol negotiation and server capability discovery.
- Namespace verification, MFA, and token scopes/rotation.
- Signed packages and transparency logs.

## 10. References

- `nomo-resolver` registry metadata/transport/archive APIs and registry CLI tests.
- [RFC 0008](./0008-canonical-package-identity-and-aliases.md), [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md), [RFC 0014](./0014-semver-resolution-and-conflict-explanations.md).
