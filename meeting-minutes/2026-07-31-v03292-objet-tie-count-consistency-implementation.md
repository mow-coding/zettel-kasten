# v0.3.292 objet tie-count consistency implementation record

- Date: 2026-07-31
- Branch: `codex/v0.3.292-objet-tie-count-consistency`
- Starting point: `9ef9ce7a`
- Status: local stacked implementation and verification in progress; public
  predecessor rebase and release evidence remain pending

## User intent and accepted scope

The accepted Letter 105 follow-up requires overview and catalog objet tie
counts to include canonical structured edge targets without turning those
frontmatter-only surfaces into body search.

This release is deliberately narrow:

- one private tie-summary collector and focused regressions;
- documentation for the two different count scopes;
- version, changelog, upgrade, decision, release-note, and deterministic
  packaged-resource plumbing; and
- no command, MCP tool, writer, migration, index rebuild, provider call,
  archive mutation, or beta-archive operation.

The service implementation must not broaden `collect_referenced_objets()`,
because that collector also feeds block-header output, source-map preservation
decisions, and cleanup safety counts.

## Starting evidence and stacked predecessor boundary

The worktree began clean at `9ef9ce7a` on the requested v0.3.292 branch. That
commit is the local v0.3.291 full-suite checkpoint and the branch is stacked on
the v0.3.291 release candidate, not yet on an independently verified public
v0.3.291 merge.

Accordingly:

- local green checks establish only candidate quality;
- v0.3.292 cannot be called public or release-ready from this stacked state;
- after v0.3.291 is merged and published, this branch must rebase onto its
  exact public merge commit;
- the complete suite and exact clean-wheel lifecycle must run again on that
  final tree; and
- PR, main, tag, GitHub Release, anonymous download, digest, and fresh-install
  evidence remain required before a public-release claim.

Beta semantic confirmation remains a later human real-use validation step.

## Documentation and release-plumbing plan

1. Move only current version, install, checkpoint, and runtime-status pointers
   to v0.3.292 while preserving historical v0.3.291 feature text.
2. Add English changelog and English/Korean upgrade guidance.
3. Add the v0.3.292 source release note and compact decision log.
4. Define `tie_summary.referenced_objets_count` as distinct structured
   frontmatter objet relationships.
5. Preserve `zettel-objet-links.count` as the broader distinct object-ID count
   across valid frontmatter and body.
6. State that catalog remains `body_read: false` and redacted results reveal
   neither counts nor relationship existence.
7. Update capability-document tests and replace the single packaged current
   release note through deterministic resource synchronization.

## Chronological implementation record

1. Confirmed the requested worktree, branch, clean starting state, project
   rules, and the complete v0.3.292 directive.
2. Inspected v0.3.291 version surfaces, current wheel links, release-resource
   mapping, capability docs, documentation tests, release notes, decision
   records, and implementation minutes.
3. Bumped package metadata, both import-visible version files, and current
   `VERSIONING.md` pointers to 0.3.292.
4. Updated only current baseline, wheel, checkpoint, install-guide, capability,
   and runtime-entrypoint surfaces. Historical v0.3.291 behavior and release
   records remain intact.
5. Added the changelog, bilingual upgrade guidance, source release note,
   decision log, and this chronological record.
6. Updated catalog, objet-link, and capability docs to separate structured
   frontmatter tie counts from broader valid-frontmatter-plus-body link counts.
7. The user corrected the coordination record after two Codex Desktop
   `Task encountered a system error` interruptions. WOM is explicitly a
   safer-AI and defensive system. The interruptions came from an automated
   false-positive on a delegated security-regression prompt, not a judgment
   that the project or user was malicious. The mitigation is to keep detailed
   defensive checks in the root task, give subagents only bounded ordinary
   implementation, documentation, test, or review work, continue the release
   task, and not retry the flagged prompt. This record does not expose private
   paths or infer hidden backend identity.
8. Reserved the final verification record below for actual command results;
   planned checks are not reported as completed evidence.
9. An independent read-only review found one P2 before release: malformed
   object-shaped direct edge targets were excluded from the new count but
   could still be echoed by the existing overview/catalog edge preview. The
   implementation now replaces partial, suffixed, URL/path-contained,
   uppercase-prefix, and non-string direct targets with the existing fixed
   `<redacted-reference>` placeholder. The regression serializes the actual
   first-read and catalog results, proves the rejected values are absent,
   preserves valid object IDs, zettel targets, and ordinary safe labels, and
   keeps catalog body reads disabled. The focused eight-test rerun, Python
   compilation, and scoped diff check passed after this correction.

## Later release-train boundary

This v0.3.292 batch does not absorb later accepted work.

- Preserve the accepted Letter 105 v0.3.293-v0.3.299 reservation as separate
  release batches.
- Plan v0.3.300 for tracked-public privacy checker and sanitation work.
- Plan v0.3.301 for AI development provenance.
- The current Codex metadata exposed requested label `gpt-5.6-sol` with
  reasoning effort `ultra` only as client request metadata. It is not served
  model or hidden-backend attestation.
- The Claude audit recorded explicit client fallback labels, but likewise
  provided no hidden-backend attestation.

Those facts belong to later provenance design and honest evidence wording.
They are not public feature claims for v0.3.292, and none of the
v0.3.293-v0.3.301 future batches is implemented here.

## Verification evidence

Completed for this documentation and release-plumbing batch:

- `python -m py_compile wom-kit/tests/test_capability_matrix_docs.py`: passed.
- Capability documentation contracts: 147 tests passed.
- Package resource contracts with this worktree's `wom-kit/src` explicitly on
  `PYTHONPATH`: 7 tests passed.
- Deterministic package-resource synchronization and check: 103 files for
  v0.3.292; the packaged current release-note set contains only
  `v0.3.292.md`.
- Release-readiness unit contracts: 5 tests passed.
- Release-readiness child checks: public links, Korean product language,
  public privacy, and runtime Skill all passed.
- `git diff --check`: passed.
- New release, decision, and implementation records contain no trailing
  whitespace.
- Current install surfaces contain no v0.3.291 wheel URL.

The first documentation run had two exact-phrase assertion failures because
the release note used an equivalent line-wrapped form. The public contract
anchors and whitespace-normalized test were corrected; the complete 147-test
rerun passed.

The first package-resource resolver run imported an unrelated editable
checkout through the machine Python environment. Re-running with the
documented source-checkout boundary, this worktree's `wom-kit/src` on
`PYTHONPATH`, made all seven tests pass without a code change.

The first readiness invocation saw the deleted packaged v0.3.291 note through
the unstaged Git index and tried to open its now-absent path. For the
non-mutating pre-stage check, the exact historical source note was
temporarily materialized at that old packaged path; all four hygiene checks
and all five readiness tests then passed. The temporary file was removed, and
the deterministic final resource check again proved that only v0.3.292 is
packaged.

After the implementation, P2 correction, resource-note rename, and this
ignored-but-required minutes file were staged as one candidate index, the
release supervisor reran the actual gate. Public links, Korean product
language, public privacy, and runtime Skill all passed, and the resource
mirror again reported 103 synchronized files for v0.3.292. The four focused
tie-summary tests passed from the supervisor process; the implementation
agent's expanded focused selection passed eight tests after the
case-insensitive malformed-marker correction. Capability documentation passed
147 tests and package-resource contracts passed seven tests on the corrected
tree. `git diff --cached --check` passed. A staged-addition scan found zero
exact local usernames, Windows user-home paths, Unix user-home paths, or
credential-bearing URLs, and the ordinarily excluded implementation minutes
also passed the privacy checker's own text rules when checked directly.

The complete source suite, final-predecessor rebase, clean wheel, remote CI,
tag, release, anonymous download, digest, fresh install, and beta semantic
validation remain outside this local stacked documentation checkpoint.
