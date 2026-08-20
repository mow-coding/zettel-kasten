# Source Fidelity And Private Verbatim Preservation

Status: v0.4.0 exact-human and private session-evidence contract; v0.3.313 baseline preserved

## The problem this contract closes

A draft could previously carry a source reference while its body silently
omitted part of the referenced material. The body hash proved only that WOM
replayed the already-shortened candidate. It did not prove that the candidate
preserved the source requested by the archive owner.

This release separates three concerns that must not be collapsed:

1. credential secrets, which must not enter a zet;
2. private personal source data, which may need complete private preservation;
3. a separately reviewed derivative intended for another audience.

Existing zets and receipts are not rewritten. The stricter contract applies to
new AI-assisted and AI-generated drafts. Human-written legacy routes remain
compatible. A request that declares AI `created_by` or `assisted_by` provenance,
or carries non-empty `local_ai_sessions` evidence, cannot downgrade to a human
or absent creation mode; it fails as
`ai_provenance_requires_ai_creation_mode`.

## Closed modes

Every new AI draft declares one mode.

- `verbatim` preserves one reviewed source region in full. It is available only
  for a personal archive and `private_self` audience.
- `faithful_summary` binds the source and exact candidate reviewed by a human.
  WOM does not claim that a digest proves semantic faithfulness.
- `sanitized_derivative` binds a new reviewed candidate while leaving the
  private source unchanged. It neither shares nor exports anything.

The source authority is a manifested local content-addressed objet. Mutable
paths are not durable evidence and are never copied into public output or
receipts.

## What verbatim means

`utf8_newlines_lf` converts CRLF and lone CR to LF and makes no other text
transformation. It does not trim leading or trailing whitespace, collapse final
newlines, normalize Unicode, change case, or remove a BOM. The receipt records
`byte_exact: false` because newline conversion is a real transformation.

WOM records the raw source digest, transformed source-region digest, byte
offset and length within the raw draft body, current body digest, archive and
draft identity, mode, audience, and reviewed plan digest. It records no source
text or private source path. A verifier reads the draft body as raw UTF-8 bytes;
the ordinary zettel parser's whitespace cleanup is not evidence for this
contract.

The receipt calls the replay-bound draft timestamp `candidate_created_at`.
It does not present that timestamp as the wall-clock time when the human
reviewed or approved the candidate; reviewer identity and approved digests are
the durable approval evidence. A separate review-binding digest binds that
reviewer to the archive, draft, candidate body, and reviewed creation plan.

Only verbatim region equality may be reported as mechanically verified.
Summary and derivative modes always report semantic machine verification as
false and require a human review of the exact candidate digest.

## Approval and publication

The workflow is two reviewed replays:

1. Capture the source as an approved content-addressed objet.
2. Run `create-draft --dry-run` with mode, audience, and objet id.
3. Review the proposed draft and content-free fidelity plan.
4. Replay with `--approve`, reviewer, expected body hash, and expected fidelity
   plan hash. Draft and receipt publication are create-only and idempotent.
5. Run `mint-zet --dry-run`. WOM re-verifies the source authority and raw body
   region and returns the current publication plan.
6. Replay mint with a reviewer and the exact current fidelity plan hash.

An edit outside an intact verbatim region may be reviewed through a new mint
plan. A source change or source-region change blocks publication. Conflicting
existing files are never overwritten or deleted as repair.

Legacy AI drafts do not acquire a guessed mode. They need an attributed legacy
fidelity review before mint. This is a compatibility path, not retrospective
proof of verbatim preservation.

CLI create uses `--source-fidelity`, `--fidelity-audience`, and
`--fidelity-source-object-id`; its approved replay adds
`--draft-approved-by`, `--expected-body-sha256`, and
`--expected-source-fidelity-plan-sha256`. Approved mint also requires the
current fidelity-plan hash. MCP `create_draft_zettel` exposes the matching
dry-run inputs while binding its own AI runtime identity, but v0.4.0 rejects
`approved: true` with `exact_human_approval_cli_required`; MCP cannot display
the local native dialog or supply a claim. MCP `mint_zettel_check` remains
preview-only.

## v0.4.0 Session Evidence And Approval Link

`source-fidelity-session-evidence --dry-run|--approve` can bind reviewed
private UTF-8 session evidence without turning a mutable path or raw session
reference into public authority. The source must be under the fixed private
session-evidence scratch boundary. Its role, producer kind, produced/captured
times, exact byte digest, and optional input-provenance digests form the plan;
ordinary output and the receipt return no source text, path value, or raw
session ref.

Approved session evidence and AI draft creation use the exact-human sequence:

```text
native TaskDialog -> authenticated durable started claim -> writer -> workflow finalize
```

There is no issued approval receipt with a time-to-live. The writer revalidates
the current exact plan and target binding immediately before mutation, and the
workflow alone finalizes the claim. A surviving `started` state is unknown and
must be reconciled rather than retried automatically.

The strict source-fidelity receipt remains immutable. A separate create-only,
HMAC-authenticated approval-link receipt binds it to the exact approval claim
after all source-fidelity evidence is verified. Reading or verifying that link
requires the archive authentication key and a matching authenticated
`succeeded` claim. Only `effect=created` proves that the approved invocation
created the source operation. `effect=already_present_exact` records a later
review and does not rewrite or silently upgrade historical evidence.

## Privacy and authority boundary

Names, contact details, dates, and conversation order are private personal data,
not credential secrets. Under an explicit private verbatim request WOM does not
silently mask them. PATs, API keys, passwords, private keys, bearer tokens, and
similar credentials block the candidate before writing and remain in a
human-controlled secret store.

An `audience` field documents intent; it is not an ACL and never authorizes a
share. External publication remains a separate approval and transport action.
Failures return fixed reason codes and counts or digests only, never source
excerpts, private paths, provider URLs, or raw exceptions.
Human reviewer attribution remains explicit in approved draft and mint
evidence.

## Standards used narrowly

This contract borrows a small set of established principles rather than
claiming to implement whole standards:

- [W3C PROV-O](https://www.w3.org/TR/prov-o/) models the source and derivative
  as separate entities connected by derivation activity.
- [RFC 9530](https://www.rfc-editor.org/rfc/rfc9530.html) applies digests to
  exact byte sequences and supplies no hidden content canonicalization.
- [BagIt, RFC 8493](https://www.rfc-editor.org/rfc/rfc8493.html) treats payload
  as uninterpreted octets verified by a manifest.
- [OAIS 2024](https://public.ccsds.org/Pubs/650x0m3.pdf) distinguishes
  provenance, fixity, context, reference, and access-rights information.
- [in-toto Statement v1](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md)
  and [SLSA provenance v1.2](https://slsa.dev/spec/v1.2/build-provenance)
  motivate binding source, candidate, action, and invocation evidence.

Digests prove equality to reviewed bytes, not truth, authorship, semantic
quality, or permission to disclose them.
