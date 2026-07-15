# Reading Memory And Revision

Use this reference when the human asks what the archive knows, whether a zet is
fresh, what changed, or whether earlier canonical bytes can be recovered.

## Read Abstracts Before Full Bodies

Check first-read readiness:

```text
archive first-read-readiness <archive-root> --dry-run --progress --format json
```

Read the bounded abstract catalog and relation hints before opening full zet
bodies. Abstracts choose reading order; they do not replace the full documents
needed to answer the human's goal.

Use freshness inspection when abstracts or derived reading surfaces may lag:

```text
archive abstract-freshness <archive-root> --dry-run --progress --format json
```

Separate these questions:

- **coverage**: does each eligible zet have a usable abstract?
- **freshness**: does the abstract still describe the current canonical body?
- **semantic quality**: is the abstract accurate and useful to a human?

A structural pass cannot prove semantic quality.

## Follow The Goal Through The Archive

1. Start from abstract matches and the human's stated goal.
2. Use ties, edges, and containment as reading routes, not as a substitute for
   reading relevant nodes.
3. Open complete zet bodies in the order suggested by those routes.
4. Inspect linked objet metadata or bytes only when the answer needs source
   evidence.
5. Record unresolved contradictions instead of silently choosing one version.

## Prepare Abstract Backfill Carefully

Backfill and repair commands are write workflows. Preview proposals, inspect
the exact target set and body hashes, then use only the explicit approved path.
Never treat a generated abstract as human-verified truth.

## Audit Revisions Before Handoff

After approved revision work, run:

```text
archive zet-revision-receipt-audit <archive-root> --dry-run --max-receipts 5000 --max-locks 5000 --max-problems 100 --progress --format json
```

If a canonical revision needs to be restored, use a trusted private byte source
and the dedicated restore plan/write workflow. Do not delete revision locks,
rewrite receipts, or reconstruct old bytes from a displayed diff.

Search [operator-contract.md](operator-contract.md) for these exact advanced
workflows before using them:

- `zet-abstract-backfill`
- `zet-abstract-backfill-revert`
- `zet-revision-plan`
- `zet-revision-write`
- `zet-revision-restore-plan`
- `zet-revision-restore-write`

The complete operator contract contains the required hashes, event timestamps,
human affirmations, and rollback boundaries.
