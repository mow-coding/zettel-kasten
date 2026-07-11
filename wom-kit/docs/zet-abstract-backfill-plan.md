# zet Abstract Backfill Plan

Status: implemented as read-only planning in v0.3.218

## Plain-Language Purpose

An archive-wide catalog can prove that every zet node was visited while still
reporting that some zets have no usable `abstract`, `gist`, `summary`,
`description`, or `overview` first read.

WOM-kit must not invent and write those missing abstracts automatically. An
abstract is a new interpretation of canonical content. It needs a visible
source version, a private proposal, and human review before any future write.

v0.3.218 adds the read-only half of that workflow:

```text
find gap -> read one canonical body -> pin exact file bytes -> prepare private proposal -> validate plan -> human review
```

No canonical zet is changed in this release.

## 1. Read One Selected zet

Use the id from a validated catalog page:

```powershell
archive read-zettel <archive-root> `
  --zettel-id <verified-zet-id> `
  --section body `
  --format json
```

For a non-redacted zet, `read-zettel` now returns:

- `integrity.file_sha256`: SHA-256 of the exact canonical file bytes;
- `integrity.body_sha256`: SHA-256 of the decoded body returned by
  `read-zettel`;
- `integrity.exact_file_bytes_hashed: true`.

The exact file hash binds a proposal to the version the AI or human actually
read. Hashes are suppressed for redacted zets.

## 2. Prepare A Private Proposal JSONL

Write one JSON object per line under:

```text
.wom-scratch/abstract-backfill/<private-name>.jsonl
```

Each row follows
`wom-kit/schemas/zet-abstract-backfill-proposal.schema.json`:

```json
{"schema":"wom-kit/zet-abstract-backfill-proposal/v0.1","zettel_id":"zet_example","expected_file_sha256":"sha256:<64-hex>","abstract":"A compact reviewed first read.","generation_mode":"ai_assisted","basis":"canonical_zet_body"}
```

`generation_mode` is `human_written` or `ai_assisted`. It records how the
candidate was prepared; it does not prove review. `basis` must remain
`canonical_zet_body`.

The proposal is a private AI working file. It can contain zet ids and proposed
abstract text. Never commit it or treat it as canonical knowledge.

## 3. Validate Without Writing

```powershell
archive zet-abstract-backfill-plan <archive-root> `
  --proposal .wom-scratch/abstract-backfill/<private-name>.jsonl `
  --max-items 500 `
  --dry-run `
  --progress `
  --format json
```

Alias: `abstract-backfill-plan`.

The planner checks each row against the current archive:

- proposal schema and allowed fields;
- safe unique zet id;
- exact canonical file SHA-256 match;
- readable canonical frontmatter identity and status;
- no existing `abstract` key or compatibility first-read field;
- already-normalized single-line abstract text, compact length, and
  private-locator/secret-like rejection;
- byte-preserving insertion after the YAML opening delimiter;
- semantic proof that only the new `abstract` field changes.

The proposal is limited to 64 MiB, each line to 1 MiB, and a batch to at most
5,000 rows. A real 8,000-plus gap set should therefore be reviewed in at least
two bounded batches.

## Output And Privacy

The planner returns row indexes, status, safe counts, candidate file hashes,
abstract hashes, the exact proposal SHA-256, and a plan digest. It does not
return zet ids, titles, paths, bodies, proposed abstract text, or the private
proposal filename.

The planner reads selected canonical zet bodies to verify exact insertion but
does not echo them. It calls no model or provider and writes no file, receipt,
zet, objet, map, index, or external database row.

## Honest Boundary

v0.3.218 does not implement the approved revision write. A green plan means the
private candidates are bound to current canonical bytes and are ready for human
review. It does not mean the abstracts are true, complete, stylistically good,
or approved.

Do not hand-edit thousands of canonical files after this preview. A separate
approval-gated writer must re-check the proposal hash and every canonical file
hash, insert only `abstract`, roll back the full batch on failure, and record
before/after/abstract hashes in a revision receipt.
