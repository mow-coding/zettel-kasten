# Decision Log: v0.4.0 Letters 136–137 Operator and Approval Integrity

Date: 2026-08-20

## Context

One day of real archive work exposed thirteen connected operator frictions:
ambiguous scratch ownership, hidden path and document-shape requirements,
misclassified root failures, incomplete approval replay guidance, an objet-only
source-fidelity authority, missing receipt lookup, immutable feedback records
without an obvious withdrawal route, global argparse noise, and inconsistent
approval-value locations.

The successful safety properties must remain: batch intake, separate plan and
write review, receipt-backed rollback, private-value non-echo, and immutable
history.

A follow-up review showed that these frictions can also produce false approval
evidence and circular source-fidelity claims. A caller-supplied `person:*`
string or CLI affirmation is not proof that a human reviewed exact publication
bytes, warnings, and checklist. An AI-authored body captured as an objet is not
independent external evidence for that same body.

## Decision

1. Release the response as v0.4.0. It adds compatible public lookup, vocabulary,
   and reviewed-evidence surfaces, so the repository's SemVer rule requires a
   minor release rather than another v0.3 patch.
2. Keep scratch deletion archive-local. A separately bound project root may be
   inspected for a content-free same-name warning, but inventory and GC never
   adopt or delete that external root.
3. Add one common, additive approval-handoff envelope while preserving every
   existing result field. The envelope identifies required options, safe value
   locations, and whether exact replay is required without reflecting private
   inputs.
4. Add a reviewed session-evidence authority alongside manifested objets.
   Private source bytes move only from an allowlisted scratch input into an
   ignored local profile path; the durable public-side receipt contains safe
   digests and review evidence, not the source text or locator.
5. Add bounded, internally validated link-receipt lookup and direct operators
   to the existing revert-then-relink path. Existing link receipts have no MAC
   or signature, so lookup must never describe them as authenticated. Do not
   mutate old link receipts.
6. Keep feedback references immutable. Verify a composed body before creating
   a body-bound record, warn on legacy generic references, and expose the
   existing archive transition as the official withdrawal path.
7. Expose facet vocabulary and warn on unknown keys. Do not turn the current
   extensible facet map into a breaking allowlist.
8. Report archive-root, request-shape, proposal-shape, index-remediation, and
   subcommand-argument failures at the boundary that actually failed.
9. Require a fresh one-use approval-handoff receipt, bound to exact operation,
   body, frontmatter, warnings, checklist, and reviewer, before v0.4
   high-impact publication and relationship writes accept human approval.
10. Add a human-artifact registry and closeout gate. External roots are only
    included after explicit local registration; scanning does not grant GC or
    deletion authority.
11. Detect circular self-source authority, support reviewed multi-source
    bundles and human-reviewed summaries without claiming machine semantic
    verification, and retain v0.3 receipts as auditable legacy evidence.
12. Add a read-only approval-integrity audit and append-only repair plan for
    legacy unbound approval, circular fidelity, and affected canonical, edge,
    or retired-draft receipts. Do not silently rewrite old evidence.
13. Classify duplicate-object blockers and local instruction-policy conflicts,
    then provide fixed remediation or precedence guidance before new work.
14. Treat writer entry as an uncertainty boundary. Only a well-formed
    `ok: true` result may finalize an exact-human claim as `succeeded`; any
    writer-level non-success leaves the one-use claim `started` with
    reconciliation required. A generic `ok: false` cannot prove that no
    canonical file or immutable receipt was already committed.
15. Fixed-close every discovered public high-impact writer that still relies
    on `--approve`, a reviewer label, or an unauthenticated legacy receipt.
    Preserve its dry-run, plan, and audit surfaces, but do not let a legacy
    metadata record authorize future provider, credential, canonical,
    provenance, export, or bootstrap effects.
16. Make exact approval digests deterministic across the approval dialog.
    Bind scratch-cleanup candidates, hashes, policy, and all durable mint
    targets, but exclude the fresh timestamped cleanup-receipt locator from
    `would_change` projections because it is generated independently on each
    dry run and is not the approved cleanup effect itself.
17. Revalidate approved scratch-cleanup candidates immediately before deletion.
    The mint writer passes its approved candidate projection to GC; path,
    state, size, digest, plain-file status, and file identity must still match.
    Drift preserves the replacement and turns the already-committed mint into
    an explicit reconciliation-required partial result.
18. Make the release-time wheel checker enforce the v0.4 onboarding and
    runtime-skill boundaries. It must verify useful dry-runs and zero-effect
    fixed-close approved writes, not reopen or claim success for retired
    `onboard`, runtime-skill install, or runtime-skill uninstall approval
    paths. Strict Doctor still runs through the freshly installed entrypoint,
    using the checked-in fake archive as its non-private fixture.
19. Apply the same authority rule to packaged Python modules, not only CLI and
    MCP. Concrete claim minting, native/key access, credential/provider
    brokers, lifecycle/evidence committers, recovery storage/execution, and
    live network/transport engines are underscore-private. Their old public
    module attributes and exports are absent. Safe plans, validation data,
    projections, and read-only audits remain public.
20. On Windows, compare path and open-handle identity using stable creation time
    plus device, inode, mode, size, and mtime. Path ctime and fd ctime may be
    different NTFS observation surfaces, so each surface must remain internally
    unchanged before/after instead of being compared across surfaces. File
    type, byte count, SHA-256, and final identity still have to match exactly.
21. Reject non-boolean approval and dry-run values before private reads. The
    canonical fixed-close inventory contains 79 top-level commands; integer or
    custom-object lookalikes must not enter a historical writer branch.
22. Treat the four-shard manifest, pytest-native set, standard wheel checker,
    fresh virtual environment, and release-readiness suite as one frozen-byte
    release gate. A focused fix invalidates only the shard whose current source
    manifest changed; the manifest must be recomputed before accepting that
    narrower rerun.
23. Keep the historical Notion typed-property loss investigation outside
    v0.4.0. Current recovery is body/location-only and is not evidence of a
    complete source mirror. Start the read-only typed-property audit and
    exact-approval/CAS backfill track immediately after the security release.

## Consequences

- Existing v0.3 result fields, object-backed fidelity receipts, and read-only
  plans remain readable. Legacy write commands without a complete exact
  binding are intentionally unavailable in v0.4.0 rather than being treated
  as compatible approval paths.
- New schemas and optional fields require synchronized packaged resources and
  a full v0.4.0 release note, CI, wheel, and fresh-install verification.
- Direct in-place link-label edits and feedback-reference rewrites remain
  unsupported. Corrections are append-only, approval-bound, or receipt-backed.
- Existing v0.3 write receipts remain readable, but they do not become valid
  v0.4 exact-human-review evidence merely because they contain an actor label.
- A structurally valid legacy approval or handoff receipt is advisory metadata,
  not future execution authority. Its public audit result must say so.
- Recomputing an unchanged mint plan before the write yields the same approval
  digest even when the eventual scratch-cleanup receipt filename changes; a
  cleanup candidate or candidate digest change still invalidates approval.
- Scratch cleanup is not treated as a best-effort success after an approved
  mint. If approved bytes drift after canonical effects are committed, the
  exact claim remains `started` and automatic retry is prohibited.
- The wheel-install evidence schema advances to v0.3 and reports onboarding
  and runtime-skill writes as fixed closed; a passing release check is not
  evidence that v0.4 created a new archive or changed a host skill target.
- A caller cannot turn a synthetic native object, arbitrary key, reviewer
  label, capability-shaped document, generic callback, or directly imported
  transport into public write authority. Private cores remain testable only by
  explicit internal names so their atomicity and tamper invariants stay covered.
- The Windows scratch cleanup comparison no longer flakes on path-vs-handle
  ctime representation, while any real drift in either surface, identity,
  bytes, or digest remains fail closed.
- The implementation and tests use isolated fixtures only. No real personal
  archive, credential store, provider, or external service is mutated.
- Historical typed-property loss remains a high-priority data-integrity debt,
  but no generic Notion-mirror-to-canonical writer exists in v0.4.0. The
  follow-on must detect populated unmapped values before proposing any
  idempotent, exact-approved repair.
