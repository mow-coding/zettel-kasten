# Objet Capture Enablement

Status: v0.3.158 objet-capture enablement checkpoint
Date: 2026-07-03

Current v0.4.0 boundary: enable, revoke, and reenable approval fail with
`compound_exact_human_approval_binding_required` before archive read or
mutation. The state preview remains read-only; no enablement record or receipt
is written. Approval examples below are historical.

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

## 3. Current Command Grammar

```text
archive objet-capture-enable <archive-root> --dry-run
    [--revoke] [--acknowledge-never-touch-name] [--reenable]
    [--format text|json]
```

Dry-run is a read-only eligibility/state report and writes nothing. It may
classify `enabled`, `revoked`, `invalid_record`, `sandbox_marked`,
`not_an_archive`, or `not_enabled`, and may show the historical planned record
and receipt paths without authorizing them.

In v0.4.0 every enable, revoke, or re-enable approval returns
`compound_exact_human_approval_binding_required` before reading private archive
targets or writing a record/receipt. No flag combination reactivates the
historical writer. The command is CLI-only and has no MCP writer.

## 4. Historical Record Schema

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

## 5. Historical Receipt Schema

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

Historical gates did not require receipts: receipts were evidence and the
record was enforcement. v0.4.0 creates neither artifact. Doctor may still warn
when an existing historical record has no matching receipt.

## 6. Gate Behavior For Existing Historical Enablement

Historically, a valid enablement record let the capture gate continue to the
per-item never-touch checks. In v0.4.0 an existing record grants no capture
authority: enablement, selection, and capture approval return
`compound_exact_human_approval_binding_required` before private target reads or
mutation. Relative-component and `resolved_path_never_touch` rules remain
available to dry-run validation and historical audit only.

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
- the historical record was last-writer-wins; v0.4.0 cannot re-enable it,
- receipts are plain files inside the archive and are deletable in-archive.

A revoked historical record stays revoked through this command in v0.4.0;
approval is fixed fail-closed.

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
