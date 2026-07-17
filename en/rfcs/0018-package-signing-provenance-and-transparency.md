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
| Implementation | Implemented in `nomo-supply-chain`, registry publish/owner-key APIs, resolver trust policy, lockfile evidence, the independent `nomo verify` CLI, dual-signed log-key rotation, signed-head gossip, and online/offline proof-freshness enforcement |
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
- A version-2 signed tree head binds the log id, issue time, signing key, and
  predecessor size/root. Log-key rotation is a monotonically activated event
  signed by both the previous and replacement keys and rooted in the original
  manifest pin.
- Clients compare independently obtained signed heads. A same-size root
  disagreement is equivocation; a newer head must provide a signed predecessor
  chain back to the cached or gossiped anchor.
- Proof freshness has separate online and offline maximum ages plus a bounded
  future-clock skew. Offline mode relaxes age only; it never relaxes the pinned
  trust root, rotation chain, inclusion proof, rollback, or equivocation checks.
- Trust policy supports `checksum-only`, `signed`, and `signed+transparent`. Public registries should ultimately default to the strongest tier; private registries configure it explicitly.
- Rotation and revocation are new log events. Locked artifacts are never silently replaced, while refetch applies current policy.
- Private keys never enter Nomo credentials files; the CLI accepts external signers or hardware/OS key providers.

## 4. Implementation

1. `nomo-supply-chain` defines the Ed25519 release envelope, canonical subject,
   provenance document, publisher key ids, transparency events, signed tree
   version-2 signed tree heads, dual-signed log-key rotations, and Merkle
   inclusion proofs. Serialization is deterministic and unknown fields are
   rejected.
2. `nomo publish --signer` streams only the canonical subject to an external
   signer and uploads the archive, provenance, and attestation separately.
   `nomo owner key add|revoke` manages publisher authorization. `nomo verify`
   is an independent archive/envelope/provenance verifier and requires an
   explicit `--log-key` for transparency proofs. It accepts repeatable
   `--gossip` inputs, can emit a shareable `--write-gossip` checkpoint, and
   exposes online/offline freshness and future-skew controls.
3. `checksum-only`, `signed`, and `signed+transparent` policies are parsed from
   manifests. The last policy requires explicit `trust.transparency-keys`; the
   resolver passes those pinned keys into transparency verification, validates
   configured gossip checkpoints, applies separate online/offline freshness
   limits, and writes both a private cached head and a shareable signed-head
   checkpoint.
4. Lockfile entries retain publisher key id, subject/provenance digests, and
   transparency root/size. Tests cover deterministic vectors, publisher-key
   rotation and revocation, dual-signed log-key rotation, inclusion proofs,
   untrusted-log rejection, rollback, gossip equivocation, online/offline proof
   freshness, offline metadata, and signed registry archives.

## 5. Alternatives

| Option | Problem | Direction |
| --- | --- | --- |
| TLS plus checksums only | Leaves the registry as an unauditable trust root | Insufficient |
| Registry signs every package | Cannot distinguish registry and publisher identity | Reject |
| Publisher signing plus transparency | Verifies authorization and consistent history | Accepted |

## 6. Drawbacks and Risks

Key recovery and revocation are complex for users. Weak canonical encoding causes cross-implementation signature disagreement, and transparency logs add operational cost.

## 7. Compatibility and Migration

Legacy registries begin as explicit `checksum-only`; they cannot appear signed.
The lockfile schema gains optional signature/proof identity without changing
archive-checksum semantics. New transparency bundles use signed-head schema 2;
schema-1 signatures are rejected because they do not bind log identity, issue
time, key lineage, or predecessor state. Existing cached size/root anchors
remain usable when a valid schema-2 history extends them.

## 8. Acceptance Gate

The implementation is accepted because the independent verifier reproduces
signatures and inclusion proofs; publisher and log-key rotation, revocation,
untrusted-log, rollback, gossip-equivocation, and online/offline freshness tests
pass; and private keys are excluded from credentials, metadata, provenance,
envelopes, and lockfiles. The production transparency-log operations gate is
complete.

## 9. Open Questions

- Which standard attestation format should provenance adopt after schema v1?

## 10. References

- [RFC 0013](./0013-registry-protocol-and-package-integrity.md).
