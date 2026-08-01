# Private Objet Metadata, Safe Labels, And Reviewed Registration

Status: v0.3.295 pure contract plus v0.3.296 approval-gated local writer

## Why This Contract Exists

Content-addressed storage correctly uses SHA-256 as object identity, but people
usually remember a document by a human name. WOM preserves both facts without
confusing them:

```text
SHA-256 remains identity.
Human names are provenance-bound aliases.
Aliases never rename bytes, merge objets, or prove object equality.
```

v0.3.295 defined deterministic private metadata normalization and
audience-safe projection. v0.3.296 adds one CLI-only writer that can register
one human-reviewed private observation without absorbing the later index or
finder authority.

## Public Schemas

The v0.3.295 contract remains normative:

- `wom-kit/private-objet-source-metadata/v0.1`; and
- `wom-kit/objet-safe-label-projection/v0.1`.

v0.3.296 adds five closed Draft 2020-12 contracts:

- `wom-kit/private-objet-source-metadata-intake/v0.1`;
- `wom-kit/private-objet-source-metadata-write-plan/v0.1`;
- `wom-kit/private-objet-source-metadata-authority-chain/v0.1`;
- `wom-kit/private-objet-source-metadata-write-receipt/v0.1`; and
- `wom-kit/private-objet-source-metadata-write-journal/v0.1`.

The source schemas and packaged resource mirrors are byte-identical. Runtime
validation stays dependency-light; CI also checks the schema documents with a
Draft 2020-12 oracle.

The intake accepts only a reviewed observation and its evidence: SHA-256 objet
identity, privacy class, original filename and input profile, source-declared
media observation or an explicit unknown, source-observed byte count, closed
source provenance, and a human-review evidence digest. It rejects
caller-supplied normalized names, aliases, labels, search keys, registry
results, derived MIME claims, duplicate keys, non-finite numbers, BOMs,
malformed UTF-8/JSON, surrogate scalars, and additional properties.

## Identity And Evidence Boundaries

The durable row keeps these axes separate:

- original, decoded, NFC, NFD, stem, and extension name evidence;
- source-declared MIME evidence;
- source-observed size evidence;
- source-system and source-record/attachment provenance;
- candidate label evidence and review evidence; and
- private or restricted protection level.

v0.1 does not infer MIME from a suffix or the operating system. It accepts only
`unknown` or `source_declared` MIME basis, writes size as
`source_observed`, and keeps registry status, extension agreement, and
confusable checking at fixed `not_checked`/`unknown` states. Registration does
not prove object-byte availability, manifest-size agreement, source coverage,
or external storage health.

## Filename Normalization And Safe Labels

The pure reference module supports either literal Unicode or one strict UTF-8
percent-encoded component.

- Literal input is never percent-decoded.
- Encoded input is decoded exactly once, and `+` remains a literal plus.
- Malformed escapes, invalid UTF-8, BOMs, residual `%HH`, path separators,
  NUL, controls, Unicode separators, and pinned bidi controls block
  derivation.
- NFC and NFD use `unicodedata2==17.0.1`, whose data version is Unicode
  17.0.0.
- NFKC and NFKD never define the canonical filename.
- A filename or derived name longer than 512 Unicode scalars is blocked
  without truncation.

The writer never trusts caller-supplied derived fields. It invokes the exact
v0.3.295 normalizer and builds either no label candidate for a blocked name, one
accepted original-filename candidate for valid literal input, or one accepted
decoded-filename candidate for valid encoded input.

Private and restricted projections use fixed precedence and deterministic
evidence ordering. Equal-priority distinct labels remain ambiguous. The
`public_generic` branch remains structurally unable to contain a free-form
filename, source identifier, path, provider locator, secret, or private
ambiguity detail.

## Content-Free Dry-Run

Use an archive-relative private intake path and bind its exact byte digest:

```powershell
archive objet-source-metadata-write <archive-root> `
  --intake <archive-relative-private-json> `
  --expected-intake-sha256 sha256:<64-lowercase-hex> `
  --dry-run `
  --format json
```

Dry-run creates no lock, directory, journal, temp, manifest row, receipt,
database row, or index. It opens no object bytes, provider, network,
credential store, or external local store.

The result contains only safe archive identity, digests, closed states and
actions, bounded counts, fixed reason codes, and a next-command skeleton. It
does not echo the filename, source record or attachment id, intake path,
reviewer, provider locator, absolute path, raw evidence, or private exception
text.

The deterministic plan binds the intake and canonical-row digests, exact
object-manifest authority, private-manifest before/after states, receipt
directory projection, journal and owned-temp states, complete prior
row/receipt authority-chain digest, normalization profile, action, resource
bounds, and deterministic receipt family.

## Approval Boundary

Approval requires the exact dry-run plan plus two explicit human statements:

```powershell
archive objet-source-metadata-write <archive-root> `
  --intake <archive-relative-private-json> `
  --expected-intake-sha256 sha256:<64-lowercase-hex> `
  --expected-plan-sha256 sha256:<64-lowercase-hex> `
  --approve `
  --reviewed-by operator:<safe-token> `
  --affirm-private-metadata-reviewed `
  --affirm-external-writers-quiescent `
  --format json
```

v0.3.296 approval mutation is supported only on Windows 10 version 1607 or
newer and Windows 11, on a local NTFS volume. Read-only planning remains
cross-platform. Unsupported platforms and filesystems fail closed; there is no
path-based or simulated write fallback.

The quiescence affirmation means every other WOM and non-WOM process that
could create, write, rename, link, replace, or delete an archive child remains
stopped for the complete approval. Hardened locks are defense in depth for
cooperating manifest writers; they do not make a process that violates the
affirmation safe.

Approval retains and revalidates exact directory/file identities, acquires the
object-manifest lock before the private-manifest lock, and rebuilds the same
plan inside both locks. The supported mutation profile uses guarded Win32
create-if-absent materialization, create-if-absent hard-link publication,
source-handle-guarded absolute manifest rename, handle disposition, and
regular-file flush. It never falls back to `os.replace`, shell, subprocess,
provider, or network mutation.

The public profile name is:

```text
windows_ntfs_win32_process_interruption/v0.1
```

This profile supplies process-interruption restart and recovery evidence. It
does not claim that directory-entry or volume metadata durability across a
sudden power loss was verified.

If an abnormal Windows API state leaves terminal raw-handle release unproved
after three consecutive close-and-validity cycles, the approval process
fail-stops with exit code 74 and emits no normal JSON result. A fresh dry-run
must then classify the current state. The interrupted invocation does not
report the affected residue as either preserved or removed.

## Durable Row, Journal, And Receipt

The canonical private manifest is:

```text
objects/manifests/private-source-metadata.jsonl
```

Every new row is canonical UTF-8 JSON plus one LF. Before an append, the
writer validates every existing row and its historical receipt binding. A new
row is allowed only when the target object occurs exactly once in the existing
object manifest and that object authority remains unchanged at the commit
boundary. Existing valid rows are never changed, reordered, or deleted.

One deterministic manifest-wide journal plus authority-key-derived owned temp
names make interruption state discoverable. The journal freezes the exact
accepted append plan, before/after manifest states, actor-bound receipt,
receipt digest, and owned paths. It authorizes cleanup only for those exact,
identity-verified artifacts.

The final receipt is an immutable private artifact under:

```text
receipts/objects/private-source-metadata/
```

Its basename is derived from the observation-evidence authority key, never
from a filename, source id, local path, reviewer name, timestamp, or random
value. The receipt binds the original accepted append plan, object and
observation evidence, exact manifest transition, normalization profile,
review evidence, safe operator token, quiescence fact, and closed no-call facts.
A `restricted` row produces a `restricted` receipt; privacy is never lowered.

## Replay, Rollback, Recovery, And Manual Hold

The content-free state machine distinguishes:

- `append`: clean authority can register the reviewed observation;
- `rollback_required`: pre-manifest interruption left only exact owned
  evidence, so a separately approved plan removes that evidence and stops;
- `recovery_required`: the exact final row exists without its receipt and the
  valid journal proves the interrupted append;
- `already_applied`: the row, immutable receipt, and complete authority chain
  verify exactly;
- `manual_hold`: authority is ambiguous, invalid, changed, orphaned, or cannot
  be safely described; and
- `blocked`: caller, environment, or prospective resource conditions refuse
  the action without authority/content mutation.

Exact replay returns the original receipt without rewriting its bytes, mtime,
action, or original operator token. A different canonical row for the same
observation is a collision, not a second receipt. Rollback and recovery never
delete ambiguous or merely equal-bytes evidence.

Observation-time `manual_hold` returns an exact current
`plan.action=manual_hold` plan when that plan is constructible. An
execution-time failure after accepting an append, rollback, recovery, or
already-applied plan instead returns the byte-identical accepted plan with its
original action and adds one closed, non-authoritative `hold_context`.
`hold_context` reports only a fixed failure stage, last verified authority
state, and cleanup state. It grants no new mutation authority and contains no
path, identifier, count, byte value, or free text.

Ordinary `FileRenameInfo` preserves the checked replacement profile, but an
uncoordinated process that has the current private manifest open can make NTFS
return `ERROR_ACCESS_DENIED` before replacement. That outcome is an
execution-time `manual_hold` with the accepted before-state preserved and
attempt-owned journal/temp evidence removed when cleanup verifies. Let the
reader release the file, obtain a fresh dry-run, and approve that fresh plan
again. The release claims atomic old-or-new reader observations; it does not
claim wait-free progress through uncoordinated readers.

## Rediscovery Status And Deferred Work

v0.3.296 changes the checked-layer status for
`private_original_name_metadata` to `unchecked` with:

```text
private_metadata_rediscovery_not_checked
```

The writer exists, but no receipt-bound private index or private rediscovery
query exists, and no private index freshness is proven. The layer therefore
remains non-complete, contributes nothing to a negative absence claim, and
cannot make a remembered filename searchable.

- v0.3.297 owns receipt-bound generated-index ingestion and freshness.
- v0.3.298 owns the local private finder.
- v0.3.299 owns source-reference coverage versus storage integrity.

External local-store registration, object-byte verification, provider access,
database/index writing, MCP writing, and UI remain separately reviewed work.
