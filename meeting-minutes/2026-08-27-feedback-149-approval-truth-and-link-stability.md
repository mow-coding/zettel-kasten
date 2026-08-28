# Feedback 149: approval truth and zet–objet link stability

Date: 2026-08-27

## Intake boundary

The user asked development to read the newly delivered Feedback 149 while the
v0.4.11 Letter 148 work continued. The original letter was read only from the
private client archive. It was not copied into the public development project,
and the client archive was not changed.

Feedback 149 is independent of Feedback 148. It reports successful mint,
retire, edge, and source-fidelity work, then identifies three larger gaps:

1. approval truth differs between `capabilities`, planning output, and help for
   fixed-closed `zet-revision-write` and `discard-draft` operations;
2. an approval-available `zettel-objet-link` plan can be slow and
   nondeterministically return `zettel_unavailable` or `plan_changed`, including
   an inconsistent result for an already-present link;
3. one canonical write invalidates the broad search index, while mint copy
   describes that stale-index state as a possible duplicate zet.

It also reports two smaller interaction defects: a nominally optional
`--dry-run` that is operationally mandatory for `zet-self-contained-check`,
and staged create-draft prerequisite errors that should be reported together.

## Initial decision

The report must not be answered by opening every closed writer. The client's
explicit request is earlier, consistent truth: a fixed-closed operation must
say so in its plan and help before a person prepares a full proposal. This is a
small, high-value contract correction and is a candidate for the current
release if it can reuse the existing parser-derived approval inventory without
duplicating policy.

The zet–objet link instability is a correctness issue in an already-open
writer and therefore has higher priority than adding a new writer. It requires
an independent code-path audit and large-archive performance proof; blind retry
must not become the product behavior. Incremental search-index maintenance is a
separate state-management change and should not be claimed complete merely by
correcting the stale-index message.

## Work routing

- Continue the in-progress v0.4.11 runtime, Doctor, approval-language, and
  Markdown display work without writing client data.
- Independently trace Feedback 149 against current v0.4.10 code and identify
  the smallest honest release boundary.
- Include fixed-closed plan/help truth and misleading stale-index wording only
  if their shared-policy tests are complete.
- Include `zettel-objet-link` only after the unavailable/plan-changed race and
  full-scale cost have a deterministic test and bounded fix.
- Defer incremental index mutation if it cannot be isolated safely; document
  that correcting the message does not remove rebuild cost.

No provider, credential, global executable, or private archive write is
authorized by this feedback intake.

## Implemented v0.4.11 boundary

The bounded truth corrections were implemented without opening any additional
writer. A shared fixed-close registry now drives CLI help, capability status,
revision planning, and discard planning. A successful read-only proposal
validation may retain its validation digest, but the structured result says
`approval_fixed_closed`, `approved_write_implemented: false`, and
`actionable_handoff_available: false`; it issues no writer handoff or next-step
command that pretends approval is available.

`zet-self-contained-check` is always read-only and accepts omission of the
compatibility `--dry-run` flag. AI create-draft approval reports all five
missing replay/evidence options together in stable order without echoing their
values. Stale index failures use a dedicated rebuild-required message and no
longer call the state a possible duplicate canonical zet.

The existing `zettel-objet-link` implementation was intentionally not changed
in v0.4.11. Investigation showed that it repeatedly walks about 8,616 zets,
reparses a large manifest, and uses a broad Windows change watcher to protect
identity and race safety. Removing those checks or trusting filename-equals-ID
would regress Letter 140. The accepted v0.4.12 decision instead requires
generation-bound zet/manifest projections, deterministic `already_present`,
writer-wide index lifecycle integration, distinct content-free reason codes,
and declared cold/warm Windows performance gates. This preserves honest early
truth in v0.4.11 without pretending the open writer's latency is solved.

## Release-candidate correction loop

The first public CI run exposed two tests that still observed the previous
implementation rather than the current contracts. The quarantine test watched
`os.walk` even though Doctor now uses the bounded `os.scandir` traversal, and
the MCP test still expected the historical revision-plan status. Both tests
were updated to assert the new behavior without weakening the underlying
security or privacy checks.

That review also found stale current guidance in the revision-plan guide,
revision-writer guide, capability matrix, and installed AI operator contract.
They still told operators to hand a green revision plan to
`zet-revision-write --dry-run`. All current guidance was corrected before
release: validation hashes are review evidence only, successful validation
remains `approval_fixed_closed`, and v0.4.11 exposes no actionable writer
handoff. Historical release notes remain unchanged as historical evidence.
These documentation corrections change no client data and open no writer.
