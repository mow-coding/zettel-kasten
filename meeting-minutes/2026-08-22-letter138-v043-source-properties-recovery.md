# Letter 138 v0.4.3 source-properties recovery implementation

Date: 2026-08-22

## User correction and intent

The user objected that earlier releases had accumulated safety commands while
leaving the historical client data unrepaired. The correction was explicit:
Letter 138 must end in a usable data-recovery writer, independent verification,
durable interruption recovery, and rollback. Work must remain complete but
efficient, reuse existing command families and shared infrastructure, and
avoid command bloat.

## Evidence corrections during implementation

The first implementation assumption treated the 3,605-page DB3 JSONL as the
source. It was corrected after checking the Letter 138 evidence: the complete
source is the recursive 11,585-file block mirror. Its content-free inventory is
4,034 Notion API page objects and 7,551 legacy `recordMap` pages. Legacy root
properties are present on 7,441 pages and absent on 110.

The legacy `recordMap` files often lack collection schema, so internal property
ids cannot honestly be translated into names or types. The design changed from
blanket review to lossless opaque preservation for exact one-to-one targets.
Only ambiguity, invalid shape, absent root properties, or indeterminate typed
payloads remain review cases.

The old email 51 / URL 904 / date 2,810 figures were traced to a historical
2026-08-20 diagnostic that read only the first 40,000 decoded characters and
matched three exact Korean names with raw regular expressions. The full-file
exact-name results were 51/907/2,827, while semantic typed populated-page
counts were 51/917/3,439. The acceptance design was corrected to preserve those
probe figures as provenance instead of forcing current semantic counts to
match them.

## Architecture corrections

An early draft had its own transaction, journal, approval check, whole-file
receipt, and duplicate atomic-replace helper. Those were rejected. The final
path reuses the shared `ExactOperationManifest v1`, exact-operation approval
binding, fixed archive-wide writer lock, file checkpoint store, authenticated
resume, independent verifier, and final result receipt.

The domain contribution is limited to acquisition, normalization,
classification, payloads, target field writer, target field verifier, and
operation-specific CLI wrappers. Every manifest effect covers only
`source_properties`; rollback therefore does not erase later title, body, or
unrelated frontmatter changes.

The writer was further corrected after identifying a time-of-check/time-of-use
race in a plain temp-file `os.replace`. It now rereads the current file and uses
the existing exact expected-byte compare-and-swap helper. A concurrent external
editor or sync writer produces a drift failure instead of being overwritten.

Resume was bound to the same authenticated `started` approval claim, the same
approval context, the same manifest target set, the authority-specific
execution digest, and the matching durable checkpoint. It never opens a fresh
approval prompt or accepts an arbitrary manifest callback.

Apply and revert were then separated into distinct exact-human operations and
distinct manifests. The native dialog, context plan digest, execution locator,
checkpoint chain, result, and final receipt now agree on one direction. An
apply claim cannot authorize a revert. Revert also verifies the exact managed
post-state before starting a one-use approval.

A further time-of-check correction binds the deterministic complete canonical
source-id/target projection. After the execution locator callback and while
holding the common writer lock, WOM scans that projection again. A late
duplicate canonical target or lifecycle/identity change blocks before the
first field write. Prospective replacements above the canonical size cap now
move to review during planning rather than failing after approval.

## CLI and operator boundary

No new top-level command was added. The implementation extends:

```text
archive migrate <archive-root> --target notion-source-properties
```

The fixed target first requires `--source-mirror --acceptance-bootstrap
--acceptance-output ... --dry-run`. That pass stages one canonical JSON
candidate create-only under ignored
`profiles/local/notion-property-backfill/`; it is explicitly a private
recovery-evidence write, not a zettel write. The later plan requires that exact
byte-canonical file through `--acceptance-file`. Existing outputs are never
overwritten, linked/reparse paths are rejected, directory durability is
checked, and ambiguous publication returns `effects_state: unknown` instead of
claiming no effect.

The target then supports exactly one of ordinary `--dry-run` or `--approve`,
plus target-scoped apply, resume, revert preview, approved revert, and resumed
revert. Other migration targets reject the new options and their approved
writes remain fixed closed. Parser inventory therefore reports top-level
`migrate` as conditionally available, not as global migration authority. The
CLI always emits content-free progress to stderr and keeps JSON results on
stdout.

Final independent review found one privacy gap in the parser-error path:
before parsing completed, a misspelled migration option could cause argparse
to reflect the following private path in text mode. The whole `migrate`
family is now classified as privacy-sensitive at that boundary, so parse
failures return only a fixed redacted message. A dedicated private-path canary
regression was added; the final related regression set passed 295 tests.

The same final review corrected two acceptance-publication claims. Windows had
previously returned directory-durable success after doing no namespace flush;
the PC-first path now uses `MoveFileExW` with `MOVEFILE_WRITE_THROUGH` and no
replace flag. POSIX retains create-only hard-link publication, removes the
temporary name, then fsyncs the parent. If that unlink fails, WOM returns an
unknown outcome instead of a success whose two-link file would be rejected by
the next exact acceptance read.

Machine capability truth was also tightened. The successor
`command-approval-status-inventory/v0.2` attaches a content-free
`approval_scope` to `migrate`: only `--target notion-source-properties` is in
the approval-available allowlist, and every other target is explicitly
fixed-closed with the common reason code. This supplements, rather than
replaces, the handler enforcement.

The review also found that unresolved counts and digests were added to the CLI
result only after the common final receipt had been finalized. The common
manifest now accepts a bounded content-free `operation_evidence` document and
copies it into the stable result and durable receipt. Letter 138 fills it with
the complete source/category counts plus mirror, acceptance, canonical,
classification, category-set, and unresolved-set digests. A synthetic durable
receipt with mapped, unmapped, and review pages is reread and verified without
exposing its source ids or property values.

Finally, resume was tested as a true process-restart boundary rather than an
in-memory object reuse. After a synthetic write-before-field-receipt crash, a
new plan is rebuilt from the same mirror, reviewed acceptance, and current
archive. Only the adapter-owned managed-equal field is normalized back to its
original mapped effect, producing byte-identical manifest JSON and the same
authority-bound execution digest before authenticated resume succeeds.
Applied property and populated-property totals also come from that stable
manifest evidence, so a restarted process cannot undercount fields already
written before its new observation pass.

The follow-up independent review found this restart counter issue as its last
P2, then rechecked the correction and reported no remaining P1 or P2 in the
product slice. The full focused, approval, CLI, inventory, resource, and
historical-boundary suite passed 295 tests after the correction. The separate
common checkpoint performance commit remains an integration prerequisite and
must be followed by a combined 8,566-effect scale run.

The earlier blanket populated-unmapped block was explicitly narrowed for this
recovery. The 2,882 unmapped pages remain exact manifest-bound unresolved sets;
they are not dropped, called resolved, or given a fabricated target. A human
may approve the separate 8,566 certain effects only after reviewing those set
digests. WOM does not modify the source mirror and does not overclaim control
of its future lifecycle.

## Performance feedback loop

The first full read-only run took 318.109 seconds: mirror acquisition 178.234,
canonical scan 105.344, join 33.172, and finalization 0.703. This exceeded the
five-minute limit by about eighteen seconds.

The plan was revised to discover and scan canonical small files before the
925MB mirror, use a deterministic bounded four-worker pool only for canonical
read/parse, keep mirror acquisition sequential and memory-bounded, build one
source-id index, and preserve source/effect ordering. Tests assert that each
mirror and canonical file is read exactly once.

The second full read-only run completed in 240.563 seconds:

- first content-free status: 0.000 seconds;
- maximum observed status gap: 1.109 seconds;
- canonical scan: 30.172 seconds for 8,606 files;
- mirror acquisition: 174.265 seconds for 11,585 files;
- join and classification: 33.656 seconds;
- manifest finalization: 0.719 seconds.

The final content-free classification was 8,566 mapped, 2,882 unmapped, and
137 review pages, totaling 11,585. It produced 8,566 exact field effects,
verified the acceptance profile, and reported zero unexplained populated-
property and property-type omissions. The read-only run wrote nothing.

One malformed UTF-8-BOM canonical Markdown file had no `source_page_id` token
and was therefore a noncandidate. It is reported only through an opaque digest
and fixed reason code instead of turning every source page into review. The
underlying BOM/path hygiene remains planned v0.4.7 debt; no private path is
published here.

## Files implemented in this worktree

- `wom-kit/src/wom_kit/notion_property_backfill.py`
- `wom-kit/src/wom_kit/archive_cli.py`
- `wom-kit/src/wom_kit/exact_human_approval_windows.py`
- `wom-kit/schemas/notion-source-properties-v0.1.schema.json`
- `wom-kit/schemas/notion-property-backfill-acceptance-v0.1.schema.json`
- `wom-kit/schemas/zettel-frontmatter.schema.json`
- focused domain and CLI regression tests
- public operator guide, decision log, navigation, and capability record

The shared exact-operation infrastructure came from separately reviewed core
commits and was integrated before the domain wrapper. The private Basoon
archive and mirror were inspected read-only only. Actual Basoon apply, public
release, tester upgrade, and post-apply verification remain pending and must
not be reported as completed.

Letter 138 completion additionally requires a private real-archive backup, the
actual mapped-field apply and independent verification, a successful
field-scoped rollback drill, and a durable result retaining the unresolved
classification evidence.
