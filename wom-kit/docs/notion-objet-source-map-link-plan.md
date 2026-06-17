# Notion Objet Source Map Link Plan

Status: v0.3.103 read-only source-map material-link planner
Date: 2026-06-17

`notion-objet-source-map-link-plan` is the fallback planner for imported
Notion zets whose provider locators were already removed from the zettel body.

The earlier `notion-objet-link-index` and `notion-objet-link-plan` commands
work when a zettel still contains a provider locator that can be fingerprinted.
This command works one step earlier in the evidence chain: it joins safe
archive metadata from source maps, optional download/retrieval ledgers, and the
object manifest to propose reviewed zet-to-objet `embed` candidates.

## Command

```bash
archive notion-objet-source-map-link-plan <archive-root> --dry-run --format json
```

Optional explicit inputs:

```bash
archive notion-objet-source-map-link-plan <archive-root> \
  --source-map source-maps/notion-export.jsonl \
  --ledger receipts/import/notion-download-ledger.jsonl \
  --dry-run \
  --format json
```

If `--source-map` is omitted, the command reads archive-relative
`source-maps/*.jsonl`. `--ledger` can be supplied when a separate download or
retrieval ledger preserves file-to-`sha256` rows.

MCP:

```text
notion_objet_source_map_link_plan
```

## Why This Exists

Public-safe zettel bodies should not keep provider URLs, private local paths,
page titles, or raw locator text. But removing those locators too early can
also remove the only clue that an imported zet used a particular attachment,
snapshot, or source object.

This planner keeps the two requirements separate:

- zettel bodies stay clean of provider locator text,
- source-map or ledger metadata can still preserve stable, non-body join
  evidence,
- the output proposes candidate `embed` edges only after hashing private join
  values into fingerprints.

## Input Shape

The command accepts flexible JSON, JSONL, YAML, or YML rows. It looks for safe
metadata families, not one provider-specific schema:

- zettel refs: `zettel_id`, `zet_id`, `zettel_path`, `from_path`,
- page refs: `page_id`, `notion_page_id`, `external_id`, `item_id`,
- file refs: `relative_path`, `download_path`, `file`, `key`, `name`,
- object refs: `object_id`, `sha256`, `approved_object_id`, `objet_ref`.

The raw values are used only for local matching. They are not echoed. Output
uses `sha256:` fingerprints for join evidence and `sha256:<hex>` object ids for
targets.

## Output

The planner returns:

- source-map, ledger, manifest, zettel, and candidate counts,
- candidate rows with `candidate_id`, `from_zettel`, `target_object_id`,
  `target_mode=embed_edge`, `edge_type=embed`, `confidence`, and `join_basis`,
- `write_status` such as `not_written`, `already_referenced`, or
  `blocked_until_manifest_review`,
- next safe actions for human review and later `zettel-edge` or
  `zettel-edge-batch` approval gates.

## Boundary

`notion-objet-source-map-link-plan` is read-only.

It writes nothing, rewrites no zettel body text, writes no edges, writes no
receipts, reads no object bytes, calls no providers, creates no presigned URLs,
and does not require body provider locators.

It echoes no provider URLs, provider locator text, page titles, zettel body
text, frontmatter values, absolute local paths, account ids, emails, tokens, or
secret values.

## Relationship To Other Notion Objet Tools

Use this order:

1. `runtime-context` to confirm the archive and entrypoints.
2. `ai-response-concept-guide` when an AI runtime needs the current routing
   vocabulary.
3. `notion-objet-import-clue-audit` to see which imported Notion zettels already
   have a preserved material clue, have a recoverable source-map clue, or are
   missing the clue after locator omission.
4. `notion-objet-source-map-link-plan` when provider locators are already absent
   from zettel bodies but source maps or ledgers still carry page/file/object
   join evidence.
5. `notion-objet-link-index` and `notion-objet-link-plan` only when imported
   zettels still contain provider locators.
6. `notion-objet-link-rewrite-plan` and `notion-objet-link-convert` for the
   older body-locator review path.
7. `zettel-objet-links` after reviewed object refs or embed edges exist.

## Import-Time Contract

Future import adapters should remove provider locators from zettel bodies while
preserving the resolved material clue as one of:

- a safe `source_refs` object id such as `{"type":"object_id","value":"sha256:<hex>"}`,
- a planned or reviewed `embed` edge candidate,
- a source-map or ledger row that can join page -> file -> `sha256`.

Storing only `source_locator_omitted_count` is not enough. The import must keep
a durable, provider-safe material link clue outside the body.
