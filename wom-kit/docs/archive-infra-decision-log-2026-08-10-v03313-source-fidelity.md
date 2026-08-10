# Decision Log: v0.3.313 Source Fidelity

Date: 2026-08-10

## Context

v0.3.312 could bind an AI draft's candidate body hash while having no evidence
that the candidate preserved the manifested source requested by the operator.
The reported case was stopped before writing, so this is a pre-write contract
defect with zero verified data loss.

## Decisions

- Source fidelity is a separate contract with closed modes `verbatim`,
  `faithful_summary`, and `sanitized_derivative`.
- New AI drafts require a manifested local content-addressed objet, audience,
  dry-run plan, exact replay hash, and attributed human approval.
- Declared AI provenance cannot downgrade to a human or absent creation mode.
- `private_self` verbatim preserves private personal data without silent
  redaction. Credential secrets remain blocked.
- `utf8_newlines_lf` converts newline encoding only. It is not byte-exact and
  performs no trimming, Unicode normalization, or BOM removal.
- Verbatim equality is verified from an explicit raw draft-body byte region.
  Summary and derivative semantics are human-reviewed, never machine-proven.
- Draft and receipt publication is create-only and idempotent. Conflicts are
  retained and blocked, not overwritten or deleted.
- Mint re-verifies source authority and body-region equality and binds the
  current reviewed plan into canonical metadata and its receipt.
- The creation plan binds the complete non-recursive frontmatter authority and
  closed fidelity evidence. A separate review-binding digest binds reviewer,
  archive, draft, body, and approved creation plan without making the reviewer
  part of the pre-review candidate.
- The private receipt uses an exact closed schema. Its replay-bound timestamp
  is `candidate_created_at`, not a claimed review wall-clock time, and it omits
  unverifiable recursive draft-digest claims.
- Credential, private-locator, and private-source-authority failures return
  content-free envelopes. Recursive keys and values are both inspected, and
  fidelity `draft_creation` metadata has an exact closed key set.
- Existing zets are not migrated. Legacy AI drafts require an explicit
  attributed review; no past fidelity mode is inferred. Historical `ai:` and
  MCP AI provenance are classified as AI rather than allowed to downgrade to
  human.
- Audience metadata is not access control and does not authorize transport or
  sharing.

## Consequences

Existing human-written workflows remain compatible. New AI automation must
supply explicit source-fidelity and approval inputs. The runtime guidance now
distinguishes credential secrets, private personal source data, and separately
reviewed shared derivatives. No live source, private archive state, provider transport,
or external share is part of this release proof.
