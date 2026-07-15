# RFC 0018: Package Signing, Provenance, and Transparency

> Language: [中文](../../zh-CN/rfcs/0018-package-signing-provenance-and-transparency.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0018 |
| Title | Package Signing, Provenance, and Transparency |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-11 |
| Implementation | Implemented in `nomo-supply-chain`, registry publish/owner-key APIs, resolver trust policy, lockfile evidence, and the independent `nomo verify` CLI |
| Topics | package signing, provenance, transparency log, registry, trust policy |
| Related RFCs | [RFC 0008](./0008-canonical-package-identity-and-aliases.md), [RFC 0013](./0013-registry-protocol-and-package-integrity.md) |

---

## 1. Summary

Add a signature envelope over canonical id, version, archive checksum, and provenance for every release. Registries return verifiable inclusion proofs from an append-only transparency log. The resolver enforces project or organization trust policy instead of treating registry TLS as publisher identity.

## 2. Motivation

A checksum detects disagreement between metadata and downloaded bytes but does not prove who authorized a release or expose a registry presenting different histories to different clients. A real ecosystem needs key rotation, revocation, and audit boundaries.

## 3. Design

- A deterministically encoded signed object covers canonical package, version, archive checksum, manifest checksum, publisher key id, and optional provenance digest.
- Namespace owners explicitly register publisher public keys. Registry-token authentication and release-signing keys remain separate.
- The transparency log provides a signed tree head and inclusion proof for every release and owner-key event; clients cache heads and detect rollback.
- Trust policy supports `checksum-only`, `signed`, and `signed+transparent`. Public registries should ultimately default to the strongest tier; private registries configure it explicitly.
- Rotation and revocation are new log events. Locked artifacts are never silently replaced, while refetch applies current policy.
- Private keys never enter Nomo credentials files; the CLI accepts external signers or hardware/OS key providers.

## 4. Implementation

1. `nomo-supply-chain` defines the Ed25519 release envelope, canonical subject,
   provenance document, publisher key ids, transparency events, signed tree
   heads, and Merkle inclusion proofs. Serialization is deterministic and
   unknown fields are rejected.
2. `nomo publish --signer` streams only the canonical subject to an external
   signer and uploads the archive, provenance, and attestation separately.
   `nomo owner key add|revoke` manages publisher authorization. `nomo verify`
   is an independent archive/envelope/provenance verifier and requires an
   explicit `--log-key` for transparency proofs.
3. `checksum-only`, `signed`, and `signed+transparent` policies are parsed from
   manifests. The last policy requires explicit `trust.transparency-keys`; the
   resolver passes those pinned keys into transparency verification and caches
   tree heads to detect rollback or equivocation.
4. Lockfile entries retain publisher key id, subject/provenance digests, and
   transparency root/size. Tests cover deterministic vectors, key rotation and
   revocation, inclusion proofs, untrusted-log rejection, rollback, offline
   metadata, and signed registry archives.

## 5. Alternatives

| Option | Problem | Direction |
| --- | --- | --- |
| TLS plus checksums only | Leaves the registry as an unauditable trust root | Insufficient |
| Registry signs every package | Cannot distinguish registry and publisher identity | Reject |
| Publisher signing plus transparency | Verifies authorization and consistent history | Accepted |

## 6. Drawbacks and Risks

Key recovery and revocation are complex for users. Weak canonical encoding causes cross-implementation signature disagreement, and transparency logs add operational cost.

## 7. Compatibility and Migration

Legacy registries begin as explicit `checksum-only`; they cannot appear signed. The lockfile schema gains optional signature/proof identity without changing archive-checksum semantics.

## 8. Acceptance Gate

The implementation is accepted because the independent verifier reproduces
signatures and inclusion proofs; rotation, revocation, untrusted-log, and
rollback tests pass; and private keys are excluded from credentials, metadata,
provenance, envelopes, and lockfiles. Deployments still need an operational
transparency-log key-rotation and gossip policy.

## 9. Open Questions

- How should the initial Ed25519 log key be rotated and gossiped across public
  registries?
- Which standard attestation format should provenance adopt after schema v1?
- How should offline environments distribute tree heads and proof-freshness
  policy without weakening the manifest-pinned trust root?

## 10. References

- [RFC 0013](./0013-registry-protocol-and-package-integrity.md).
