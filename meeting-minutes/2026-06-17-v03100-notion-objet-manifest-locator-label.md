# 2026-06-17 v0.3.100 Notion Objet Manifest Locator Label

## Context

After v0.3.99 closed policy batch zettel-edge writes, the next client feedback
gap was Notion objet matching.

The observed failure mode:

- zettel bodies can contain Notion provider locator fingerprints,
- object manifests may know that an object came from a Notion export,
- but the manifest may not preserve the specific locator fingerprint,
- therefore `notion-objet-link-index` can find locator rows but report 0
  manifest candidates.

## Decision

Add a narrow approval-gated manifest label command:

```text
archive notion-objet-manifest-locator-label <archive-root>
  --object-id sha256:<hex>
  --locator-fingerprint sha256:<hex>
  --dry-run|--approve
```

Alias:

```text
notion-objet-locator-label
```

The command writes only a non-secret locator hash label to one existing object
manifest record. It never stores or prints the raw Notion URL/provider locator.

## Implementation Notes

If the target manifest record has no locator label, the command writes:

```text
provenance.provider_locator_sha256
```

If the record already has a different primary label, the command preserves it
and adds:

```text
provenance.provider_locator_sha256_values
```

The command also writes a receipt under:

```text
receipts/objects/notion-locator-labels/
```

## Safety Boundary

The command is CLI-only and exposes no MCP write tool.

It does not:

- read zettel bodies,
- rewrite zettel bodies,
- write `embed` edges,
- call providers,
- start OAuth,
- read real source exports,
- read object bytes,
- write candidate records.

The output avoids provider URLs, raw provider locator text, zettel body text,
zettel titles, frontmatter values, page titles, local absolute paths, account
ids, emails, tokens, and secret values.

## Files Changed

- `wom-kit/src/wom_kit/archive_services.py`
- `wom-kit/src/wom_kit/archive_cli.py`
- `wom-kit/tests/test_cli.py`
- `wom-kit/tests/test_capability_matrix_docs.py`
- `wom-kit/docs/notion-objet-manifest-locator-label.md`
- `wom-kit/docs/notion-objet-link-index.md`
- `wom-kit/docs/notion-objet-link-plan.md`
- `wom-kit/docs/notion-objet-link-rewrite-plan.md`
- `wom-kit/docs/capability-matrix.md`
- `wom-kit/docs/releases/v0.3.100.md`
- `README.md`
- `wom-kit/README.md`
- `CHANGELOG.md`

## Next Work

The remaining related work is the actual approved body rewrite or reviewed
`embed` edge write after `notion-objet-link-rewrite-plan` passes.
