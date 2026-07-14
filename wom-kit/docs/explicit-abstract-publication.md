# Explicit Abstract Publication Gate

This gate prevents a new canonical zet from being published without the
compact first-read data that a future AI operator needs before opening the
body.

## Plain-Language Rule

- An incomplete idea may stay in `inbox/` as a draft without an abstract.
- Before `mint-zet`, `mint-zettel`, or legacy `promote` publishes that draft,
  add a human-reviewed explicit `frontmatter.abstract`.
- A compatibility field such as `summary` can help an older reader, but it
  does not replace the explicit publication field.

Preview the normal mint path:

```text
archive mint-zet <archive-root> --path inbox/<draft>.md --dry-run --format json
```

The result is ready to proceed only when:

```text
first_read_check.status = ready
first_read_check.ready_for_publication = true
```

## Accepted Shape

The abstract must be a non-empty string, already normalized to one line, no
longer than 360 characters, and free of private local paths, provider
locators, and secret-like material. Draft creation normalizes a supplied safe
abstract; publication fails closed when a manually edited draft no longer
matches this shape.

## Last-Moment Check

Real mint and promotion bind both the complete draft SHA-256 and the approved
abstract SHA-256. After the dry-run checks, they reread one source-byte
snapshot and stop before any canonical, receipt, or draft-snapshot write if
any draft byte changed or the abstract is missing or invalid. Canonical text,
the mint snapshot, and receipt evidence are then derived from that one captured
source snapshot instead of separate file reads.

Mint and promotion results and receipts keep a text-free `first_read_check`
with status, character count, limit, and SHA-256. The check never copies the
abstract text and does not read the body for this decision.

## Compatibility And Limits

Existing canonical zets and receipts are not migrated or rejected. Use
`first-read-readiness` to find older gaps and the separately reviewed abstract
backfill workflow to repair them.

This gate does not decide whether an abstract is true, complete, semantically
fresh, or understood by a model. Those remain separate human-review and
runtime-consumption claims.
