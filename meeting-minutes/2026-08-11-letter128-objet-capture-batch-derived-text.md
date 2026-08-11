# Letter 128 objet-capture-batch derived-text omission

Date: 2026-08-11

## Intake boundary

While the Letter 127 project-update hotfix was still in progress, the user
authorized reading one exact new feedback letter from the protected beta
archive. Only that named letter was opened. No staged source, PDF, extracted
text, zettel, object, receipt, provider, credential, or other protected file
was inspected or changed.

The source letter and protected archive were not modified. No source filename,
path, body excerpt, or file digest is copied into this project record.

## Reported incident

A v0.3.314 beta runtime received one valid multi-item
`wom-kit/objet-capture-batch-request/v0.1` request whose reviewed rows paired
source items with BOM-free UTF-8 derived text. The sources had already passed
source intake, and paired rows included their source receipt, derived-text
staging reference, parser provenance, review state, language, and born-digital
metadata.

Both dry-run and approved execution reported complete success for the reviewed
set. The source items were captured byte-exactly. The requested derived text,
however, did not appear in the selection, command result, derived-text object
store, or derived-text receipt store. No warning or blocker disclosed that the
schema-valid fields had been ignored.

The beta operator did not run a manual workaround. The already captured source
objects remain preserved while an official recovery path is awaited.

## Preliminary severity

This is a P1 product and completion-truth failure unless development evidence
disproves the report. The source bytes were not lost, but a valid requested
artifact class was silently omitted while the command reported whole-batch
success. A user could reasonably believe that paired derived text and its
provenance had been preserved when they had not.

## Required investigation

- Trace the request JSON Schema through the CLI adapter, selection manifest,
  paired capture service, result projection, and receipts.
- Reproduce the omission in a disposable fixture, including a Korean path and
  BOM-free UTF-8 derived text.
- If paired batch capture is supported, preserve all schema-valid fields and
  make requested, planned, written, and blocked derived-text counts explicit.
- If it is not supported, fail closed in dry-run whenever any paired field is
  present. Silent discard is forbidden.
- Whole-batch `ok` and `written` require requested-versus-written equality for
  both source and derived artifacts.
- Provide an official reconcile operation that attaches only the missing
  derived text to already captured source objects without copying those source
  objects again, and binds the original batch/item provenance.

## Sequencing decision

Letter 127 work continues without interruption because it blocks clients from
updating at all. Letter 128 is recorded as a separate mandatory workstream and
is being diagnosed in parallel against the development repository. No release
will be called beta-ready while either known P1 remains unresolved or lacks a
safe operator procedure.

## Root cause and implemented correction

The lower objet capture engine already supported a reviewed source/derived
pair. The bounded batch adapter, however, rebuilt each selection item with only
the original fields. It silently discarded schema-valid derived fields before
the lower engine saw them. Its summary therefore described the adapter's
reduced plan rather than the full reviewed request.

The correction keeps the request schema compatible while enforcing a strict
closed shape, duplicate-key rejection, paired-field dependencies, legacy/current
model-name conflict rejection, and null-safe confidence/language values. The
adapter preserves the entire reviewed pair into an exact selection and passes
that selection directly to the lower engine.

Apply now verifies the archive identity, exact selection identity and digest,
exact item set and shapes, receipt route, and exact `files_written` delta before
claiming completion. Request, staged source, and derived source reads are
stable, regular-file, no-follow, and bounded. Public results and the
attempt-bound batch receipt carry separate original and derived requested,
written or ready, skipped, and blocked partitions.

Publication result is tri-state across objects, manifests, and receipts:
verified write, verified no-write, or unverified. Possible durable writes
followed by an exception no longer become guessed zero-write counters.
`partial`, `evidence_incomplete`, `recovery_required`, and
`batch_capture_outcome_unverified` provide fixed state-specific safe actions
and prohibit automatic replay.

## Recovery and release boundary

An unchanged reviewed request can be dry-run again under v0.3.315. Exact
existing originals converge as skipped while missing derived halves can be
completed. If original staging bytes are unavailable, durable original capture
receipt object IDs can feed a separately reviewed `derive-text capture
--from-manifest` request; originals need not be copied again.

Focused feature and adversarial tests now cover selection binding, partition
truth, bounded stable reads, publication ambiguity, partial/recovery routes,
legacy receipt compatibility, and text/JSON CLI projection. This establishes
local implementation evidence only. Package synchronization, release checks,
fresh installation, prior-client execution, and human acceptance remain
separate gates.
