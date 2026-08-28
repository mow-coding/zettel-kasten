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
- Preserve `WOM`, `zet`, `ZET`, and `objet` as distinct product terms. A native
  Korean sentence may use the established Korean rendering `오브제`; it must
  not fall back to generic `object`, `객체`, or `오브젝트`. Use
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

This was a queued design requirement rather than a v0.4.10 release claim. In
the v0.4.11 worktree, the first migration step replaces legacy `제텔`, generic
object wording, generic relation buttons, and post-mint `폐기` wording in the
native approval surface with canonical `zet`, `objet`/`오브제`, `엣지`,
`발행`, and `퇴역` language. The same worktree now derives a small local-only
target preview from the already validated operation plan. Mint and promotion
show the zet filename, retirement shows the draft filename, edge work shows
both zet identities and the edge kind, and
zet–objet work shows the zet, objet id, and role. The writer re-derives the same
exact plan and target binding before mutation; a changed target still fails
closed. A title that is not already part of that operation's authenticated
plan is deliberately omitted rather than shown as if it were bound. Missing
bound identities fail before approval. Preview values are not written to the public binding document,
approval receipt, log, or machine details. Tests cover target drift, redacted
durable output, local-only display, spoofing controls, and every operation that
is actually open.

Unpublished-draft discard remains deliberately fixed closed in v0.4.11. This
release does not claim a native discard approval operation or its distinct
sentence; it preserves the `폐기` versus `퇴역` language rule for the later
discard writer. The closed command must not read a private target or mutate it.

Microsoft's Windows UI text guidance supports this structure: use one concise,
specific question about the person's objective, put decision-helping context
in supplemental text, and keep machine detail behind Task Dialog's progressive
disclosure control. WOM therefore keeps the exact human decision and safe
target identity in the primary surface, with machine hashes and codes in the
existing advanced section.

- https://learn.microsoft.com/en-us/windows/win32/uxguide/text-ui
- https://learn.microsoft.com/en-us/windows/win32/controls/task-dialogs-overview
- https://learn.microsoft.com/en-us/windows/win32/uxguide/ctrl-progressive-disclosure-controls
