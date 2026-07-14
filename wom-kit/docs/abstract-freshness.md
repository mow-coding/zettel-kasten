# Abstract Freshness Check

An explicit abstract is useful only while it still describes the current zet
body. This read-only check tells a human or AI operator whether WOM retains
evidence that the current abstract and current body were reviewed together.

## Plain-Language Rule

Run this after `first-read-readiness` and before the complete private catalog
pass:

```text
archive abstract-freshness <archive-root> --dry-run --progress --format json
```

The MCP tool is `abstract_freshness`.

The result uses these states:

- `fresh`: the current abstract/body hash pair exactly matches retained review
  evidence.
- `stale`: review evidence exists for this zet, but the abstract, body, or both
  changed afterward.
- `unverified`: the zet has a valid explicit abstract, but WOM cannot find
  recognized review evidence for the current pair.
- `missing`: the explicit abstract is absent or invalid.
- `unreadable`: the canonical zet could not be parsed within the bounded read.
- `excluded`: the zet is redacted by policy and is not required to expose an
  abstract.

`unverified` is deliberately different from `stale`. It does not accuse old
material of being wrong; it says only that the evidence needed for a freshness
claim is unavailable.

## Evidence

New mint and legacy promotion receipts store an `abstract_review_basis` after
human approval. It contains only the abstract SHA-256, canonical body SHA-256,
hash basis, and review status. It stores neither text.

The scanner can also recognize:

- v0.3.232 mint receipts when the exact SHA-bound draft snapshot remains,
- v0.3.232 promotion receipts when the exact SHA-bound inbox source remains,
- applied human-reviewed abstract-backfill receipts.

Changing only other frontmatter, such as an edge, does not make the abstract
stale. Changing the body or abstract does. WOM never fixes either value
automatically.

## Scale And Privacy

The command builds the receipt evidence index once and scans canonical zets
once. Its complexity contract is
`O(canonical_zets + receipt_files + receipt_items)`, not one full receipt scan
per zet. Receipt and zet reads are bounded, and the receipt count is capped.

Output may identify an attention row by archive-relative canonical path and a
safe zet id. It does not return title, abstract text, body text, hash values,
receipt paths, reviewer ids, provider URLs, absolute local paths, or secrets.
It writes nothing and calls no provider, model, or credential store.

## Claim Boundary

A `fresh` result proves an exact local hash-pair match to retained human-review
evidence. It does not prove that the abstract is true, complete, useful, or
understood by a model. A non-fresh result is a human review queue, never
permission for an AI to rewrite memory automatically.
