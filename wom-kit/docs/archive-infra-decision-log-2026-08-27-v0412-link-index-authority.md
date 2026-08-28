# v0.4.12 decision: generation-bound link and index authority

Date: 2026-08-27
Status: accepted for a bounded follow-up release; not implemented in v0.4.11

## Context

The single `zettel-objet-link` workflow currently proves one zet identity by
walking both canonical and inbox trees, reading every Markdown candidate,
revalidating the complete snapshot several times, and repeatedly parsing the
full objet manifest. A recursive Windows change watcher intentionally rejects
tree changes during that proof. This preserves important identity and race
safety, but it also makes a single link slow and causes unrelated concurrent
tree activity to collapse into the same public `zettel_unavailable` result.

The v0.4.11 response is deliberately limited to truthful approval status,
human-readable prerequisite reporting, and honest stale-index wording. It must
not weaken the link resolver or claim that partial index maintenance is already
complete.

## Decision

v0.4.12 will replace repeated full-tree authority discovery with a
generation-bound zet identity projection and a manifest projection bound to
the exact manifest generation or SHA-256. The projection is an accelerator, not
authority by itself. A final stable-point check must still prove the selected
zet generation, ID uniqueness, manifest generation, and approved link target
before any write.

Every canonical write and revert workflow must participate in the existing
index mutation lifecycle. The release may not claim that the index stays current
until all such writers have been inventoried and either integrated or explicitly
classified as index-dirtying blockers.

Once authoritative target identity is proved, an existing exact link is checked
before receipt and write planning so repeated calls return one stable
`already_present` result without unnecessary downstream work.

`current` records the clean watcher-close linearization point. It is evidence
that the indexed source authority was exact at that instant, not a promise that
external writers keep the archive frozen until the command returns. Every
consumer must obtain a fresh current-index proof before using the projection;
it must not reuse an earlier successful response as continuing authority.

## Security invariants

- Do not trust a filename as proof of zet ID.
- Do not remove duplicate-ID detection, reparse-point rejection, descriptor-bound
  reads, or the final Windows stable-point proof.
- Do not return titles, labels, zet IDs, objet IDs, local paths, provider
  values, OS exception text, or low-entropy hashes in public progress or errors.
- Distinguish failures only with fixed, content-free codes such as
  `zettel_identity_projection_stale`, `zettel_tree_changed_during_plan`, and
  `manifest_changed`.
- A stale or incomplete projection fails closed and points to bounded index
  recovery; it never falls back to an unbounded silent approval path.

## Regression requirements

The existing race and identity tests remain mandatory, including duplicate IDs,
same-byte identity swaps, cross-root renames, in-place mutation, manifest drift
after review, and Windows watcher closure. New tests must additionally prove:

1. Twenty unchanged repeated plans produce the same plan digest and public
   status.
2. Twenty unchanged repeated calls for an existing link return
   `already_present`, never `zettel_unavailable` or `plan_changed`.
3. Projection generation drift, canonical writer drift, and manifest drift each
   return their own fixed public reason code without private values.
4. Each canonical write/revert either seals its exact index delta or leaves a
   durable dirty state that blocks authority-dependent commands.
5. Interrupted index delta updates are recoverable and cannot make a stale
   projection appear current.

## Performance and observability release gates

Use a synthetic public-safe fixture comparable to 8,616 zettels, 22,441 objets,
and a 37 MiB manifest.

- First non-empty serialized progress write and its first flush: no later than
  2 seconds each.
- Maximum gap between flushed progress events while work continues: 10 seconds.
- Cold single-link plan p95: no more than 20 seconds on the declared Windows
  reference runner.
- Warm single-link plan and unchanged `already_present` p95: no more than 5
  seconds on that runner.
- The captured serialized progress stream and final benchmark JSON contain
  counts, durations, generations, hashes, and fixed state codes only; neither
  contains archive content or local locations.

The reference runner specification and raw benchmark receipt must ship with the
release evidence. A faster result obtained by disabling any security invariant
does not pass the gate.

## Non-goals for v0.4.11

- No change to `zettel-objet-link` scan, watcher, manifest, plan, apply, or write
  implementation.
- No claim that incremental index maintenance covers every writer.
- No automatic retry that hides archive mutation or approval drift.

## v0.4.12 implementation evidence

The bounded follow-up implementation is documented by the public v0.4.12
release note and this decision record. The exact Windows reference path is
`docs/evidence/v0.4.12-link-index-windows-reference.json`. The earlier v0.1
file timed a callback and scanned only the final JSON, so it is not release
authority. Publication requires a v0.2 replacement from the final candidate
that captures the serialized progress writes and flushes, scans that stream,
and binds source-tree, commit-object, benchmark-script, wheel-byte, and
wheel-package-tree hashes. Pull-request CI builds the wheel outside the checkout
and reruns the full profile on Windows.

Release remains conditional on writer-wide lifecycle regression, the complete
supported CI matrix, packaged-wheel verification, and public release-asset
verification. This implementation evidence does not modify a client archive
and does not by itself resolve any private feedback report.
