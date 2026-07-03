# Objet Capture Enablement

Status: v0.3.158 objet-capture enablement checkpoint
Date: 2026-07-03

This document describes `archive objet-capture-enable` (alias
`archive capture-enable`): the explicit, receipted, revocable owner consent
flow that lets a real (non-sandbox) archive run local objet capture.

## 1. What And Why

Since v0.3.2, `archive objet-capture` has refused to run outside sandbox-marked
archives (`.wom-sandbox` marker file or top-level `environment: sandbox` in
`archive.yml`). That protected real archives from accidental writes, but it
left no graduation path: a real archive that wants local objet capture — for
example an archive root whose name matches the external live-store protection
pattern (`zettel-kasten-*` / `*-objets`) — was double-blocked with no owner
route forward.

v0.3.158 adds that route. The archive owner can approve a singleton consent
record, `ops/capture-enablement.yml`, plus a receipt under
`receipts/capture-enablement/`. When the record is valid, the objet-capture
gate allows capture without a sandbox marker.

## 2. Scope

The enablement record gates ONLY `objet-capture` (its sole gate consumer is
the objet-capture run path). `derive-text capture` and
`tiro-lossless-recovery-capture` keep their own rules; the record carries
`scope: "objet-capture"` and the gate rejects any other scope value.

## 3. Command Grammar

```text
archive objet-capture-enable <archive-root>
    (--dry-run | --approve --reviewed-by <actor>)
    [--revoke] [--acknowledge-never-touch-name] [--reenable]
    [--format text|json]
```

- `--dry-run` — read-only eligibility report; writes nothing. Returns
  `ok: true` with a `state` field, one of (by precedence):
  `enabled` > `revoked` > `invalid_record` > `sandbox_marked` >
  `not_an_archive` > `not_enabled`; plus the orthogonal boolean
  `never_touch_name_match` (the name pattern never blocks ENABLEMENT, so it is
  not reported as a blocking state), `planned_writes` (the two relative paths
  `--approve` would write; empty for an already-final state; for a `revoked`
  record the actual `--approve` additionally requires `--reenable`), and a
  `reason` string when the state is `invalid_record`. `--dry-run` is also
  valid with `--revoke`: every write has a preview. Note `sandbox_marked`
  reports marker presence, not capture eligibility: on a never-touch-named
  root the CAPTURE gate still refuses without an enablement record (the marker
  cannot override the name pattern; check `never_touch_name_match`).
- `--approve --reviewed-by <actor>` — evaluates every blocker BEFORE any
  write, then writes the receipt first and the record second. Blockers:
  exactly-one-mode, missing/unsafe `--reviewed-by`, `not_an_archive`
  (`archive.yml` missing or without a readable `archive_id`),
  `never_touch_acknowledgement_required` (pattern-matched root without
  `--acknowledge-never-touch-name`), `revoked_record_present_use_reenable`
  (existing revoked record without `--reenable`), and `unsafe_record_path`
  (record/receipt path escapes the root or crosses a symlink/junction).
- `--revoke --approve --reviewed-by <actor>` — loads the existing record,
  sets `enabled: false`, `revoked_by`, `revoked_at`, and writes a revoke
  receipt then the record. Blockers: `nothing_to_revoke` when no record
  exists, `invalid_record_present` when the record is unparseable.
  `--reenable` and `--acknowledge-never-touch-name` are NOT required to
  revoke: revoking must never be harder than enabling.
- `--reenable` — required to approve enablement over a previously revoked
  record, so an operator cannot silently undo a human revocation.

Re-enabling overwrites the singleton record; the timestamped receipts
directory is the audit trail. Receipt timestamps have second granularity, so
two actions within the same second share one receipt file (last write wins).

The command is CLI-only. It is NOT exposed via MCP: a consent command that
writes an owner approval record belongs on the CLI where a human runs it.

## 4. Record Schema

Singleton record at `ops/capture-enablement.yml`:

```yaml
schema: "wom-kit/capture-enablement/v0.1"
scope: "objet-capture"
archive_id: <archive_id from archive.yml>
enabled: true            # the gate checks `enabled is True` (YAML boolean identity)
statement: "I am the owner of this archive and I approve objet-capture writing into it outside sandbox mode."
reviewed_by: <actor>
enabled_at: <iso>
never_touch_acknowledged: true|false
revoked_by: null | <actor>
revoked_at: null | <iso>
```

Gate validity requires ALL of: the record parses to a mapping; `schema`,
`scope`, and `statement` match exactly; `archive_id` equals
`archive.yml`'s `archive_id`; `enabled` is the YAML boolean `true` by identity
(quoted strings such as `"true"`/`"yes"` and integers such as `1` do not
enable; note that the YAML 1.1 loader parses unquoted `yes`/`on` to the
boolean `true`, so those spellings DO enable — write `enabled: true`
explicitly); and, when the root or any parent component matches the
never-touch name pattern, `never_touch_acknowledged` is literally `true`.
ANY deviation — including a raised exception while reading the record or
`archive.yml` — fails closed to a clean refusal, never a traceback. The
timestamp fields (`*_at`) are informational only and are not gate-validated.

Read footprint: when `ops/capture-enablement.yml` is absent the gate performs
a single stat and reads nothing; when present, the gate reads at most the two
control files (`ops/capture-enablement.yml` and `archive.yml`).

## 5. Receipt Schema

Receipts live at
`receipts/capture-enablement/capture-enablement.<compact-ts>.json` (fixed
basename: archive ids contain colons, which would become an NTFS alternate
data stream on Windows):

```json
{"schema": "wom-kit/capture-enablement-receipt/v0.1", "dry_run": false, "approved": true,
 "action": "enable", "archive_id": "...", "record_path": "ops/capture-enablement.yml",
 "reviewed_by": "...", "never_touch_acknowledged": true, "reenable": false,
 "record_sha256": "<sha256 of the record YAML text>", "created_at": "<iso>"}
```

The gate does NOT require receipts: receipts are evidence, enforcement is the
record. `--approve` writes the receipt BEFORE the record so "a valid record
implies at least one receipt" holds across a crash, and doctor warns when a
valid record has zero receipts.

## 6. Gate Behavior After Enablement

For a validly-enabled root, the objet-capture gate allows the run, and the
per-item never-touch checks evaluate the name pattern on the path components
RELATIVE to the enabled root only. The root's own owner-enabled name no longer
re-blocks every item, but a staged item whose OWN relative component matches
the pattern (for example `staging/incoming/evil-objets/…`) still blocks with
`resolved_path_never_touch`. Non-enabled roots keep the absolute-path
semantics unchanged, and `target_looks_external_live_never_touch` itself is
identical in both of its copies (runtime and hygiene checker).

Refusals keep their existing `blocked_by` ids (`sandbox_marker_required`,
`external_live_never_touch`) and gain one additive field,
`enablement_state: "absent"|"invalid"|"revoked"|"disabled"`. Hint strings are
static, blocker-keyed text, not a parsing contract.

## 7. Revocation Is Advisory And Forward-Only

Revoking blocks FUTURE captures. It does not and cannot undo the past:

- already-captured bytes under `objects/sha256/` remain (capture never
  deletes),
- object manifest records remain,
- capture receipts remain,
- the record is last-writer-wins: `--approve --reenable` re-flips it,
- receipts are plain files inside the archive and are deletable in-archive.

Re-approving over a revoked record additionally requires `--reenable`, which
prevents an AI operator from SILENTLY undoing a human revocation — but this is
an honesty measure, not an enforcement boundary.

## 8. Safety Boundary

Stated exactly, without overclaiming:

1. The record is STRICTLY STRONGER than `.wom-sandbox`: the sandbox marker
   cannot override the never-touch name pattern, but the record can (the
   enablement check precedes the name check in the gate). Graduation removes a
   previously-unbypassable name-based protection for exactly the guarded path
   class.
2. Anyone with archive write access can forge enablement: a minimal
   `archive.yml` (any `archive_id`) plus a matching record (plus
   `never_touch_acknowledged` on pattern-matched roots) validates. The
   `archive_id` binding prevents cross-archive COPYING only when the ids
   differ; it does not resist a local forger (`archive.yml` is in the same
   write domain), and clones/backups/forks sharing an id inherit enablement.
3. The receipt proves the command ran with the given `--reviewed-by` string —
   not that a human consented. Two commands can enable and then capture.
4. Revocation is advisory and forward-only (see section 7).
5. Real improvements over the sandbox marker, stated as such: an
   approval-gated command, a named reviewer, a receipt trail, archive-id
   binding, an explicit never-touch acknowledgment, a revocation signal, and
   doctor visibility.

The gate does not require receipts; receipts are evidence, enforcement is the
record.

## 9. Doctor Visibility

`archive doctor` reports:

- INFO `capture_enablement_enabled` (reviewed_by / enabled_at) for a valid
  record,
- INFO `capture_enablement_revoked` (revoked_by / revoked_at) for a revoked
  record,
- WARN `capture_enablement_record_invalid` (with the WHY) for a record that is
  present but does not validly enable capture,
- WARN `capture_enablement_receipts_missing` for a valid record with zero
  receipts under `receipts/capture-enablement/`.

The WARN severity is a contract: it fails strict validation and surfaces via
the MCP `archive_doctor` tool — fail-closed AND loud.
