# Reviewed zet Title Remap Plan

Current v0.4.0 boundary: this plan remains read-only. It grants no title-write
authority; `zet-title-remap-write` approval fails before private target read or
mutation with `compound_exact_human_approval_binding_required`.

Status: v0.3.276 read-only title proposal validation before approved write, evidence audit, interrupted-case recovery, approved compensation, and revert recovery

Use this command after `zet-title-readiness` finds a canonical zet whose title
is an imported identifier:

```powershell
archive zet-title-remap-plan <archive-root> `
  --proposal .wom-scratch/title-remap/<private>.jsonl `
  --max-items 5000 `
  --dry-run `
  --format json
```

The proposal path is relative to the archive root. It must be a real `.jsonl`
file under `.wom-scratch/title-remap/`; the file is private working material
and must not be committed.

## Proposal Row

Each line follows `zet-title-remap-proposal.schema.json`:

```json
{"schema":"wom-kit/zet-title-remap-proposal/v0.1","zettel_id":"zet_import_example","expected_file_sha256":"sha256:<64 lowercase hex>","title":"Reviewed replacement title","basis":"source_export_property"}
```

`basis` has two meanings:

- `source_export_property`: a human checked that the replacement came from a
  source export property;
- `human_written`: no trustworthy automatic source title exists, so a human
  wrote and reviewed a specific replacement.

Neither basis is automatic approval. The command binds the private proposal to
the exact current canonical file bytes and reports `ready_for_review` or fixed
blocker codes. The plan command never writes a zet. In v0.4.0
`zet-title-remap-write` approval returns
`compound_exact_human_approval_binding_required` before private target reads or
mutation and writes nothing.

The default `--max-items` is the implemented 5,000-row ceiling. A smaller value
is an explicit operator bound, not a batching recommendation.

A non-generic exact source-export name that is just below the ordinary title
promotion threshold, such as a compact product or media name, is accepted only
with `basis: source_export_property` and reports
`source_export_title_below_promotion_threshold`. This is not available to
`human_written`: a human-created replacement must still satisfy the ordinary
specificity rule. Identifier-shaped, secret-like, generic, stale, or
re-flagged replacement titles remain blocked.

## Title Length

The replacement may contain 1 through 2,000 Unicode characters. The command
never truncates a title. A longer value blocks with `title_too_long`; the
operator must decide whether the source value is really a title or whether
some of its detail belongs in a separate reviewed facet or body field.

The 2,000-character ceiling matches Notion's official rich-text
`text.content` request limit and is a proposal safety ceiling, not a claim that
every good title should be long.

## Exact Whitespace Contract

The command does not normalize a title for you. A proposal title must:

- contain no line-break character;
- use only U+0020 SPACE for whitespace;
- have no leading or trailing space;
- have no consecutive spaces.

`title_contains_line_break` means the value contains a line break.
`title_contains_non_normalized_whitespace` means it contains a tab, NBSP or
other Unicode whitespace, leading/trailing space, or consecutive spaces.

If either fires, compare the source and intended display text, make the
normalization deliberately in the private proposal, then rerun the plan.
Changing whitespace without that review would silently change source text, so
WOM does not do it automatically.

## Safety Rule Names

A blocked row may report these fixed `matched_safety_rules`:

- `local_absolute_path`;
- `private_provider_url`;
- `credential_assignment_or_private_key`;
- `token_shaped_value`.

Only the rule name is reported. The matched value is never echoed.

An ordinary public `http://` or `https://` citation in a title is allowed and
reports `title_contains_public_web_url` as a warning. Private Notion/Tiro URLs,
object-store URLs, local paths, actual credential assignments/private keys,
and token-shaped values remain blocked. A bare topic word such as `password`
does not block by itself.

## When No Automatic Source Title Exists

For an empty source title, an identifier-shaped value with no matching source
name, or a source name that is genuinely too vague:

1. a human reads enough of the source record and canonical zet to name its
   subject accurately;
2. the human writes a specific one-line title;
3. set `basis` to `human_written`;
4. refresh `expected_file_sha256` from the current canonical zet;
5. rerun the complete plan and review every remaining blocker or warning.

Do not use `human_written` to rewrite an ordinary human-readable title. The
command remains limited to current titles that are identifier-shaped.

## Safe Input Errors

The CLI prints a fixed code and safe explanation for proposal-input mistakes,
including:

- `proposal_path_not_archive_relative`;
- `proposal_path_outside_private_scratch`;
- `proposal_path_contains_symbolic_link`;
- `proposal_file_missing_or_not_regular`;
- `proposal_file_exceeds_64_mib`.

Archive-root and unexpected failures keep a generic redacted message because
their underlying exception may contain a local absolute path.

## Next Step

The command does not read the source export, invent a title, normalize private
text, call a provider or model, modify canonical zets, write receipts, or grant
approval. After every ready row has been reviewed, follow
[zet Title Remap Write Preview](zet-title-remap-write.md) only to obtain its
dry-run plan, then stop.

The v0.3.269 writer adds exact prior-byte snapshots, a private receipt,
ordinary-failure rollback, and hard-exit evidence. After a completed or
interrupted write, use the separate read-only
[zet Title Remap Receipt And Interruption Audit](zet-title-remap-receipt-audit.md).
Use [zet Title Remap Recovery Plan](zet-title-remap-recovery-plan.md) and the
dry-run-only [zet Title Remap Recover](zet-title-remap-recover.md) for a
retained interrupted transaction. Historical completed-title revert
starts with the separate read-only
[zet Title Remap Completed-Receipt Revert Plan](zet-title-remap-revert-plan.md);
v0.3.274 added the historical [zet Title Remap Revert
Preview](zet-title-remap-revert.md). A revert
transaction left by a hard exit can be reviewed with the v0.3.275
[zet Title Remap Revert Recovery Plan](zet-title-remap-revert-recovery-plan.md);
since v0.3.276 its non-forensic fixed actions can be handed to the separate
[zet Title Remap Revert Recover](zet-title-remap-revert-recover.md).
