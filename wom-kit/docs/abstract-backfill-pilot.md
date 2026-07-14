# Three-zet Abstract Backfill Pilot

Use this procedure when a legacy archive has many canonical zets without an
explicit frontmatter `abstract`. The pilot measures the human review workflow.
It is not permission to fill the whole archive automatically.

## Stop Rule

Work on exactly three candidates. Stop after the verification commands and
report what was confusing, slow, or unsafe before selecting any fourth zet.

## 1. Select Three Candidates

Run:

```text
archive first-read-readiness <archive-root> --dry-run --max-items 3 --progress --format json
```

Use the three returned attention rows in their existing order only when each
row has a safe zet id, readable frontmatter, and a missing or compatibility-
only abstract. If fewer than three safe rows are returned, stop with that
smaller number. Do not search for more convenient content and do not change a
redacted or unreadable zet in this pilot.

Process exit zero means the diagnostic completed. It does not mean the archive
is ready; check `readiness_met` and `state`.

## 2. Prepare A Private Proposal

Read only those selected zets with `read-zettel`. An AI may draft a compact
abstract from each selected body, but it cannot review or approve its own
proposal. Keep exactly three JSONL rows under:

```text
.wom-scratch/abstract-backfill/<private-name>.jsonl
```

Follow the row contract in [Abstract Backfill Plan](zet-abstract-backfill-plan.md).
Keep zet ids, paths, body hashes, and proposed abstract text in private scratch.
Do not paste them into public feedback.

## 3. Validate And Review

```text
archive zet-abstract-backfill-plan <archive-root> --proposal .wom-scratch/abstract-backfill/<private-name>.jsonl --max-items 3 --dry-run --progress --format json
```

The result must be `ready_for_human_review` with three ready candidates and no
blockers. A human then reads all three full zet bodies and all three proposed
abstracts together. A green plan does not count as review.

Preview the separate writer with the exact proposal SHA-256:

```text
archive zet-abstract-backfill-write <archive-root> --proposal .wom-scratch/abstract-backfill/<private-name>.jsonl --expected-proposal-sha256 <sha256> --dry-run --progress --format json
```

Only after that review may the human authorize:

```text
archive zet-abstract-backfill-write <archive-root> --proposal .wom-scratch/abstract-backfill/<private-name>.jsonl --expected-proposal-sha256 <sha256> --approve --reviewed-by person:<reviewer> --affirm-abstracts-reviewed --progress --format json
```

## 4. Verify And Stop

Run all three checks:

```text
archive first-read-readiness <archive-root> --dry-run --max-items 3 --progress --format json
archive abstract-freshness <archive-root> --dry-run --max-items 3 --progress --format json
archive zet-abstract-backfill-receipt-audit <archive-root> --dry-run --max-receipts 5000 --max-locks 5000 --max-problems 20 --progress --format json
```

Confirm that exactly three missing abstracts became explicit, the three current
abstract/body pairs are `fresh`, and the backfill receipt lifecycle is healthy.
Then stop. Preserve the private result hashes and report timings, review effort,
confusing language, and any blocker. Do not start a bulk batch from this pilot.

## Safety Boundary

- No command may auto-select and auto-write all missing abstracts.
- AI assistance may prepare private text; human review and approval remain
  separate and explicit.
- The writer changes only `frontmatter.abstract`, retains text-free hash
  evidence, and has its own reviewed revert and receipt-audit flow.
- A technically fresh abstract is not proof that it is true, useful, complete,
  or understood by a model.
