# Zettel Objet Links

Status: v0.4.1 read-only discovery plus exact-human structured link apply;
structured link revert remains fixed closed
Previous checkpoint: v0.4.0 structured link apply/revert were both fixed closed
Historical extension: v0.3.301 structured link receipts remain readable
Date: 2026-08-21

`zettel-objet-links` is the first small reading-side bridge between a human
zettel and source objets referenced by content address.

It does not open the objet. It does not create a browser URL. It does not call a
storage provider. It only answers:

```text
This zettel mentions these sha256 objet refs.
For each ref, the local manifest currently knows these safe link candidates.
```

## Commands

CLI:

Command shape:

```text
archive zettel-objet-links <archive-root> --path inbox/example.md --dry-run
```

```powershell
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli zettel-objet-links <archive-root> `
  --path inbox/example.md `
  --dry-run
```

or:

```powershell
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli zettel-objet-links <archive-root> `
  --zettel-id zet_20260614_example `
  --dry-run `
  --format json
```

MCP:

```text
zettel_objet_links
```

Inputs:

- `archive_root`
- `path` or `zettel_id`
- `dry_run`, which must be true
- optional `max_refs`

## Plan And Apply One Structured Link

The read-only preview remains unchanged. The singular command plans one
reviewed asset entry:

```text
archive zettel-objet-link <archive-root> --zettel-id <id> \
  --object-id sha256:<64-hex> --role source --dry-run --format json
```

The objet must already exist in `objects/manifests/files.jsonl`. A complete
SHA-256 is mandatory. Truncated hashes are not guessed or expanded.

In v0.4.1, copy the exact `summary.plan_sha256` from a fresh successful
dry-run into the approval command:

```text
archive zettel-objet-link <archive-root> --zettel-id <id> \
  --object-id sha256:<64-hex> --role source \
  --expected-plan-sha256 <64-hex> --reviewed-by person:reviewer-id \
  --approve --format json
```

Approval is available only in the local interactive Windows CLI. It presents
the native exact-human TaskDialog and then uses one authenticated durable
claim. MCP exposes no writer and a caller-supplied Boolean is never treated as
human approval.

The plan and operation-specific approval binding cover the complete effect
set:

- the exact current canonical zettel bytes and the one proposed
  `frontmatter.assets` entry;
- a strict, bounded, stable read of the complete object manifest and the exact
  unique matching object-record set;
- an exact before-zettel snapshot, created only when absent or reused only
  when its existing regular-file bytes are exact;
- the next create-only receipt generation and path;
- one deterministic canonical compare-and-swap transaction and both of its
  approved archive-relative private residue paths,
  `<zettel-directory>/.<transaction-sha256>.<path-sha256-prefix>.zettel-objet-link.swap`
  and the same path with `.previous` appended;
- one support-effect-set digest tying the zettel, snapshot, receipt, and both
  compare-and-swap coordinates together; and
- the separately bound persistent per-zettel control artifact at
  `receipts/objects/zettel-links/.locks/<sha256-of-zettel-id>.lock`, including
  its absent or `existing_exact` state and exact bytes.

The writer re-derives those bindings under the control artifact before the
first canonical mutation. It holds every relevant parent-directory identity,
uses an exact-byte compare-and-swap for both forward write and rollback, reads
back the canonical zettel, snapshot, and v0.2 receipt, proves both transaction
residue paths absent, and jointly revalidates the exact manifest target and
unique Zettel authority at the final success point. A first approved use may
create the fixed control
artifact; later uses retain and reuse the exact artifact. A wrong, non-regular,
replaced, ambiguous, incomplete, stale, or over-limit input fails closed.

ID and path selection have the same uniqueness boundary. Either selector
performs a bounded, handle-bound scan of both `zettels/` and `inbox/`, requires
the selected Zettel id to occur exactly once, and for a path selector requires
that unique match to retain the selected file identity and exact bytes. A
direct canonical filename never bypasses duplicate-id detection. The writer
repeats this proof under its control artifact before mutation and after final
canonical/receipt/manifest readback; final uniqueness or identity drift raises
inside the CAS rollback boundary and retains reconciliation evidence.

The two-root scan is one stable namespace snapshot. On Windows, exact
`ReadDirectoryChangesW` watches are armed before scanning: an archive-root name
watch protects a missing `zettels/` or `inbox/` root, while subtree watches
protect each existing root. WOM holds all discovered directory identities,
records their complete entry inventories, and re-reads every Markdown file to
verify identity, mode, link count, size, modification/change timestamps,
platform attributes, and SHA-256. It then arms a full archive-root closing
guard, repeats the complete revalidation, cancels the earlier watches under
that guard, and cancels the guard last. `CancelIoEx` plus
`GetOverlappedResult` must prove clean cancellation; a cross-root move,
in-place rewrite, late root creation, overflow, unsupported watch, or ambiguous
completion fails closed. POSIX retains every directory descriptor and performs
the same directory and file version-token, inventory, identity, and digest
revalidation. Restoring former content bytes does not restore the held file
version token. POSIX records the archive-root inventory before probing
potentially absent `zettels/` or `inbox/` roots; creating one after an absence
result changes that existing baseline and fails instead of leaving an
unscanned root in the snapshot.

The final manifest proof shares that stability window. WOM holds the exact
manifest parent and single-link file observation, validates its record set,
revalidates the complete Zettel snapshot, and requires the same parent token,
file identity, metadata, and exact bytes afterward. On Windows the archive-
subtree closing guard remains armed across the interval. Therefore manifest
provenance and Zettel uniqueness have one jointly valid point; alternating a
duplicate and a missing manifest fails inside rollback instead of satisfying
two separate checks at different times.

`archive.yml` is parsed independently by both the operation core and the live
CLI approval boundary from held bytes. The duplicate-key-rejecting approval
YAML loader rejects duplicate mapping keys, then a bounded acyclic JSON-safe
normalization and the exact-human archive-id validator reject ambiguous or
unsupported identity trees before approval.

On Windows, the compare-and-swap never uses a replacement API that can
overwrite a concurrently created `.previous` file. WOM retains write- and
delete-denying handles for the exact old and proposed files, moves the old file
to `.previous` with `FileRenameInfo` replacement disabled, and then moves the
proposed file to the now-absent canonical name with replacement disabled. The
canonical name can therefore be briefly absent. A process exit in that gap
leaves the exact `.previous` plus `.swap` pair for reconciliation; a concurrent
canonical-name winner makes the second move refuse while preserving all three
occupants.

The held old and proposed files must also be single-link, non-reparse regular
files with matching supported security descriptors and semantic attributes.
A handle-bound `BackupRead` inventory permits only the unnamed default data
stream, so alternate data streams, extended attributes, object IDs, sparse
data, unknown backup streams, or unverifiable metadata block before the first
move instead of being lost. After the new canonical identity, bytes, metadata,
and namespace verify, `.previous` is unlinked with `FileDispositionInfoEx`
using `FILE_DISPOSITION_DELETE`, `FILE_DISPOSITION_POSIX_SEMANTICS`, and
`FILE_DISPOSITION_IGNORE_READONLY_ATTRIBUTE`. WOM never falls back to ordinary
delayed deletion. If the filesystem cannot provide that immediate unlink,
canonical-new and `.previous`-old remain as explicit reconciliation evidence.

The v0.2 receipt embeds `wom-kit/operation-exact-human-approval/v0.1` with
operation `zettel_objet_link`. It also records digests and safe archive-relative
coordinates for the strict manifest set, snapshot, control artifact, both
compare-and-swap paths, support effect set, transaction, and receipt
generation. It does not include the optional label, zettel body, object bytes,
provider values, or an absolute local path.

The compare-and-swap files are private transaction artifacts, not disposable
scratch outside the approved operation. During an interrupted or ambiguous
swap, either deterministic path can retain full pre-write or proposed zettel
bytes. WOM does not auto-delete an ambiguous residue, snapshot, or receipt.
An error with `effects_state: unknown` therefore requires reconciliation of
the exact started approval claim and all approved paths before any retry. A
retained receipt alone is recovery evidence, not proof of committed success;
readers require the current canonical zettel, exact snapshot, and for v0.2 the
same exact manifest target before presenting an active link history.

`zettel-objet-link-revert --approve` remains fixed closed in v0.4.1 with
`compound_exact_human_approval_binding_required`. Historical link and revert
receipts remain readable; neither kind is deleted or silently treated as new
authority.

Historical v0.4.0 boundary: the link writer affected canonical zettel bytes,
private snapshot state, and receipt history together, while revert also read
those records before restoring bytes. v0.4.0 had no exact-human binding for
either complete effect set. Both approval branches therefore stopped before
private target read or mutation and wrote no zettel, snapshot, or receipt.

## Failure Contract

For JSON mode, v0.4.1 uses `wom-kit/cli-error/v0.1` for the repaired usage,
policy, and precondition paths:

- malformed or missing command arguments return exit code `2`,
  `error_class: usage`, and `effects_state: none`;
- policy and precondition failures return exit code `1` and
  `effects_state: none` when the exact-human workflow did not start; and
- a caught failure after the exact-human workflow started returns exit code
  `1` and `effects_state: unknown`.

`effects_state: unknown` means the local approval claim must be reconciled. Do
not auto-retry and do not interpret `files_written: []` as proof that no effect
occurred. Every envelope keeps `private_values_echoed: false`.

## What It Scans

The preview looks for:

- `sha256:<64 hex characters>`
- `objet:sha256:<64 hex characters>`

It does not treat provider locators as object refs. For imported Notion page
mentions or embeds, first run `archive notion-objet-link-plan --dry-run` to
match locator fingerprints against reviewed manifest metadata without echoing
provider URLs.

It scans zettel frontmatter and body text, but it does not echo the body text or
frontmatter values back to the caller. Output locations are limited to safe
position hints such as:

- `source: frontmatter`
- `field: frontmatter.source_refs[0].object_id`
- `source: body`
- `line: 12`

## Count Scope Compared With Overview And Catalog

`zettel-objet-links.count` is the number of distinct normalized objet IDs
discovered across the valid frontmatter and body of one non-redacted zettel.
This is deliberately broader than the v0.3.292 overview and catalog
`tie_summary.referenced_objets_count`.

```text
tie_summary.referenced_objets_count
  = distinct structured frontmatter objet relationships

zettel-objet-links.count
  = distinct objet IDs discovered across valid frontmatter and body
```

The tie summary recognizes structured frontmatter sources and exact canonical
edge target fields without reading the body; catalog output therefore keeps
`body_read: false`. This link preview performs the broader read-only scan, so a
body-only objet ID can increase its count without increasing the tie summary.

The link preview deliberately performs a broader recursive token scan across
valid frontmatter plus body text. It can discover a canonical object-ID token
inside arbitrary nested edge metadata, a URL string, or a path string. Such a
discovery is a token occurrence for this link command; it does not make that
location a structured relationship target and does not increase the tie
summary.

Overview and catalog also replace malformed object-shaped or non-string direct
edge targets with the fixed `<redacted-reference>` placeholder. A target that
does not count therefore cannot leak through the neighboring edge preview.
This does not change the broader body/frontmatter scan performed by this
read-only link command.

## Output Shape

For each distinct objet ref, the preview returns:

- normalized `object_id`,
- occurrence count,
- limited occurrence position hints,
- `resolution_state` from the existing objet ref resolver,
- safe local archive-relative candidates,
- safe external store labels,
- command hints for `resolve-objet-ref`.

Local candidates use archive-relative paths only:

```text
objects/sha256/ab/abcdef...
```

External candidates are labels only:

```text
provider: external_prehashed
store_kind: notion_source_export
store_ref: notion-export-20260614
```

## Privacy And Safety Boundaries

`zettel-objet-links` is read-only. In v0.4.1, singular
`zettel-objet-link --approve` is the only writer in this family;
`zettel-objet-link-revert --approve` remains fixed closed.

The discovery preview does not:

- write files,
- echo zettel body text,
- echo frontmatter values,
- print absolute local paths,
- print provider URLs,
- create presigned URLs,
- call provider APIs,
- download objects,
- upload objects,
- read object bytes,
- hash object bytes during link preview,
- prove remote availability,
- decide whether local originals can be deleted.

The approved singular link operation reads the target zettel and strict
manifest metadata. Its complete bound private effect set is the canonical
zettel, exact before-snapshot, create-only receipt, persistent control
artifact, and both deterministic compare-and-swap paths described above. On
verified success the two swap paths are absent; on an uncertain failure they
may remain with full private zettel bytes and must be reconciled rather than
automatically deleted. The operation still reads no object bytes, calls no
provider, checks no network, and echoes no label or zettel body.

Redacted zettels are blocked before the frontmatter/body scan and do not expose
a count, private relationship existence, or link previews. Redacted overview
and catalog surfaces independently return zero ties, empty edges, and
`body_read: false`.

## Relationship To `resolve-objet-ref`

`resolve-objet-ref` resolves one object id.

`zettel-objet-links` finds object ids mentioned by one zettel and then reuses
the same resolver for each id.

That means the link preview inherits the resolver boundary:

```text
manifest metadata in, safe local/external candidates out, no provider action.
```

## Relationship To `notion-objet-link-plan`

`notion-objet-link-plan` is the earlier bridge for imported Notion zets whose
body still contains provider locators instead of stable content refs.

After human review adds `sha256:` or `objet:sha256:` refs, run
`zettel-objet-links` to resolve those stable refs into safe local-client
candidates.

## Future Work

Future reader surfaces can render `archive_relative_path` candidates as
clickable local-client links.

Provider-backed presigned URLs are separate future work. They need explicit
provider binding, credential handling, expiry policy, and user opt-in before
they can safely exist.
