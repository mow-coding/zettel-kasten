# Contiguous Node Reading

Status: implemented in v0.3.207; duplicate-safe file-entry chain identity in v0.3.210

## Purpose

A final page is not proof that prior pages were read. WOM therefore separates:

- `complete`: this requested page reached the scope end;
- `archive_wide_coverage_claim_ready`: a strict cursor-zero chain reached the
  scope end without a skipped cursor and passed snapshot validation.

Host goal/loop UI remains outside WOM. This contract only makes the host's
continuation evidence harder to misuse.

## Recommended First Pass

```powershell
archive zet-catalog <archive-root> `
  --status canonical `
  --projection reading `
  --coverage-mode strict `
  --cursor 0 `
  --max-estimated-tokens 8000 `
  --dry-run `
  --format json
```

`reading` retains the node header needed for ordering later body reads: id,
status, title, kind, updated time, abstract state, facets, tie summary, and all
safe frontmatter edges. It omits full-only bookkeeping fields.

For every continuation, pass:

```text
coverage.next_cursor
snapshot.id
coverage.continuation_token
```

The host may change page-size or token-budget values between calls. It may not
change the status filter, projection, deterministic order, expected cursor, or
snapshot bound by the token.

## Token Boundary

The token is a base64url safe payload plus SHA-256 checksum. Its v0.3 payload
binds schema, snapshot id, status filter, projection, order, fixed-size
seed-list SHA-256, file-entry identity basis, next cursor, covered prefix count,
and the cumulative chain hash over page entry-identity digests. Snapshot-bound
file entries remain distinct even when malformed archives contain duplicate zet
ids.

It contains no raw seed id, file-entry identity list, zet body, title, abstract,
edge, or local path. It is stateless and WOM writes no traversal record.

The checksum detects accidental corruption and normal cursor drift. It is not
keyed, so a determined caller can construct another valid checksum. It is not
a signature, authentication mechanism, attestation, receipt, or adversarial
proof.

## Failure Rules

Strict continuation blocks when:

- cursor is nonzero and the prior token is missing;
- cursor does not match the token;
- token checksum or payload is malformed;
- status, projection, or order changes;
- seeded order's start-id list changes;
- expected snapshot conflicts with the token;
- local catalog evidence changes before completion.

Restart at cursor 0 after a changed snapshot. Search, top-k results, a raw final
page, or `complete: true` without strict claim readiness are not archive-wide
coverage.
