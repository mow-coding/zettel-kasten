# Archive Infra Decision Log - v0.3.202 Operator Vocabulary Translation

Date: 2026-07-09
Release: v0.3.202

## Context

After adding the `ai-start-here` signpost in v0.3.201, the next gap was the
human-facing language an AI operator should use while helping a beginner run
WOM. Existing translation support covered edge types, connection mechanisms,
lifecycle fragments, and git/infrastructure terms, but not the broader everyday
WOM operator vocabulary.

During review, the user clarified that previously confirmed product-language
terms must be treated as confirmed, not "almost confirmed", and that unreviewed
functional words must not receive invented Korean product names. The user also
confirmed that `zettel` points to the abstract zettelkasten idea while actual
WOM records should be called `zet`, and confirmed `frontmatter` as
`초록 데이터`.

## Decision

Add an `operator_vocabulary` topic to `archive ai-response-concept-guide`.

The topic separates confirmed product/operator language from future
user-translation-review items. Confirmed terms include `WOM`, `zet`, `ZET`, `objet`,
`mint` as `발행하다`, `receipt` as `영수증`, `canonical` as `정본`, `node` as
`노드`, `edge` as `엣지`, `tie` as `타이`, and the reviewed operator terms `archive` as `아카이브 폴더`,
`archive_root` as `아카이브 최상위 폴더`, `AGENTS.md` as `AI 메뉴얼`,
`runtime_context` as `인수인계 문서`, `ai_start_here` as `AI 스타팅 메뉴얼`,
`operational_context` as `작업기록`, `capabilities` as `도구 설명서`,
`draft` as `초안`, `inbox` as `임시저장소`, and `frontmatter` as
`초록 데이터`. The second reviewed pass also confirms functional operator terms
including `object_id` as `오브제 아이디`, `doctor` as `검진`, `provider` as `외부 서비스`,
`containment` as `포함 관계`, `safe_preview` as `미리보기`,
`approved_write` as `승인 후 쓰기`, `external_report` as `공개용 문서`, and
`private_working_note` as `비공개 문서`.

## Consequences

- AI operators have a read-only lookup that preserves confirmed WOM wording and
  preserves reviewed operator wording before falling back to future naming review.
- Machine terms remain stable and unchanged in JSON, receipts, and CLI command
  names.
- The guide remains advisory: it shapes human-facing prose but does not enforce
  output wording.
