# RFC 0018: Package Signing, Provenance, and Transparency

> Language: [中文](../../zh-CN/rfcs/0018-package-signing-provenance-and-transparency.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0018 |
| Title | Package Signing, Provenance, and Transparency |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Not implemented; TLS, archive checksums, and registry ownership are verified today, but publisher signatures and an auditable log are absent |
| Topics | package signing, provenance, transparency log, registry, trust policy |
| Related RFCs | [RFC 0008](./0008-canonical-package-identity-and-aliases.md), [RFC 0013](./0013-registry-protocol-and-package-integrity.md) |

---

## 1. Summary

Add a signature envelope over canonical id, version, archive checksum, and provenance for every release. Registries return verifiable inclusion proofs from an append-only transparency log. The resolver enforces project or organization trust policy instead of treating registry TLS as publisher identity.

## 2. Motivation

A checksum detects disagreement between metadata and downloaded bytes but does not prove who authorized a release or expose a registry presenting different histories to different clients. A real ecosystem needs key rotation, revocation, and audit boundaries.

## 3. Proposed Design

- A deterministically encoded signed object covers canonical package, version, archive checksum, manifest checksum, publisher key id, and optional provenance digest.
- Namespace owners explicitly register publisher public keys. Registry-token authentication and release-signing keys remain separate.
- The transparency log provides a signed tree head and inclusion proof for every release and owner-key event; clients cache heads and detect rollback.
- Trust policy supports `checksum-only`, `signed`, and `signed+transparent`. Public registries should ultimately default to the strongest tier; private registries configure it explicitly.
- Rotation and revocation are new log events. Locked artifacts are never silently replaced, while refetch applies current policy.
- Private keys never enter Nomo credentials files; the CLI accepts external signers or hardware/OS key providers.

## 4. Implementation Slices

1. Envelope, key ids, deterministic encoding, and cryptographic test vectors.
2. Publish/sign/verify CLI and registry owner-key endpoints.
3. Transparency tree, proofs, and gossip/rollback detection.
4. Resolver policy, lockfile provenance, and rotation/revocation end-to-end tests.

## 5. Alternatives

| Option | Problem | Direction |
| --- | --- | --- |
| TLS plus checksums only | Leaves the registry as an unauditable trust root | Insufficient |
| Registry signs every package | Cannot distinguish registry and publisher identity | Reject |
| Publisher signing plus transparency | Verifies authorization and consistent history | Proposed |

## 6. Drawbacks and Risks

Key recovery and revocation are complex for users. Weak canonical encoding causes cross-implementation signature disagreement, and transparency logs add operational cost.

## 7. Compatibility and Migration

Legacy registries begin as explicit `checksum-only`; they cannot appear signed. The lockfile schema gains optional signature/proof identity without changing archive-checksum semantics.

## 8. Acceptance Gate

This RFC requires an independent verifier to reproduce signatures and inclusion proofs, passing rotation/revocation/rollback tests, and proof that secrets never enter logs or lockfiles before becoming `Accepted`.

## 9. Open Questions

- Which initial signature algorithm and long-term algorithm migration model should be used?
- Should provenance use a standard attestation format in the first release?
- How do offline environments carry tree heads and proof-freshness policy?

## 10. References

- [RFC 0013](./0013-registry-protocol-and-package-integrity.md).
