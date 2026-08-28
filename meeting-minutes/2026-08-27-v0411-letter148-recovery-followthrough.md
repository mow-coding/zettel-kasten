# v0.4.11 Letter 148 recovery follow-through

Date: 2026-08-27

## Chronology and intent

The user asked WOM development to continue until recurring beta-client
problems are genuinely resolved, while keeping public/private boundaries,
client-controlled writes, repository cleanup, and WOM's philosophical product
language intact. The user additionally required approval messages to follow the
canonical `WOM`, `zet`, `ZET`, `objet`, `엣지`, `타이`, `발행`, `폐기`, and
`퇴역` distinctions already recorded for future preview work.

Feedback 148 was read from the private client archive without changing it. The
report was generated under v0.4.9 and is therefore valid evidence for the
v0.4.9 behavior it describes. It confirmed that two previously stuck mint
operations and two missing-file intake/capture paths completed, while exposing
remaining runtime, Doctor, lifecycle, provider, relation, and cleanup work.

The v0.4.10 public release had already shipped before this follow-through. It
fixed the bounded batch approval scope from Feedback 147 and removed the Git
subprocess fan-out behind one v0.4.9 version-inspection failure. It did not
silently install into or write the client archive.

## v0.4.11 investigation

The old Doctor-performance commit was transplanted from its v0.4.9-based
branch onto a dedicated worktree based on the exact v0.4.10 merge. Independent
review found that it was a useful performance foundation but unsafe as-is:

- the default changed from deep to operational verification;
- operational success could hide same-size objet corruption;
- path-only text/hash caches could become stale;
- cached zet text could hide a newly introduced secret value;
- no actual Letter 148 scale benchmark existed;
- new user copy used `object` instead of canonical `objet`.

The implementation direction was corrected. Deep remains the default, strict
mode requires deep verification, operational scope explicitly withholds a full
integrity claim, secret scanning is fresh, caches are identity-bound, and deep
objet bytes are hashed exactly once at completion with descriptor/path stability
checks and progress heartbeat support.

Runtime inspection was independently traced into two separate causes. The
v0.4.9 per-file Git subprocess budget problem is fixed in v0.4.10. A second
contradiction remains: static receipt candidates are intentionally not live
verified, but the caller treated that conservative value as automatic runtime
failure. The new design keeps static receipt evidence and current process
binding separate, and the writer guard checks both rather than trusting the
version string alone.

## Mint lifecycle findings

The paired 3,345 canonical mint mismatches and 3,346 retired-draft mismatches
must not be treated as 6,691 unrelated failures without evidence. Later
zet–objet links and field-scoped local recovery may have legitimately changed
`frontmatter.assets` after minting.

Direct link receipts can prove full-file before/after SHA transitions when a
unique, cutoff-respecting, branch-free chain reaches the current SHA. The
historical receipt format provides internally consistent exact-byte transition
evidence but not a cryptographic MAC/signature claim.

The v0.4.7 local-recovery writer instead binds field-local pre/post hashes,
control, checkpoints, final receipt, and supersession. It cannot be converted
retroactively into a chronological full-file SHA chain. WOM can reconstruct an
exact mint-anchor candidate only when the complete recovery evidence validates,
current `assets` equals the proven field result, and body/title/all unrelated
frontmatter remain byte-equivalent. Because the old final receipt has no bound
completion time, this becomes a precise
`field_scoped_assets_state_evidence_without_chronology` error category; it does
not soften the mint mismatch. Any ambiguity remains an ordinary error.

Only canonical and retired diagnostics with the same archive, zet id, target,
expected SHA, current SHA, and exact mint-receipt relationship may be folded
into one logical issue. Folding changes presentation counts, not historical
receipts or evidence severity.

## Current implementation boundary

Development changes are confined to a dedicated v0.4.11 worktree. The client
archive remains read-only during development, no provider is called, no
credential is read or requested, and the global PATH executable is not
replaced. A release is not complete until focused tests, the Letter 148 scale
gate, full CI, public wheel verification, and task-owned branch/worktree cleanup
all succeed.

## Approval language correction

The user clarified that target-identifying approval messages must use WOM's
existing philosophical notation, not generic developer vocabulary. A focused
audit found legacy Windows approval copy that still said `제텔`, described
post-mint retirement as `폐기`, and used `객체` for duplicate objets. The
current v0.4.11 worktree corrects those native-dialog labels, questions,
summaries, and buttons to the canonical `zet`, `objet`/Korean `오브제`, `엣지`,
`발행`, and `퇴역` meanings. The exact mint question is now
`이 zet를 정본으로 발행할까요?`.

Official Microsoft Task Dialog and UI-text guidance was checked before fixing
the target-preview direction. It supports one short, specific human question,
supplemental context needed for the choice, and progressive disclosure for
machine details. WOM will therefore show safe target identity and human meaning
before internal relation codes or hashes. Sensitive body, absolute path, and
evidence are not added to the popup or public artifacts; existing bounded local
read surfaces remain the inspection path. This is presentation work on top of
the exact plan binding; it does not weaken the write gate or make the operator
verify system-maintained counts.

## Target preview and Markdown correction

The user asked for the actual draft, zet, edge endpoints, or objet to be visible
before a native decision, even while v0.x remains no-custom-UI. The first
implementation derives a small local-only preview from the already validated
operation plan. Only identities already covered by the operation's existing
plan/target binding may be shown. Unbound optional titles are omitted, a missing
bound identity fails before approval, and preview values never enter the public
binding, receipt, log, machine detail, or compatibility context hash. AI draft
creation can show its filename and title because both are covered by its source-
fidelity plan.

The user also reported that Korean range notation such as `3~5` and incomplete
`**`/`~~` markup could render incorrectly. WOM now produces a display-only
Markdown projection for the unpaged document view and leaves canonical zet
bytes and body-only/paged reads unchanged. The projection preserves code,
autolinks, ordinary URLs, link destinations, HTML syntax/blocks, and deliberate
strong/strike markup while escaping only ordinary single range tildes and exact
unpaired double runs. Container-ended fences and paragraph-continuation
indentation are tracked. Backslash parity is linear rather than quadratic.

An independent audit found and blocked several release candidates before merge:
unbound target descriptions, Unicode line-separator spoofing, URL/HTML
rewrites, and code-container overreach. The fixes reject U+2028/U+2029 and
missing bound identities, remove unbound titles, preserve non-text Markdown
syntax, and add the exact repros as regression tests. The 16,000-backslash
case improved from about 14.87 seconds in the audit to about 0.02 seconds on
the development machine.

## Exact-scale Doctor result

The release-scale synthetic archive used 22,441 unique objets, 8,612 zets,
3,345 mint receipts, and 3,346 retired-draft receipts. A competing run under
unrelated heavyweight test contention exceeded the time contract; it is kept
as failed evidence and is not reported as a pass.

The isolated final run, repeated after the final descriptor-cache and SQLite
boundary regression coverage, completed the operational check in 116.991098
seconds and the default deep check in 112.526742 seconds. Both produced their first
status at 0.0 seconds and kept the maximum heartbeat gap to 5.0 seconds. The
operational mode read no objet bytes and classified all 22,441 as byte
integrity unverified, as its contract requires. The deep mode performed exactly
22,441 stable descriptor-bound hashes, one per unique objet path, and then
revalidated all 22,441 as current at completion. Each main manifest, stage,
zettel, inbox, mint-receipt, and retired-receipt source was scanned once, and
the public output contained no synthetic private title, body, or path sentinel.

The deep completion-and-hash phase improved from 228.418346 seconds to
21.294631 seconds without weakening the stable-file observation contract.

## Final regression loop

The changed-file suite first reported four failures among 1,956 passing tests.
Two showed that detail throttling had also suppressed the per-receipt liveness
events needed for a bounded heartbeat. The implementation now emits minimal,
content-free liveness for every receipt while keeping detailed progress
throttled.

The other two were Windows-only approved-edge evolution failures. Replacing
`Path.read_text()` with a descriptor-bound byte reader had preserved CRLF in
the parsed text, unlike the historical universal-newline contract. The stable
byte read remains intact, but decoding now applies the existing strict UTF-8
universal-newline helper. The four failed cases, the explicit CRLF regression,
and the final exact-scale benchmark all passed after the correction.
