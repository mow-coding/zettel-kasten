# Notion Source Properties Recovery

Status: v0.4.3 working-tree implementation; public release and real-archive apply pending

Date: 2026-08-22

## What this repairs

Letter 138 identified a concrete historical loss: canonical zettels retained a
Notion source page id, but the page's source properties were not preserved.
This operation actually restores those properties into a managed
`source_properties` frontmatter field. It is not another audit-only command.

The operation is deliberately local. It reads an operator-selected raw Notion
mirror and the local archive. It does not contact Notion, read a credential, or
change the mirror.

Two source shapes are preserved:

- current Notion API page objects retain every property name, id, type,
  population classification, and exact raw JSON payload;
- legacy `recordMap` pages whose collection schema is unavailable retain each
  internal property id and exact raw JSON value in an opaque envelope marked
  `semantics_unavailable: true`.

The legacy envelope prevents data loss without pretending that an internal
property id is a human-readable name or that WOM knows its type.

## Step 1: stage the exact private acceptance candidate

Do not hand-copy or hand-author the completeness profile. Bootstrap it from the
complete mirror into one ignored, archive-relative, create-only file:

```text
archive migrate <archive-root> \
  --target notion-source-properties \
  --source-mirror <complete-block-mirror> \
  --acceptance-bootstrap \
  --acceptance-output profiles/local/notion-property-backfill/letter138-acceptance.json \
  --dry-run \
  --format json
```

On PowerShell, put the command on one line or replace the displayed backslashes
with PowerShell backticks. Do not redirect stdout to construct the file.

This mode is the one documented exception to the usual `--dry-run` no-write
rule. It creates recovery-evidence staging bytes only; it does not modify a
zettel. The archive must ignore `profiles/local/`. The destination must stay
below `profiles/local/notion-property-backfill/`, cannot traverse a link or
reparse point, and cannot already exist. WOM fsyncs the complete bytes and
publishes them create-only. On Windows it uses a no-replace
`MoveFileExW(..., MOVEFILE_WRITE_THROUGH)` namespace commit; on POSIX it
removes the temporary hard-link name and fsyncs the parent directory. A
surviving second link is never reported as success because the exact loader
requires a single-link file. If an outcome is uncertain, the CLI returns
`effects_state: unknown`; inspect the private directory instead of retrying
automatically.

The saved document binds the exact one-pass mirror snapshot digest, total page
count, source-property count, populated count, indeterminate count, opaque
count, source-shape split, legacy-root split, normalized source-id accounting,
and optional populated page counts by property type. Review that exact private
file. A later plan accepts only its byte-canonical JSON form and exposes the
same content-free `acceptance_document_sha256` for comparison.

This gate matters because the separate 3,605-page DB3 JSONL is not the full
Letter 138 source. A well-formed but incomplete export must not be mistaken for
the 11,585-page recovery mirror.

## Step 2: calculate the read-only recovery plan

```text
archive migrate <archive-root> \
  --target notion-source-properties \
  --source-mirror <complete-block-mirror> \
  --acceptance-file <archive-root>/profiles/local/notion-property-backfill/letter138-acceptance.json \
  --dry-run \
  --format json
```

On PowerShell, place the command on one line or use PowerShell's backtick line
continuation instead of the backslashes shown above.

The command sends `WOM-PROGRESS` records to stderr before I/O begins and at
bounded intervals. Those records contain only a fixed stage, counts, elapsed
time, and ETA. Paths, page ids, and property values stay private.
Argument-parser failures are redacted for the entire `migrate` family as well,
so a misspelled option cannot reflect a mirror or acceptance path into text
output.

Do not approve unless the digest matches the reviewed private candidate and all
of these are true in the final JSON:

- `ok: true`;
- `acceptance_verified: true`;
- `zero_silent_omission: true`;
- `unexplained_missing_populated_property_count: 0`;
- `unexplained_missing_populated_property_type_count: 0`; and
- `mapped + already_equal + unmapped + review == mirror_page_count`.

`unmapped` means the source page has no exact canonical zettel target, so WOM
does not invent one. `review` means the source or target is ambiguous or the
property payload cannot be safely classified, so WOM preserves the evidence
but does not silently write it.

Every category has a deterministic source-set digest. The exact unresolved
source and reason digests are included in the source inventory bound by every
manifest effect and therefore by native approval. A bounded backfill may write
the certain mapped effects after a human reviews those exact unresolved
digests. This does not classify unresolved pages as dropped or resolved, does
not modify the source mirror, and does not guarantee the mirror's future
lifecycle.

## Step 3: apply the reviewed plan

Run the same command with `--approve` and a reviewer claim:

```text
archive migrate <archive-root> \
  --target notion-source-properties \
  --source-mirror <complete-block-mirror> \
  --acceptance-file <exact-private-acceptance.json> \
  --approve \
  --reviewed-by person:<reviewer> \
  --format json
```

The complete source and archive are planned again. The native Windows dialog
shows the exact recovery operation summary. Approval is valid only for the
unchanged manifest, acceptance bytes, unresolved classification, canonical
projection, and target set. Revert has a separate operation label and manifest;
an apply approval cannot authorize a revert, or vice versa.

The writer then:

- holds the common archive-wide exact-operation writer lock;
- rechecks the complete deterministic canonical source-id/target projection
  under that lock, after publishing the resume locator;
- compares the current `source_properties` state with the manifest;
- rereads each current zettel and preserves unrelated frontmatter and body
  bytes;
- uses exact expected-byte compare-and-swap at replacement time, so an
  external editor or sync change causes a fail-closed drift error rather than
  an overwrite;
- independently verifies each field after writing;
- records hash-chained checkpoints under
  `profiles/local/exact-operations/checkpoints/`; and
- publishes one content-free final result receipt under
  `receipts/ops/exact-operations/` only after complete verification. That
  receipt retains the manifest-bound source/category counts, including mapped
  property and populated-property totals that stay stable across resume, plus
  mirror,
  classification, category-set, unresolved-set, canonical-projection, and
  acceptance digests as `operation_evidence`.

The mirror is never changed, and no parallel Letter 138 transaction or receipt
format exists.

## Interrupted execution and resume

Do not start a fresh approval after an interrupted write. Reuse the exact
authenticated `started` approval id and the authority-bound execution digest
recorded by the same operation:

```text
archive migrate <archive-root> \
  --target notion-source-properties \
  --source-mirror <complete-block-mirror> \
  --acceptance-file <acceptance.json> \
  --approve \
  --reviewed-by person:<same-reviewer> \
  --resume \
  --approval-id <started-approval-id> \
  --execution-sha256 sha256:<digest> \
  --format json
```

Resume does not display a second approval dialog. It reauthenticates the same
started direction-specific claim, reconstructs the same context and manifest,
proves the matching checkpoint exists, verifies current field state, and
continues only that execution. Reconstruction does not depend on the prior
Python process: an exact adapter-owned managed-equal field is normalized back
to its originally approved mapped effect for manifest accounting, while plain
pre-existing equal data is not. A regression rebuilds the byte-identical
manifest from the reviewed acceptance, complete mirror, and partially written
archive after a write-before-receipt crash. A changed mirror, archive target,
reviewer context, approval id, execution digest, checkpoint chain, or field
state blocks.

## Preview and perform field-only rollback

First preview:

```text
archive migrate <archive-root> \
  --target notion-source-properties \
  --source-mirror <complete-block-mirror> \
  --acceptance-file <acceptance.json> \
  --revert \
  --dry-run \
  --format json
```

Then repeat with `--revert --approve --reviewed-by person:<reviewer>` and accept
the native **revert** dialog. Before the dialog, WOM independently proves every
selected field is still in the exact managed post-state. An interrupted revert
uses the same resume flags as apply, plus `--revert`, and must use the revert
approval id and revert execution digest.

Rollback removes only the marker-owned `source_properties` field. A later edit
to the title, another frontmatter field, or the body does not by itself block
or get erased. Drift in `source_properties` does block.

## What the 2026-08-22 read-only run proved

The full private source was read once without writing the Basoon archive:

- source pages: 11,585;
- classified: 8,566 mapped, 0 already equal, 2,882 unmapped, 137 review;
- planned field effects: 8,566;
- review reasons: 110 legacy roots without properties and 27 indeterminate
  typed-property pages;
- unexplained populated-property omissions: 0 properties and 0 types;
- malformed noncandidate canonical files excluded from the join: 1, recorded
  only by opaque digest and reason; and
- elapsed time: 240.563 seconds, with the first status at 0.000 seconds and a
  maximum observed status gap of 1.109 seconds.

Those facts prove plan completeness and performance for that read-only run.
They do **not** prove that the 8,566 writes have been applied, that v0.4.3 has
been released, or that a beta tester has installed it.

Letter 138 may be called fully resolved only after a private backup exists, the
8,566 certain effects have been applied and independently verified in the real
archive, a field-scoped rollback drill has succeeded, and the durable result
retains the 2,882 unmapped classification evidence. This working-tree result is
not that completion proof.

The excluded file had a UTF-8 BOM and no `source_page_id` token, so it was not
a Notion join candidate. It remains visible as v0.4.7 archive-hygiene debt;
WOM does not let one unrelated malformed file turn all 11,585 source pages into
false review items.

## Why the old 51 / 904 / 2,810 figures are not write gates

Those figures came from a historical 2026-08-20 diagnostic that read only the
first 40,000 decoded characters of each source file and used raw regular
expressions for three exact Korean property names. Reproduction found:

- the historical head probe: email 51, URL 904, date 2,810;
- the same exact-name probe over full files: email 51, URL 907, date 2,827; and
- semantic typed populated-page counts: email 51, URL 917, date 3,439.

The differences are explained by values after the 40,000-character boundary,
alternate property names, and three URL raw-regex matches that did not belong
to root semantic properties. They are kept as content-free historical audit
counts, not forced into current recovery acceptance.
