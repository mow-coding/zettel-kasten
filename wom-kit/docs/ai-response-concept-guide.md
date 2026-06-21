# AI Response Concept Guide

Status: v0.3.104 read-only concept, operational terminology, and material-clue routing checkpoint
Date: 2026-06-17

This guide tells an AI runtime how to explain core WOM ideas when a beginner
gets stuck during intake, object-storage setup, or connection review:

```text
sha256 identity vs location URL
manifest vs zet
objet -> derived text -> zet
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
does not silently force containment into unrelated edge types.

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
operational_terms
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

## 4. Operational Terms

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

## 5. What The AI Should Ask Next

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
  --source notion --dry-run` to create a local request queue for a future
  credential-bounded adapter.
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

## 6. Overclaim Guardrails

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

## 7. Relation To Existing Docs

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

It does not change those underlying implementation boundaries.

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
