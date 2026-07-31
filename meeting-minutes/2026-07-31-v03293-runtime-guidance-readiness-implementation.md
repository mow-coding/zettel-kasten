# v0.3.293 Runtime Guidance Readiness Implementation

Date: 2026-07-31

## User Intent

Continue the accumulated beta-feedback release train carefully rather than
claiming that archive guidance is effective merely because files exist. The
release must improve the AI entry route, preserve human approval, and keep
truth boundaries explicit.

## Authority And Scope

The implementation followed Letter 105, the v0.3.293 implementation
directive, and the Letter 105 release-train decision record. This batch is
limited to runtime-guidance readiness and complete operator-feedback routing.
Later v0.3.294-v0.3.299 items remain separate batches.

## Implementation

- Added `wom_kit.runtime_guidance` and the explicit
  `runtime-guidance-readiness` CLI command.
- Bound the explicit invocation to
  `archive runtime-guidance-readiness <archive-root> --host codex --scope repo
  --repo-root <repo-root> --format json`.
- Added real, read-only Codex repository checks for managed runtime Skill
  status and bounded `AGENTS.md` routing anchors.
- Added distinct absent, incomplete, unreadable, unsafe, and unsupported
  diagnostics without echoing paths or source bodies.
- Kept ordinary `runtime-context` and `ai-start-here` at `not_checked` with
  an exact opt-in command and `host_guidance_consumption: not_proven`.
- Advanced action routing to v0.7 and embedded the five-stage
  operator-feedback sequence with a required human gate.
- The sequence names `operator-feedback-plan`, `operator-feedback-ledger`,
  required human review, `operator-feedback-record --dry-run`, and
  `operator-feedback-record --approve --reviewed-by <human-actor>`.
- Any needed Skill change is returned only as
  `runtime-skill-install --dry-run`; no automatic install or `AGENTS.md`
  rewrite is authorized.
- Extended Markdown guidance and the public documentation set.
- Changed no archive content, existing `AGENTS.md`, provider, external
  service, tag, release, or beta archive.

## Verification Record

The new focused runtime-guidance test module contains coverage for a current
Skill plus complete routing, distinct absence diagnostics, unreadable and
unsupported fail-closed behavior, required CLI selectors, no implicit host
inspection, and exact feedback sequencing. Initial focused execution passed
6 tests.

Verified local evidence:

- focused runtime-guidance: 6 passed;
- selected runtime-context, ai-start-here, and feedback CLI regression: 3
  passed;
- capability-document suite: 148 passed;
- packaged resources, runtime Skill lifecycle, and runtime guidance: 36
  passed with 1 environment-permission skip;
- all 27 test modules other than the 3.8 MB `test_cli.py` module completed;
  their initially reported public-hygiene errors were caused by the expected
  staged deletion/addition transition from packaged v0.3.292 to v0.3.293, and
  the four affected modules were rerun after staging and passed as part of a
  200-test verification;
- release readiness passed public links, Korean product language, public
  privacy, and runtime Skill package checks; and
- the clean wheel check passed v0.3.293 with 103/103 resources, 119 wheel
  files, runtime Skill lifecycle, onboarding, strict Doctor, and wheel SHA-256
  `086209755421b971ae4352f30d908cbb9e26fa61ac18347afdf3dcdce01e3d84`.

The complete discovery suite was attempted twice. It exceeded first the
2-minute limit and then the 10-minute limit without returning a terminal
result. No test failure was observed from those timed-out runs, but they are
not counted as a completed full-suite pass. Exact public-predecessor CI/full
verification therefore remains required. A green local subset or clean wheel
is engineering evidence only.

## Independent Review P1 Corrections

The first local commit was independently reviewed before any push or release.
Two P1 issues were found and fixed in one follow-up batch.

1. A hand-edited ownership manifest could place arbitrary text in
   `package_version`. The runtime Skill status projection copied that string
   into `installed_version`, and readiness copied the nested projection. The
   parser now uses the shared exact stable-version policy, invalid values
   become `null`, the state becomes `managed_invalid`, and both JSON and text
   explicitly report `invalid_or_untrusted` without echoing the source value.
2. An existing directory without `archive.yml` passed the directory check and
   later raised while reading `archive_id`. Archive validation now happens
   before host inspection and returns a structured `invalid_archive` blocked
   result. CLI dispatch normalizes expected local inspection failures to the
   same content-free result family.

Regression coverage uses path-like, traversal-like, partial, prerelease, and
sensitive-like version canaries, preserves normal `0.3.293`, checks JSON and
text non-echo, verifies exit 1 for the invalid archive, asserts no traceback or
absolute path, and compares complete test trees before/after to prove no write.

Follow-up verification passed 32 focused runtime-guidance/Skill lifecycle
tests with 1 environment-permission skip, three existing exact-version
redaction tests, 187 resource/document/readiness/Skill tests with the same
single skip, and all four release-readiness checks. The post-correction clean
wheel contains 120 files, verifies 103/103 packaged resources and 333,089
resource bytes, passes runtime Skill lifecycle, onboarding, and strict Doctor,
and has SHA-256
`9fe60140054a5035eb111fc4b11a9b4b81b9b509c2cbdbe8db5657fc1c2226f1`.
This supersedes the pre-review candidate wheel for any later local comparison;
it is still not public-artifact evidence.

## Re-review Archive Identity Correction

A second independent check found that malformed `archive.yml` YAML still
escaped the initial correction. PyYAML's parser exception was not part of the
expected local error boundary, and the content-free blocked-result builder
retried the same identity read. This could emit a traceback containing the
absolute archive path. The same check also found that an empty or
whitespace-only string `archive_id` passed the earlier type-only validation and
entered host inspection.

The correction now:

- treats PyYAML parser failures, Unicode decoding failures, expected local
  read errors, and path-resolution failures as invalid archive identity
  evidence;
- validates that the string identity contains at least one non-whitespace
  character while preserving a normal non-empty identity;
- uses the same safe error boundary during the blocked-result identity retry;
- returns only the static `invalid_archive` blocked result with exit 1; and
- stops before host target resolution, runtime Skill inspection, or
  `AGENTS.md` inspection.

Regression cases cover missing, null, list, empty, whitespace-only, malformed
YAML, invalid UTF-8, and simulated permission-denied identity input. Each case
separately captures stdout and stderr, parses stdout as valid JSON, requires
empty stderr, rejects traceback/parser/decoder/path/body/error canaries,
asserts all three host-inspection functions were never called, and compares
the complete repository tree digest before and after to prove zero writes.

The focused runtime-guidance module passed all 10 tests. The combined
runtime-guidance, Runtime Skill lifecycle, packaged resource, and release
readiness selection passed 50 tests with one Windows symlink-privilege skip.
The standalone package-resource check confirmed all 103 v0.3.293 resources
were synchronized, and the release-readiness gate passed public links, Korean
product language, public privacy, and Runtime Skill package checks.

## Release Boundary

v0.3.292 is currently a local candidate lineage, not a proven public
predecessor for this branch. Before v0.3.293 is release-ready, rebase onto the
exact public v0.3.292 predecessor and rerun the full suite plus clean-wheel and
public-artifact verification. No push, PR, tag, GitHub Release, anonymous
download, or beta validation is performed in this batch.

## Exact Public Predecessor Rebase And Final P1 Batch

The preceding release boundary above is historical and is now superseded.
v0.3.292 became publicly complete with exact tag CI, one GitHub Release wheel,
GitHub digest, and matching anonymous redownload. This branch was cleanly
rebased onto exact public merge:

```text
4130c9ef4c68ce1445446f0964d5edc89745b0d9
```

Only the three v0.3.293 commits replayed. Their rebased commits were:

```text
496ede66b92778d5aee5c22786a93fea3c707c42
6259f380e1bd70839a6fbac4761cd81cadc2ba91
1f7712bc7bfb69a9249c0c1418643239cb2f99cf
```

The independent exact-candidate review then required three further P1
corrections:

1. `archive_id` is exposed only when `safe_projection_scalar(raw) == raw`.
   Unsafe, path-like, secret-like, overlong, or normalization-changing
   identity is returned as content-free `archive_identity_unshareable`.
   Archive configuration is read once; Skill and AGENTS inspection do not
   run. The blocked-result constructor is now pure and performs no retry I/O.
2. New archive templates carry one exact v0.3.293 AGENTS routing block. The
   detector normalizes CRLF to LF only, requires one ordered sentinel pair and
   exact inclusive content, and rejects negated, historical, quoted, fenced,
   missing, duplicated, reordered, truncated, or edited variants. Existing
   archive AGENTS files are never migrated or rewritten.
3. Stable manifest versions now use ASCII digits, `re.ASCII`, exact
   `v?MAJOR.MINOR.PATCH`, and
   `MAX_STABLE_VERSION_LABEL_LENGTH = 64` before normalization. Unicode-digit
   and oversized values become `managed_invalid`, expose no raw value, and
   retain `installed_version_status: invalid_or_untrusted`.

The result now exposes a truthful read matrix:

```text
archive_configuration_read
agents_body_read
credential_or_secret_store_read
```

It separately records identity/body/secret-value exposure. The ambiguous
`secrets_read: false` field was removed. A CLI fallback whose exact read stage
is unknown reports `observation_status: conservative_after_failure` and
conservatively marks both file-read observations true without retrying either
file.

Current post-rebase focused evidence:

- runtime-guidance final P1 module: `17 passed`, `42 subtests passed`;
- Runtime Skill install/lifecycle: `27 passed`, `1 skipped`, `15 subtests
  passed`;
- runtime guidance + package resources + v0.3.293 documentation contract:
  `25 passed`, `159 subtests passed`;
- package resource synchronization: `103 files for v0.3.293`.

These are focused results, not a completed full-suite or public release claim.
The exact final diff still requires broader regression, readiness, clean-wheel,
fresh-install, independent review, PR/main/tag CI, and public artifact gates.

## Final P1 Batch Provenance Boundary

```text
task_role: implementation
product_or_app: Codex Desktop execution context
exact_backend_model: not_exposed
ui_model_label: not_observed
model_transition_or_fallback: not_exposed
input_commit: 1f7712bc7bfb69a9249c0c1418643239cb2f99cf
exact_public_predecessor: 4130c9ef4c68ce1445446f0964d5edc89745b0d9
human_final_authority: user
```

No model identity is inferred from the app, branch, task name, or confidence.

## Exact-Diff Review Correction: Active Unit And Read Observation

The final independent exact-diff review found two additional truthfulness
gaps before commit:

1. the old canonical block had no internal machine-readable statement that
   distinguished an active contract from the same bytes pasted under
   `Do NOT follow` or `Historical only` prose; and
2. a nonexistent archive root was reported as though `archive.yml` had been
   read even though root validation stopped before that read attempt.

The canonical sentinel unit now contains a fixed current-authority sentence.
Removing or editing that sentence into a negation or historical label makes
the unit non-current. Quoted, fenced, duplicated, reordered, truncated, and
otherwise edited units remain non-current. Prose outside the sentinels is not
treated as an NLP override of an exact active unit; an example or historical
copy must be quoted, fenced, or byte-distinct. This makes the automated
contract explicit without claiming general natural-language interpretation.

Archive-root validation and archive-configuration reading are now separate
stages. A nonexistent root reports
`archive_configuration_read: false`; an existing root whose `archive.yml` is
missing, malformed, unreadable, or invalid reports the attempted read as
`true`. Both cases remain fixed, content-free blockers and perform no Skill or
AGENTS inspection.

The two long-running suite shards that had begun before this correction were
terminated and their partial output was discarded as non-evidence. All
affected and full gates must restart from the corrected final tree.

## Final Exact-Diff Review, Full Verification, And Role Provenance

The corrected code, tests, public docs, packaged resources, and scratch-ignore
rule were committed as:

```text
implementation_output_commit:
805c039ce25033c441807fc168d6699b0e7eb34d

implementation_output_tree:
82fddbd11981d5cb230b937aad6bdd75ebbb337c

implementation_input_commit:
1f7712bc7bfb69a9249c0c1418643239cb2f99cf
```

The complete post-correction evidence on that implementation tree was:

- exact source import:
  `wom-kit/src/wom_kit/runtime_guidance.py` and
  `wom-kit/src/wom_kit/archive_cli.py` from the dedicated v0.3.293 worktree;
- runtime-guidance plus capability/document contract:
  `166 passed`, `3975 subtests passed`;
- Runtime Skill plus release-readiness tests:
  `28 passed`, `1 skipped`, `23 subtests passed`;
- non-CLI complete source suite:
  `530 passed`, `14 skipped`, `4498 subtests passed`;
- complete CLI module:
  `1341 passed`, `8 skipped`, `1023 subtests passed`;
- stderr for both complete-suite shards: zero bytes;
- package resources: `103/103` synchronized for v0.3.293;
- release readiness: public links, Korean product language, public privacy,
  and Runtime Skill package all passed; and
- independent exact-diff re-review: `P0 0`, `P1 0`.

The earlier partial long-running shards remain non-evidence. Only the two
completed final-tree shards above count as the full local source-suite result.

### Role 1: implementation

```text
task_role: implementation
product_or_app_observed: Codex Desktop execution context
exact_backend_model: not_exposed
ui_model_label: not_observed
session_self_report_used_as_identity_evidence: false
client_or_session_model_telemetry: not_exposed
served_model_attestation: not_exposed
model_transition_or_fallback: not_exposed
input_commit: 1f7712bc7bfb69a9249c0c1418643239cb2f99cf
output_commit: 805c039ce25033c441807fc168d6699b0e7eb34d
human_final_authority: user
```

### Role 2: first independent audit

The first audit reviewed the original feature commit and found the unsafe
manifest-version projection and invalid-archive exception boundary.

```text
task_role: read_only_audit
product_or_app_observed: Codex Desktop agent execution context
exact_backend_model: not_exposed
ui_model_label: not_observed
session_self_report_used_as_identity_evidence: false
client_or_session_model_telemetry: not_exposed
served_model_attestation: not_exposed
model_transition_or_fallback: not_exposed
input_commit_before_rebase: b675951d71d62cffa34e8856c77893f48e3a0c8a
equivalent_input_commit_after_rebase: 496ede66b92778d5aee5c22786a93fea3c707c42
correction_commit_before_rebase: 46e6f3721e9da85c034d39bafa7a8e75c780119a
equivalent_correction_commit_after_rebase: 6259f380e1bd70839a6fbac4761cd81cadc2ba91
human_final_authority: user
```

### Role 3: archive-identity independent re-review

The next independent check found malformed-YAML error coverage, retry I/O,
and empty-identity gaps.

```text
task_role: read_only_audit
product_or_app_observed: Codex Desktop agent execution context
exact_backend_model: not_exposed
ui_model_label: not_observed
session_self_report_used_as_identity_evidence: false
client_or_session_model_telemetry: not_exposed
served_model_attestation: not_exposed
model_transition_or_fallback: not_exposed
input_commit_before_rebase: 46e6f3721e9da85c034d39bafa7a8e75c780119a
equivalent_input_commit_after_rebase: 6259f380e1bd70839a6fbac4761cd81cadc2ba91
correction_commit_before_rebase: f8e209f21179a769bde3abf0526473b2ea5d41fd
equivalent_correction_commit_after_rebase: 1f7712bc7bfb69a9249c0c1418643239cb2f99cf
human_final_authority: user
```

### Role 4: exact-candidate audit and final exact-diff re-review

The exact-candidate audit at `f8e209f2` found the unsafe archive-identity
projection, generic AGENTS phrase acceptance, and Unicode/oversized manifest
version gaps. After the public-predecessor rebase and corrections, the final
exact-diff re-review independently reproduced the prior blockers as closed,
found no P0/P1, and required only this provenance/evidence record completion.

```text
task_role: read_only_audit
product_or_app_observed: Codex Desktop agent execution context
exact_backend_model: not_exposed
ui_model_label: not_observed
session_self_report_used_as_identity_evidence: false
client_or_session_model_telemetry: not_exposed
served_model_attestation: not_exposed
model_transition_or_fallback: not_exposed
exact_candidate_input_before_rebase: f8e209f21179a769bde3abf0526473b2ea5d41fd
equivalent_post_rebase_input: 1f7712bc7bfb69a9249c0c1418643239cb2f99cf
reviewed_implementation_output: 805c039ce25033c441807fc168d6699b0e7eb34d
verdict: P0 0; P1 0
human_final_authority: user
```

No audit is attributed to a backend model ID, UI model label, model
transition, or fallback that the execution environment did not expose. The
application name and task-role names are not used as model identity evidence.

This closes local implementation and source-suite review. It is not yet a
public-release claim: clean-wheel/fresh-install evidence, PR/main/tag CI,
annotated tag, one-asset GitHub Release, and matching anonymous download are
still required.
