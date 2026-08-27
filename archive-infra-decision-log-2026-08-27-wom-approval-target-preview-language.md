# Decision: approval target previews use WOM product language

Date: 2026-08-27

## Context

Native approval prompts can currently ask a person to publish, discard, link,
or create an edge without making the exact subject sufficiently inspectable.
The user wants a no-custom-UI path that shows what the decision concerns, while
preserving WOM's already chosen philosophical language.

## Decision

- Start from natural user-facing sentences, not dictionary translations or
  generic CRUD labels.
- Preserve `WOM`, `zet`, `ZET`, and `objet` as distinct product terms. Use
  `이 zet를 정본으로 발행할까요?` for the Korean mint decision; do not flatten
  a zet into a generic file or item, and do not use `ZET` for a local draft.
- A mint or discard decision must identify the exact zet or draft and provide a
  read-only local detail/preview route before approval.
- Keep unpublished-draft `폐기` separate from post-publication draft `퇴역`.
  Their prompts must state the different consequence.
- An edge or link decision must identify both endpoints, the proposed relation,
  and the evidence for suggesting it. Show the human-readable `관계 의미`
  before the internal `링크 타입`, keep `발견 방식` separate, and do not
  disguise weak evidence as a confident relation.
- Ordinary CLI/JSON output and public logs remain content-free. Sensitive title,
  path, body excerpt, and relation evidence belong only in the explicitly
  opened local preview surface.
- Keep product-facing language separate from implementation identifiers: CLI
  commands, JSON fields, schemas, and internal operation names stay stable
  unless a separate compatibility decision changes them.

## Consequences

This is a queued design and implementation requirement, not a v0.4.10 release
claim. Its implementation must reuse the exact approval binding so the preview
cannot describe one target while the approved writer acts on another. Tests
must cover target drift, redacted default output, local detail disclosure, and
the distinct mint/discard/retire/link/edge sentences. The implementation must
also replace the existing `제텔` approval labels with canonical `zet` and extend
the product-language gate to cover native UI strings, because the current gate
checks public Markdown but does not detect Python approval-label drift.
