# Letter 112 Beta Retest Protocol

Status: prepared for the v0.3.301 public artifact
Date: 2026-08-07

This is the consolidated human-run retest for the v0.3.300 observations in
Letter 112. It does not authorize WOM developers or an AI agent to open or
change the beta tester's private archive. The archive owner chooses the test
records, reviews every preview, and performs every approval.

## 1. Install And Freeze Evidence

1. Make an independent backup of the private archive.
2. Install only the wheel attached to the public `v0.3.301` GitHub Release in
   a fresh virtual environment.
3. Record the release page, wheel filename, published SHA-256, local SHA-256,
   and `python -m pip show wom-kit` version in the private test log.
4. Stop if the published and local digests differ or the installed version is
   not exactly `0.3.301`.

Use the installed `archive` command in the examples below. Replace every
angle-bracket placeholder locally; do not send private values back to the
public repository.

## 2. Read-Only Baseline

```text
archive doctor <archive-root> --strict
archive authoring-conventions <archive-root> --dry-run --format json
```

Expected:

- `doctor --strict` reports no new integrity failure.
- Authoring conventions return either the validated archive-local rules or an
  explicit conservative default. They must not echo private zettel bodies,
  locators, URLs, or secrets.

## 3. Source Intake Paths, Replay, And Batch Scale

First repeat one previously failing relative-path case from a directory other
than the archive root:

```text
archive source-intake-record <archive-root> --source-intake-plan <archive-relative-plan.json> --dry-run --format json
archive source-intake-record <archive-root> --source-intake-plan <same-plan.json> --approve --reviewed-by <reviewer> --format json
archive source-intake-record <archive-root> --source-intake-plan <same-plan.json> --approve --reviewed-by <reviewer> --format json
```

Expected: the path resolves from the archive root; the first approved run
records it; the exact replay returns `already_recorded` and the documented
receipt path rather than a collision. A missing path, unsafe path, and genuine
receipt collision must have distinct fixed blocker codes.

Then make a private batch request using reviewed local files. A 2-3 item smoke
test is sufficient before the full 508-item rerun:

```text
archive source-intake-batch <archive-root> --manifest <archive-relative-request.json> --dry-run --format json
archive source-intake-batch <archive-root> --manifest <same-request.json> --approve --expected-plan-sha256 <complete-plan-sha256> --reviewed-by <reviewer> --format json
archive source-intake-batch <archive-root> --manifest <same-request.json> --approve --expected-plan-sha256 <complete-plan-sha256> --reviewed-by <reviewer> --format json
```

Expected: one reviewed aggregate plan covers 1-1,000 items, ordinary redacted
per-item records are written, one aggregate receipt is written, and replay
converges without rereading file bodies. Output must not contain body text,
local path values, or content hashes. This command deliberately makes no
transaction-wide atomicity claim.

## 4. Service, Account, And Repeated Locator Occurrences

Choose one zet and one locator that appears twice in different reviewed
locations. Keep every private value local:

```text
archive external-locator-plan <archive-root> --zettel-id <id> --locator-type <type> --locator-ref <private-value> --service-ref <service> --account-ref <account-or-email> --occurrence-anchor <first-anchor> --dry-run --format json
archive external-locator-record <archive-root> --zettel-id <id> --locator-type <type> --locator-ref <same-value> --service-ref <same-service> --account-ref <same-account> --occurrence-anchor <first-anchor> --expected-plan-sha256 <plan-sha256> --approve --reviewed-by <reviewer> --format json
```

Repeat with a different `occurrence-anchor`, using a fresh plan and digest.

Expected: the two reviewed occurrences coexist, while an exact duplicate is
blocked. JSON and recovery output reveal only coordinate-presence booleans or
fixed identities, never service, account/email, locator, or occurrence values.

## 5. Table And Notion Layout Normalization

Run the global preview first:

```text
archive markup-normalization-plan <archive-root> --policy normalize --dry-run --format json
```

Review one copy of each real pattern before approving any archive-wide plan:

- a simple `table`/`tr`/`td` or `th` table;
- `columns`/`column` layout wrappers;
- paired `mention-date` containing visible text;
- a table with `rowspan`, `colspan`, nesting, or ambiguous structure; and
- a zet that still contains an unknown semantic tag.

Expected: simple tables become GitHub Flavored Markdown tables; column
wrappers become paragraph boundaries; paired mention dates retain visible
text. Spanned, nested, ambiguous, or still-unknown semantics block the whole
affected zet without a partial rewrite. If the preview is accepted:

```text
archive markup-normalization <archive-root> --policy normalize --expected-plan-sha256 <plan-sha256> --approve --reviewed-by <reviewer> --format json
```

Keep the receipt and test the documented exact-byte revert on a disposable
copy before applying this to the primary archive.

## 6. Relation Candidates From Existing Facets

Choose zets that contain reviewed combinations of
`notion_event_time_start`/`end`, `thought_date`, `source_category`,
`db1_category`, or `db1_subcategory`:

```text
archive relation-candidate-plan <archive-root> --from-zettel <id> --max-candidates 20 --dry-run --format json
```

Expected: the plan may report fixed time/category signal classes but never
their values or body text. A signal is only a candidate; it must not create an
edge or decide `continues`, `sequence`, or another relationship automatically.

## 7. Structured zet-objet Link And Revert

Use an already manifested complete `sha256:<64-hex>` object and a disposable
copy of a zet first:

```text
archive zettel-objet-link <archive-root> --zettel-id <id> --object-id <full-object-id> --role source_document --dry-run --format json
archive zettel-objet-link <archive-root> --zettel-id <id> --object-id <full-object-id> --role source_document --expected-plan-sha256 <plan-sha256> --approve --reviewed-by <reviewer> --format json
```

Expected: the strict `assets` entry contains only `object_id`, `role`, and an
optional `label`; the objet must already be manifested; the command reads no
objet bytes. A truncated hash, stale plan, missing object, or unrelated later
zettel edit blocks. Preview and exercise `zettel-objet-link-revert` with the
written receipt; it must restore only unchanged post-write bytes.

## 8. AI Human-Record Integrity

Ask the normal WOM helper AI to revise one unminted draft in place. Before
mint review, inspect the complete draft as a human-readable record.

Expected:

- no shell command, tool result, internal task state, or agent-only metadata
  appears in the zettel body;
- status statements do not contradict one another after revision;
- reported files are openable archive references rather than unverifiable
  prose claims;
- archive-local authoring conventions are followed; and
- an unminted draft is revised in place rather than deleted and recreated.

The mint preview should warn on likely tool traces or contradictory status
phrases, and it must block likely truncated objet hashes. Warnings still
require human judgment; they are not semantic proof.

## 9. Intentional Draft Discard And Restore

Use a never-minted inbox draft whose removal has been approved:

```text
archive discard-draft <archive-root> --zettel-id <id> --reason <private-safe-reason> --dry-run --format json
archive discard-draft <archive-root> --zettel-id <id> --reason <same-reason> --expected-plan-sha256 <plan-sha256> --approve --reviewed-by <reviewer> --format json
archive discard-draft-restore <archive-root> --receipt <receipt-path> --dry-run --format json
archive discard-draft-restore <archive-root> --receipt <receipt-path> --expected-plan-sha256 <restore-plan-sha256> --approve --reviewed-by <reviewer> --format json
```

Expected: discard stores an exact private snapshot and immutable receipt but
does not echo the reason or body. Minted or canonical material blocks. Restore
is collision-safe and byte-exact. The inbox audit counts the receipt as an
intentional discard rather than unexplained loss.

## 10. JSON Failure Contract

For a command that normally requires options, deliberately omit one while
keeping `--format json`:

```text
archive zettel-objet-link <archive-root> --format json
```

Expected: stdout is parseable, content-free JSON with fixed reason codes and
missing option names; stderr is empty. It must not emit the ordinary argparse
usage text to stderr in JSON mode.

## Completion Report

Record each section as `pass`, `fail`, `blocked`, or `not tested`, with the
installed version, wheel digest, command exit code, receipt path where safe,
and a redacted observation. Never paste private locator/account values, local
paths, source bodies, or zettel bodies into a public issue.

The v0.3.301 engineering release and this private real-use retest are separate
gates. The release can be engineering-complete while the real-use result is
still pending. A failed or blocked section becomes input to the next feedback
letter; it does not authorize an AI to guess through a safety blocker.
