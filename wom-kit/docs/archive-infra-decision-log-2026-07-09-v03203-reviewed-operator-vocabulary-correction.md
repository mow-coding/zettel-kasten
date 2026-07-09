# Archive Infra Decision Log - v0.3.203 Reviewed Operator Vocabulary Correction

Date: 2026-07-09
Release: v0.3.203
Status: accepted

## Context

v0.3.202 added the first broad `operator_vocabulary` surface, but the language
needed direct user review. The important rule is that AI operators must not
invent friendly Korean labels when the user has already chosen product or
operator wording.

## Decision

Keep confirmed product language separate from confirmed operator language.

Confirmed product examples include `node` as `노드`, `edge` as `엣지`, `tie` as
`타이`, `zet` for actual WOM records, and `zettel` for the abstract
zettelkasten idea.

Confirmed operator examples include `object_id` as `오브제 아이디`, `doctor` as
`검진`, `provider` as `외부 서비스`, `containment` as `포함 관계`,
`safe_preview` as `미리보기`, `approved_write` as `승인 후 쓰기`,
`external_report` as `공개용 문서`, and `private_working_note` as `비공개 문서`.

The `needs_user_translation` bucket remains present but empty, reserved for
future terms that genuinely need naming review.

## Consequences

- AI operators can show a reviewed Korean vocabulary without asking the user to
  re-translate already-set terms.
- Machine identifiers remain unchanged in JSON, receipts, schemas, CLI command
  names, and archive files.
- The guide is advisory for human-facing prose; it is not an archive migration
  and it does not enforce output wording.
