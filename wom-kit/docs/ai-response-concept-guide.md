# AI Response Concept Guide

Status: v0.3.202 WOM operator vocabulary translation checkpoint
Date: 2026-07-09

Previous checkpoint: Status: v0.3.104 read-only concept, operational terminology, and material-clue routing checkpoint

This guide tells an AI runtime how to explain core WOM ideas when a beginner
gets stuck during intake, object-storage setup, or connection review:

```text
sha256 identity vs location URL
manifest vs zet
objet -> derived text -> zet
WOM operator vocabulary translation layer
operational terminology translation layer
material-clue routing after body locator omission
link-type model-gap escalation for structural containment
```

It is not a new adapter, importer, uploader, or proof system. It is a read-only
language guide for safer human-facing answers. v0.3.102 added an operational
term dictionary so AI responses can translate terms such as `derived_from`,
`references`, and `supersedes` before asking a human to decide. v0.3.103 added
safe routing for Notion material links when provider locators were already
removed from imported zettel bodies. v0.3.104 adds an import material-clue audit
route so an AI can check whether omitted-locator imports preserved or can
recover a safe material clue. v0.3.123 adds a model-gap escalation guard and a
`contains` explanation for structural child page/database containment, so an AI
does not silently force containment into unrelated edge types. v0.3.165 adds a
git/infrastructure terminology translation layer so an operator AI can look up
everyday phrasings for words such as fetch, checkout, pin, and manifest before
explaining version or infrastructure state to a human. v0.3.202 adds a broader
WOM operator vocabulary layer for words an AI uses while helping a human operate
an archive: archive, start-here map, zet, draft, canonical copy, objet, derived
text, receipt, mint, retire, reconcile, doctor, validate, edge, tie, credential
reference, vault, provider locator, and object storage.

## Command

```bash
archive ai-response-concept-guide <archive-root> --topic all --locale ko-KR --dry-run --format json
```

Aliases:

```text
ai-concept-guide
wom-concept-guide
```

Topics:

```text
all
sha256_identity
manifest_vs_zet
three_layers
operator_vocabulary
operational_terms
git_infra_terms
```

The command writes nothing and reads no source bodies. It returns structured
explanation cards, safe routing hints, and overclaim guardrails an AI runtime
can use while helping a beginner.

`--locale` currently supports Korean and English human-facing phrases through
`ko-KR` and `en-US`. The internal WOM identifiers stay stable in English; the
selected phrase is what the AI should say first.

## 1. First Answer Pattern

When the human asks:

```text
Do I need to upload to R2 first?
If the file location changes, will the zet path break?
Is this like a Google Drive URL?
```

Answer in this order:

1. WOM identifies source objets by content fingerprint, not by a current folder
   path or cloud URL.
2. A `sha256:<hex>` value names the bytes. If the same bytes move from local
   disk to R2, the identity stays the same.
3. A location, such as a local candidate or external store label, only says
   where a copy may be found.
4. A `zet` should cite the object id or derived-text record, not hard-code a
   private path or provider URL.
5. Do not claim upload, availability, or remote recovery unless a receipt or
   future adapter has actually verified it.

Short beginner script:

```text
WOM is not pointing at "where the file happens to sit today."
It is pointing at "which exact bytes this was."
The sha256 is the fingerprint. R2 or a local folder is only a shelf where a copy
can live. So you can register the fingerprint first, upload later, and then add
better location or receipt evidence later.
```

Korean beginner script:

```text
WOM은 "지금 파일이 어디 폴더에 있나"보다 "이 파일이 정확히 어떤 바이트인가"를 먼저 봅니다.
sha256은 파일의 지문이고, R2나 로컬 폴더는 그 파일 사본이 놓인 선반입니다.
그래서 지문을 먼저 등록하고, 업로드는 나중에 해도 zet의 참조 자체는 깨지지 않습니다.
다만 실제로 R2에 올라갔다고 말하려면 별도 업로드 영수증이나 검증 기록이 필요합니다.
```

## 2. The Address Book Analogy

Use this analogy carefully:

```text
sha256 object id = fingerprint of the bytes
object manifest = address book / catalog for known objects
location = one possible shelf or address where a copy might be found
zet = human-authored memory that cites the fingerprint
```

The analogy should not overclaim. An address book entry can be stale, incomplete,
or only a reviewed label. A safe `store_ref` is not the same as a verified
download URL.

Say:

```text
The manifest is like a catalog: "this object exists, here is its fingerprint,
and here are safe labels for where it may live."
```

Do not say:

```text
The manifest proves the remote file is definitely online.
The zet stores the R2 path.
The store_ref is a URL.
```

## 3. Three Layers

Explain the layers in this order:

```text
objet        -> original source evidence
derived text -> extracted/OCR/transcribed readable text from an objet
zet          -> human-approved memory, summary, decision, or connection
```

### Objet

An `objet` is original source material. It may be a PDF, image, audio file,
Notion snapshot JSON, exported document, attachment, or another source file.

The important claim is:

```text
This object id identifies these exact source bytes.
```

### Derived Text

Derived text is readable text produced from an objet by a parser, OCR, ASR,
vision model, or other extractor.

The important claim is:

```text
This text came from that source object, by this tool/method/version, with this
review status.
```

Derived text helps search and drafting, but it does not replace the original
objet.

### zet

A `zet` is human-approved archive memory. It can summarize, interpret, connect,
or decide based on source material.

The important claim is:

```text
This is the human's durable note or conclusion, and it cites its evidence.
```

A `zet` should cite objets and derived-text records. It should not become the
only copy of the evidence.

## 4. WOM Operator Vocabulary

When the AI is helping a person operate WOM, it should use everyday Korean
first and keep the internal term in backticks only when precision matters.

Use this lookup:

```bash
archive ai-response-concept-guide <archive-root> --topic operator_vocabulary --locale ko-KR --dry-run --format json
```

Core groups:

| Internal term | Beginner Korean |
| --- | --- |
| `archive` | 보관함 / 아카이브 |
| `archive_root` | 보관함 폴더 |
| `AGENTS.md` | AI 작업 지침 |
| `runtime_context` | 처음 상태 확인 |
| `ai_start_here` | 첫 안내판 / 시작 지도 |
| `operational_context` | 현재 작업 맥락 |
| `capabilities` | 사용 가능한 도구 목록 |
| `zet` | 정식 메모 / 기억 조각 |
| `draft` | 초안 |
| `inbox` | 초안함 |
| `canonical` | 정식본 |
| `frontmatter` | 문서 앞 메타데이터 |
| `source_refs` | 출처 참조 |
| `objet` | 원본 자료 / 오브제 |
| `object_id` | 자료 지문 |
| `derived_text` | 추출 텍스트 |
| `manifest` | 자료 목록표 |
| `source_map` | 출처 지도 |
| `receipt` | 작업 영수증 |
| `dry_run` | 미리보기 |
| `approve` | 승인 실행 |
| `mint` | 정식 발행 |
| `retire` | 정리 종료 |
| `reconcile` | 대조해서 맞추기 |
| `doctor` | 건강검진 |
| `validate` | 엄격 검사 |
| `privacy_scan` | 공개 전 민감정보 점검 |
| `node` | 점 / 항목 |
| `edge` | 연결선 |
| `tie` | 관계 / 이어짐 |
| `link_type` | 연결 종류 |
| `source_mechanism` | 연결이 발견된 방식 |
| `relationship_meaning` | 사람에게 의미 있는 관계 |
| `provider` | 외부 서비스 |
| `adapter` | 연결 어댑터 |
| `credential_ref` | 비밀값 이름표 |
| `secret` | 비밀값 |
| `vault` | 비밀 금고 |
| `provider_locator` | 외부 서비스 위치값 |
| `object_storage` | 대용량 원본 보관소 |

Preferred short phrases:

```text
먼저 미리보기로 확인해볼게요.
확인되면 승인 실행으로 실제 기록합니다.
비밀값이나 원본 본문은 읽지 않고 상태만 확인합니다.
지금 상태를 짧게 정리하면 이렇습니다.
남은 일은 이것입니다.
```

Avoid raw jargon in human-facing answers:

```text
민트하겠습니다.
리컨실하면 됩니다.
매니페스트가 증명합니다.
프로바이더 로케이터를 zet에 넣으면 됩니다.
드라이런 결과니까 이미 처리됐습니다.
```

## 5. Operational Terms

When the AI discusses reviewed connections, it should translate operational
terms before showing the internal identifier.

Examples:

| WOM term | Beginner phrase |
| --- | --- |
| `derived_from` | "This note was made from that source." |
| `references` | "This note points to or refers to that one." |
| `supersedes` | "This newer note replaces the older one." |
| `semantic` | "These are meaningfully related, but the exact relation still needs a human name." |
| `contains` | "This note or page structurally contains that child page, database, or view." |

In Korean locale, the same entries return phrases such as:

```text
이 메모는 저것으로 만들어졌다.
이 메모가 저것을 가리킨다 / 참고한다.
이 새 메모가 옛 메모를 대체한다.
```

The guide also separates:

- `source_mechanism`: how a connection was found, such as a Notion synced block
  or internal URL;
- `relationship_meaning`: what the connection means to the human archive.

This matters because both synced blocks and internal URLs can currently map to
`semantic`. That does not mean the source mechanisms are identical. It means
WOM is deliberately keeping provider mechanics separate from durable
relationship meaning until a human names the tie.

For beginner-facing answers, the guide recommends bundling near-overlaps:

- `material` and `derived_from` can be explained first as source material;
- `semantic` and `references` can be explained first as meaning/reference links;
- `contains` should be explained as structural nesting, not as source material,
  view-query membership, inheritance, or a loose reference;
- `supersedes` should be used for version chains where a newer zet replaces an
  older one.

If a captured relation does not fit the active WOM edge vocabulary, the AI
should say that a model decision is needed. It should not silently map
structural containment to `view_query`, `references`, `material`, or
`inherited_by` just because those edge types already exist.

## 6. Git and Infrastructure Terms

When an AI operator explains version or infrastructure state to a human, it must
translate git/infrastructure jargon into everyday language and keep the exact
term in parentheses or in the logs only. This layer is complementary to the WOM
operational-term layer in section 5: it covers git/infra words (fetch, checkout,
commit, branch, and the like), which share no term keys with the section-4 edge,
lifecycle, and connection vocabulary. Where a word such as `manifest` also
appears as WOM vocabulary (section 2), both treatments frame it the same way —
a catalog of objects and their fingerprints — so they reinforce rather than
contradict each other.

Look it up with:

```bash
archive ai-response-concept-guide <archive-root> --topic git_infra_terms --locale en-US --dry-run --format json
```

| Git/infra term | Beginner phrase |
| --- | --- |
| `fetch` | "The update files arrived, but the update button has not been pressed yet." |
| `checkout` | "Press the update button so the files you see become that chosen version." |
| `pin` | "A saved bookmark to a specific version." |
| `manifest` | "The list of which files exist and their fingerprints." |
| `hash` | "A fingerprint of the exact content." |
| `commit` | "One saved snapshot of the files." |
| `tag` | "A friendly name stuck onto one saved snapshot." |
| `branch` | "A separate line of work." |
| `HEAD` | "The version your files are currently on." |
| `remote` | "The shared copy kept somewhere else." |
| `mirror` | "A full local copy kept in step with the shared store." |
| `clone` | "Making your own full copy for the first time." |
| `diff` | "A view of what changed between two versions." |
| `staged` | "Changes set aside as ready to save, but not saved yet." |
| `rebase` | "Replaying your changes on top of a newer starting point." |
| `stash` | "Tucking unfinished changes aside for later." |

Canonical worked examples:

```text
the update files arrived but the update button hasn't been pressed yet (fetched, not checked out)
a saved bookmark to a specific version (a pin)
the list of which files exist and their fingerprints (the manifest)
```

This governs human-facing prose only. Machine, JSON, and receipt output stays
exact and unchanged. WOM does not validate or enforce plain-language output; it
is guidance the operator AI applies while writing.

## 7. What The AI Should Ask Next

When the human is unsure about order, ask one small question:

```text
Are we trying to register known object ids now, verify/upload the bytes now, or
draft human zets from already registered evidence?
```

Then route safely:

- Recover Notion zet-to-objet material candidates after imported zettel bodies
  no longer contain provider locators: use
  `notion-objet-source-map-link-plan` with source maps and optional
  download/retrieval ledgers.
- Audit imported Notion zettels after provider locator omission: use
  `notion-objet-import-clue-audit` before deciding whether a source-map
  candidate, older body-locator route, or future import-time preservation fix
  is needed.
- Index or plan remaining body-locator matches: use `notion-objet-link-index`
  or `notion-objet-link-plan` only when imported zettels still contain
  provider locator text that can be fingerprinted.
- Plan Notion structural containment and other connection evidence: use
  `connection-import-plan --source notion --connection-kind all --dry-run`
  before creating durable edges.
- Plan nested Notion child-page recovery after database-row import: use
  `notion-nested-tree-plan --tree workbench/notion-nested-tree.sample.json
  --source notion --dry-run` so missing parent chains are reported instead of
  guessed.
- Package missing Notion ancestors reported by nested-tree planning: use
  `notion-ancestor-crawl-plan --tree workbench/notion-nested-tree.sample.json
  --source notion --scope-generation-id DB1 --dry-run` to create a scoped
  local request queue for a future credential-bounded adapter. If the target is
  a generation-unknown untraceable leaf, prefer `--scope-leaf-ref`,
  `--scope-root-ref`, or `--scope-ancestor-ref`; generation-id scope only
  matches requests that already carry affected generation ids.
- Preview the future Notion ancestor fetch adapter contract: use
  `notion-ancestor-fetch-adapter-execution-contract --tree
  workbench/notion-nested-tree.sample.json --source notion --scope-generation-id
  DB1 --dry-run` before a scoped live run.
- Run the first local Notion ancestor structure fetch after credential approval:
  use `notion-ancestor-fetch-adapter-run --tree
  workbench/notion-nested-tree.sample.json --output
  workbench/notion-ancestor-result.live.json --source notion
  --scope-ancestor-ref page:<32hex> --approval-decision approve_once
  --approval-receipt <receipt> --dry-run|--approve`. The live fetch subject is
  a WOM local credential-bounded adapter process; the AI chat runtime must not
  hand-roll provider crawling or receive credential values. The run writes only
  a sanitized ancestor fixture plus a non-secret receipt and still does not read
  page titles, page bodies, comments, or media bytes.
- Preview the future Notion media byte fetch adapter contract: use
  `notion-media-fetch-adapter-execution-contract --tree
  workbench/notion-nested-tree.sample.json --source notion --scope-leaf-ref
  page:fake:db2-nested-live-log --dry-run` when nested leaf pages may contain
  images or files whose bytes cannot be proven from local metadata alone.
- Verify a sanitized media result fixture after a future adapter run: use
  `notion-media-result-verification-plan --media-result
  workbench/notion-media-result.sample.json --source notion --dry-run`.
- Build a nested tree fixture from reviewed Notion block mirror metadata: use
  `notion-block-mirror-tree-fixture-plan --mirror
  workbench/notion-block-mirror.sample.json --source notion --dry-run`.
- Merge sanitized ancestor results and replan: use
  `notion-ancestor-merge-plan --tree workbench/notion-nested-tree.sample.json
  --ancestors workbench/notion-ancestor-result.sample.json --source notion
  --dry-run`.
- Verify a client nested-tree issue from sanitized local fixtures: use
  `notion-client-issue-verification-plan --tree
  workbench/notion-nested-tree.sample.json --ancestors
  workbench/notion-ancestor-result.sample.json --source notion --dry-run`.
- Request the minimal sanitized fixtures needed for client verification: use
  `notion-client-fixture-request-plan --source notion --dry-run`.
- Register known external hashes: use `prehashed-objet-ledger`.
- Register already extracted text: use `derive-text capture`.
- Check extraction completeness: use `derive-text coverage`.
- Explain local/remote object lookup: use `resolve-objet-ref` or
  `presigned-url-plan --dry-run`.
- Upload/sync bytes: future work unless a later release explicitly adds an
  approval-gated adapter.
- Draft/mint zets: only after the source/derived evidence and human intent are
  clear.

The CLI returns the same routing in `safe_routing` so a terminal-capable AI can
pick the next safe command without inventing a live upload or provider action.

## 8. Overclaim Guardrails

The AI must not say:

- "The file is safe in R2" unless a real upload/verification receipt exists.
- "The URL is the identity" because the identity is the content hash.
- "Derived text is the original" because derived text is only a representation.
- "The zet contains the file" because the zet should cite the source object.
- "The child database is basically a `view_query` or `references` edge" because
  structural containment has its own `contains` meaning.
- "The manifest row proves availability" when it only records a reviewed object
  id and safe location labels.

The AI may say:

- "The identity is stable if the bytes are unchanged."
- "The location can change while the object id stays the same."
- "Upload evidence and location evidence can be added later."
- "A store label is safe to show; raw paths, provider URLs, account ids, and
  tokens are not."

## 9. Relation To Existing Docs

This guide rephrases existing model documents for AI-human conversation:

- [Source Object Storage Policy](source-object-storage-policy.md)
- [Text Provenance Hierarchy](text-provenance-hierarchy.md)
- [Notion Page Snapshot Model](notion-page-snapshot-model.md)
- [Derived Text Capture](derived-text.md)
- [Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md)
- [Connection Edge Intelligence Plan](connection-edge-intelligence-plan.md)
- [Zettel Edge Batch](zettel-edge-batch.md)
- [Notion Objet Import Clue Audit](notion-objet-import-clue-audit.md)
- [Notion Objet Source Map Link Plan](notion-objet-source-map-link-plan.md)
- [Notion Nested Tree Plan](notion-nested-tree-plan.md)
- [Notion Ancestor Crawl Plan](notion-ancestor-crawl-plan.md)
- [Notion Ancestor Fetch Adapter Execution Contract](notion-ancestor-fetch-adapter-execution-contract.md)
- [Notion Media Fetch Adapter Execution Contract](notion-media-fetch-adapter-execution-contract.md)
- [Notion Media Result Verification Plan](notion-media-result-verification-plan.md)
- [Notion Block Mirror Tree Fixture Plan](notion-block-mirror-tree-fixture-plan.md)
- [Notion Ancestor Merge Plan](notion-ancestor-merge-plan.md)
- [Notion Client Issue Verification Plan](notion-client-issue-verification-plan.md)
- [Notion Client Fixture Request Plan](notion-client-fixture-request-plan.md)

It does not change those underlying implementation boundaries.

The behavioral norms an operator AI applies while running WOM — provenance
fidelity (record the source the human actually encountered, do not silently
substitute a "more authoritative" one), enumerating available tools before
declaring a task impossible, and carrying already-established/approved state
instead of re-asking — live in the AI-Operator Discipline section of the runtime
surfaces (the `AGENTS.md` templates, the runtime skill, and
`wom-ai-runtime-skill-plugin-layer.md`), with the source-substitution axis
detailed in [Text Provenance Hierarchy](text-provenance-hierarchy.md). Those are
guidance the operator AI applies; this command validates nothing and enforces
nothing.

## Closed Actions

`ai-response-concept-guide` does not:

- read source bytes,
- read derived-text bodies,
- write object manifests,
- write derived-text records,
- write receipts,
- write edges,
- draft zets,
- mint zets,
- upload objects,
- call providers,
- read secrets,
- echo source filenames, local absolute paths, provider URLs, account ids,
  emails, tokens, or secret values.
