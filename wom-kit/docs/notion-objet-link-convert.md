# Notion Objet Link Convert

Status: v0.4.0 dry-run-only embed conversion planning
Historical checkpoint: v0.3.101 conversion receipts remain readable
Date: 2026-08-20

`notion-objet-link-convert` is a dry-run-only companion after
`notion-objet-link-rewrite-plan` in v0.4.0.

It does not rewrite zettel body text. `target_mode=embed_edge` can still plan a
reviewed locator/object conversion, but the historical executor affected an
edge and two receipt families as one compound write. v0.4.0 has no exact-human
binding for that complete effect set.

## Commands

CLI:

```text
python -m wom_kit.archive_cli notion-objet-link-convert <archive-root> --path inbox/example.md --locator-fingerprint sha256:<hex> --object-id sha256:<hex> --target-mode embed_edge --expected-occurrence-count 1 --dry-run
```

An `--approve` request returns
`compound_exact_human_approval_binding_required` before private target read or
mutation. It writes no edge or conversion receipt.

There is no MCP write tool for this surface.

## Required Review Inputs

The command requires:

- one zettel target, by `--path` or `--zettel-id`,
- one selected `--locator-fingerprint`,
- one selected manifested `--object-id`,
- `--target-mode embed_edge`,
- `--dry-run`, and
- an optional `--expected-occurrence-count` drift guard.

The occurrence count is a drift guard. It must be copied from the reviewed
`notion-objet-link-rewrite-plan` output so the write blocks if the zettel
changed after review.

## What It Writes

Nothing in v0.4.0. Historical edge and conversion receipts remain readable,
but neither they nor old reviewer flags reactivate the executor.

## Privacy And Safety Boundaries

The command re-runs the read-only rewrite plan and uses the same single-edge
validation rules as `zettel-edge`, without entering a writer.

It does not:

- rewrite zettel body text,
- replace provider locator text,
- call Notion or any provider API,
- start OAuth,
- read real source exports,
- read object bytes,
- create presigned URLs,
- write candidate records,
- update object manifests,
- expose an MCP write tool,
- echo provider URLs,
- echo provider locator text,
- echo zettel body text,
- echo zettel titles,
- echo frontmatter values,
- echo page titles,
- echo absolute local paths,
- echo account ids, emails, tokens, or secret values.

`target_mode=objet_ref_rewrite` remains blocked in this command. Body rewrite
needs a separate, narrower replacement guard before it should exist.

## Relationship To Other Notion Objet Tools

Use the tools in this order:

1. `notion-objet-link-index` for an archive-wide map.
2. `notion-objet-link-plan` for one zettel.
3. `notion-objet-manifest-locator-label` if the object manifest lacks the
   reviewed locator fingerprint.
4. `notion-objet-link-rewrite-plan` to validate one selected locator/object
   pair and occurrence count.
5. `notion-objet-link-convert --dry-run` to inspect the bounded conversion
   effect. No approved conversion exists in v0.4.0.
6. Use exact `zettel-edge --dry-run|--approve` only when the reviewed action is
   one direct edge, then use `zettel-objet-links` to inspect safe candidates.
