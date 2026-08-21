# Letter 140 v0.4.0 Rescue Start

Date: 2026-08-21
Status: v0.4.1 implementation and integration in progress; no commit, push, PR, tag, or release yet

## User intent

The user asked for the GitHub repository to be restored to public visibility and then directed the team to begin resolving the accumulated beta-client letters immediately, completely, and efficiently. The temporary private state was motivated by embarrassment and concern that sensitive information might have entered WOM development history, not by a settled private-distribution strategy.

The work must protect the read-only Basoon archive, avoid disturbing unfinished Letter 138 work, and use separate worktrees plus explicit verification gates.

## Public visibility evidence

- Repository: `mow-coding/zettel-kasten`
- Remote `main`: `f24bfd262651f808e3c7dade5c476aea6f66d4ed`
- Authenticated repository metadata: public
- GitHub REST visibility: public / `private=false`
- Anonymous repository request: HTTP 200
- Anonymous exact v0.4.0 wheel request: HTTP 200
- No commit, tag, or release was pushed during the temporary private interval.

The existing current-tree public-privacy checker passed against the Letter 138 candidate tree, which contains at least the current public tree plus candidate changes. This was a useful initial gate but not a complete-history secret-scan proof. `gitleaks` was not already installed at that checkpoint; the later official-tool scan and independent classification below closed the pending gate.

## Sensitive-information audit in progress

GitHub reports repository secret scanning enabled with zero open alerts. An official Gitleaks v8.30.1 Windows x64 archive was then downloaded to a unique temporary directory. Its SHA-256, `d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e`, matched the checksum published with the same official release.

A redacted `git --all` scan and current-directory scan both reported 41 findings representing 14 unique candidate values across three rules. No candidate value was printed. All findings are confined to tests, templates, examples, release documentation, and the changelog. Initial value-safe classification found environment-variable names, prose, explicitly fake/test sentinels, a known synthetic sequential AWS identifier, credential-shape rejection fixtures, and deterministic signing test vectors. The random-looking R2-shaped fixture is paired with an explicitly fake access identifier and was introduced by a commit whose summary says `no live network`.

The Letter 138 candidate directory produced the same 41 findings with only a line-number shift in the changelog, so it introduced no additional finding.

Independent review reproduced the clean `f24bfd2` scan and classified all 14 candidates without printing values. It found zero provider live-mode prefixes, zero repository evidence of an issued credential, zero evidence requiring immediate rotation, and zero history-only finding that a rewrite would remediate. The high-entropy candidates are confined to named signing, credential-detection, non-echo, quarantine, invalid-input, redaction, or hostile-metadata tests. The only candidate also present in product code is a protocol reason-code identifier, not a credential. Privacy gate verdict: passed, with the honest limitation that no credential provider was contacted to test external validity. If a human later states that a fixture was copied from a real credential, that specific credential must be rotated.

Broad test-directory allowlisting is not permitted because it could hide a later real leak. Any future false-positive suppression must bind a narrow file and rule or exact safe fingerprint. Two attempts to remove the unique temporary scan directory were rejected by the execution policy, including one path-validated recursive removal and one explicit non-recursive file list. No shell-switch or policy bypass was attempted. The directory contains only the official release archive/checksum/binary and redacted reports; no unredacted report was written. Cleanup remains pending outside this restricted deletion boundary.

## Isolation and starting point

- Worktree: dedicated Letter 140 rescue worktree from current `origin/main`
- Branch: `codex/letter140-v040-rescue`
- Base: `origin/main` at `f24bfd262651f808e3c7dade5c476aea6f66d4ed`
- Letter 138 candidate worktree remains separate and unreleased with its existing independent-review P1 unresolved.
- The Basoon letter files remain immutable evidence and are not test fixtures.

## Execution plan and feedback loop

1. Trace three independent Letter 140 surfaces in parallel: the version-update escape, the single-target zettel-to-objet attachment path, and JSON/exit-code plus command-status behavior.
2. Reproduce only with synthetic or repository fixtures; never run mutating commands against Basoon.
3. Convert trace results into the smallest safe P0 release slice. Reopening a command is permitted only when its effects are exact, inspectable, narrowly approved, and testable.
4. Add focused regression tests first or alongside each code change, then run the relevant suites and the repository release-readiness gates.
5. Request independent review and resolve every P0/P1 before release.
6. Only after validation: commit, PR/merge, tag/release, anonymous fresh-install verification, and post-release command checks.
7. Run Letter 139 in parallel only as a read-only planner/schema threat-model track. Its commit/push writer remains out of scope until a deterministic plan, lock, exact human approval, revalidation, and provider-confirmed receipt contract exist.

At each gate, update this record with what is confirmed, inferred, still unconfirmed, and whether the plan must change.

## First confirmed implementation slice

Synthetic reproduction confirmed the Letter 140 structured-output defect:

- `facet-vocabulary <missing-root> --format json` returned exit 1 with empty stdout and plain stderr;
- `index <missing-root> --format json` returned exit 1 with empty stdout and plain stderr;
- argparse usage errors already returned exit 2 with JSON, while fixed-closed approval returned exit 1 with JSON.

A reusable recognized-command error envelope was added for the two confirmed invalid-root paths. JSON mode now emits exactly one `wom-kit/cli-error/v0.1` document on stdout, keeps stderr empty, records `exit_code: 1`, `effects_state: none`, and does not echo the supplied path. Text mode retains its fixed path-free stderr guidance.

The first test invocation accidentally imported the already installed v0.4.0 package instead of the worktree source and therefore reproduced the old behavior. No repository state changed. After setting `PYTHONPATH` to this worktree's `wom-kit/src`, the three new tests passed. The focused new, Letter 136 facet, Letter 137 fixed-help, and alias-boundary selection then passed 13/13 tests.

This slice intentionally does not claim that every runtime exception has a unified envelope. Index failures after indexing has started require truthful `effects_state` and result-capture handling, and the complete command-status registry remains a separate bounded implementation.

The common error contract was then extended to argparse usage failures (`exit_code: 2`, `error_class: usage`) and fixed exact-human policy blocks (`exit_code: 1`, `error_class: policy`). The fixed-closed zettel-object link projection now carries the same schema without echoing its supplied root, zettel, object, label, or reviewer values. The focused selection passed 15/15 tests after this extension.

A public `wom-kit/cli-error/v0.1` JSON Schema was added for the common content-free fields. It requires the command/lifecycle/error class, at least one fixed reason code, explicit exit code and effect state, an empty written-file list, and `private_values_echoed: false`; command-specific safe extensions remain permitted. It has not yet been copied into packaged resources or included in a built wheel because resource sync is intentionally deferred until the release version and complete public-resource set are stable.

## Confirmed urgent attachment boundary

Read-only tracing confirmed that only `zettel-objet-link --approve` is a suitable attachment rescue in this urgent release. Its human-facing effect is one manifested object added to one zettel's `frontmatter.assets`. `objet-capture`, `objet-capture-selection`, capture batches, and link revert remain fixed closed because their unstable or multi-item effect sets do not yet fit one exact-human binding.

The dormant link writer cannot be exposed by deleting its gate. Its current plan omits the snapshot from the advertised support-effect set, accepts an existing snapshot without proving regular-file identity and exact bytes, uses first-record-wins manifest lookup, lacks canonical readback verification, and can retry its inherited Windows lock indefinitely on permanent errors. The implementation is therefore split into three parallel bounded parts: exact-human operation/binding, hardened service and v0.2 receipt with v0.1 read compatibility, and CLI orchestration. Reopening is allowed only after all three parts and their drift/failure tests agree.

The release recommendation is now v0.4.1 for this operational rescue. The unreleased Letter 138 candidate must move to a later version rather than competing for the same tag. No Letter 138 code or record has been rewritten as part of this decision.

The complete command-status request is being implemented as a parser-derived, read-only inventory rather than a hand-maintained second list. The intended classifications are deliberately narrow: `approval_available`, `approval_fixed_closed`, or `approval_not_exposed`, plus whether `--dry-run` is exposed. They describe the installed CLI surface only and do not claim that archive-specific prerequisites have passed or that commands without `--approve` are necessarily read-only.

## Initial non-actions at the investigation checkpoint

- No protected archive data was read by a mutating path or changed.
- No Letter 139 commit, push, merge, rebase, reset, pull, or deletion was attempted.
- No Letter 140 behavior had yet been represented as fixed at that checkpoint.
- No version number had yet been assigned at that checkpoint.

## Confirmed v0.4.1 implementation gate

The rescue release is now assigned to v0.4.1. Letter 138 remains isolated for a later version because its separate wrapper-metadata audit-completeness P1 is unresolved.

The current implementation reopens only `zettel-objet-link --approve`. It now requires a fresh service plan digest, reviewer identity, native exact-human approval, and a one-use authenticated claim before the writer can mutate an archive. The operation binding covers the exact zettel and current digest, one unique manifested object record, role, label digest including the no-label sentinel, receipt generation and path, snapshot path/state/digest, the full support-effect set, and a persistent per-zettel control lock path/state/digest.

The service now:

- rejects missing exact-human inputs before any archive read;
- reads the complete object manifest as a bounded stable regular file and rejects malformed rows, duplicate JSON members, missing matches, and duplicate matches;
- accepts only an absent snapshot or an existing exact regular-file snapshot;
- uses the plan-bound persistent lock `receipts/objects/zettel-links/.locks/<sha256(zettel-id)>.lock` with fixed bytes and a two-second bounded acquisition;
- recomputes the full plan and approval binding while holding that lock;
- verifies canonical, manifest, snapshot, receipt, and control-artifact state immediately before mutation;
- publishes the receipt create-only and verifies canonical and receipt bytes after writing;
- writes v0.2 exact-human receipts while retaining strict v0.1 read and revert-plan compatibility;
- preserves snapshot and receipt evidence when rollback cannot independently prove that the canonical zettel returned to its approved before bytes.

The CLI end-to-end synthetic fixture passed the complete sequence `dry-run -> exact plan digest -> approved writer -> v0.2 receipt -> receipt lookup`. The private label was stored only in the target zettel and did not appear in stdout or stderr. No Basoon path was used.

Current focused verification evidence:

- approval binding, command inventory, and common CLI error contract: 24 tests passed;
- hardened link service and CLI end-to-end path: 10 tests passed after adding the uncertain-rollback evidence-preservation case;
- the first selected legacy regression run completed 117 tests with only six expected historical-assumption conflicts: three current-count assertions still expected 79, and three tests still expected link apply to remain unconditionally fixed closed. No unrelated completion-workflow regression failed.

The historical v0.4.0 release note and its 79-command fixed-close fact remain immutable history. Current parser-derived inventory reports 313 canonical executable commands, 259 alias paths, 572 invocation paths, 35 approval-available commands, 78 fixed-closed commands, 200 commands without an exposed approval option, and zero unmatched fixed-close entries. These are installed-parser facts only; they do not evaluate archive prerequisites or imply that commands without `--approve` are read-only.

## Project updater decision

`project-version-update --approve` remains fixed closed in v0.4.1. Its dry-run cannot know the exact target commit and full materialization effects before a Git fetch. The fetch itself can call credential helpers and mutate the object database, refs, and reflogs; approving before it would bind an incomplete target, while approving after it would leave that first mutation unapproved. A safe future design requires a separately approved isolated fetch/import stage, a second exact apply stage, and a project-scoped identity/claim store.

The supported v0.4.1 escape will therefore be the exact public wheel after the release exists. It updates only the isolated global CLI selected by `PATH`; it does not update `.zettel-kasten/source`, project pins or worktrees, archive content, Git refs, or Runtime Agent Skill. A new process must confirm `archive --version`, and project/global mismatch reported by `archive version` is expected until a separately safe project-updater design ships.

## Remaining release gates

1. Finish the historical/current test split and v0.4.1 documentation without editing the v0.4.0 historical contract.
2. Sync packaged schemas and release notes mechanically, then verify byte parity and the resource manifest.
3. Run focused, broader, and full test/build/readiness suites.
4. Request independent code and security review and resolve every P0/P1.
5. Commit, open the PR, wait for CI, merge, tag, publish the GitHub release and wheel, and perform anonymous exact-wheel fresh-install verification from a new isolated process.

## Packaging and full-suite checkpoint

Package resource synchronization now reports 158 current v0.4.1 files and a
clean `--check` result. The release-document tests pass 15/15 and the complete
capability-matrix documentation module passes 152/152. Public link, public
privacy, Korean product-language, and release-readiness gates pass.

The first built-wheel smoke run correctly found that its legacy fixed-close
assertion still expected the pre-v0.4.1 JSON shape. The installed commands were
returning the new common content-free error envelope with no effects; the
checker itself was stale. After updating all three installed fixed-close
assertions, the isolated wheel check passed with package version 0.4.1, all 158
resources verified, all four entry points working, identical 130-tool MCP
inventories, fixed-closed runtime-skill/onboarding writes, strict doctor, and
temporary environment cleanup.

An initial parallel full-suite launch used the nested `wom-kit` directory as
its process root. On this machine that resolved `wom_kit` through an older
installed checkout, so the resulting failures did not test this branch. Those
processes were stopped and their results explicitly discarded. The suite was
restarted from the repository root with `wom-kit/tests` as the exact test
directory, matching CI and the root source-checkout shim.

The compact public decision record is
`wom-kit/docs/archive-infra-decision-log-2026-08-21-v041-letter140-exact-link-recovery.md`.

## Letter 139 read-only planning result

The Letter 139 source SHA-256 matched before and after inspection:
`9a8b10a13bcd62dc6c4aec2a5763434e102203d6db7cfe11767b04218c02ccc9`.
No Basoon, repository, Git, provider, or network mutation was performed by that
planning track.

Letter 139 is not a v0.4.1 addition. Its requested local commit plus remote
backup is a new archive-wide and network-mutating authority layer. Existing
`backup-evidence` does not inspect Git or a provider ref; `github-repo` is a
configuration preview whose approval remains fixed closed; existing handoff
digests do not bind Git HEAD/index/worktree/remote state.

The planned safe sequence is:

1. v0.4.1 completes only the urgent Letter 140 link recovery.
2. v0.4.2 introduces read-only `git-backup-plan` and
   `git-backup-reconcile-plan` inventory/reconciliation surfaces.
3. Only after real mixed-state plans are deterministic and content-free does a
   later release consider an exact-human-bound commit/push executor.

The future writer must bind repository/provider identity, private visibility,
branch ref, local and remote OIDs, exact hidden effect-set digests, Git trust
configuration, global lock, and reviewer pause confirmation. It must revalidate
before commit and push, never pull/rebase/reset/force-push automatically, and
confirm the exact provider ref before publishing a completion receipt. Unknown
or overlapping historical changes remain human-review blockers rather than
being swept into `git add -A`.

## Independent-review P1 correction loop

The first v0.4.1 implementation was not released when focused independent
review found real release blockers. The release plan moved back from packaging
to implementation instead of treating the earlier focused passes as final
evidence.

Confirmed P1 findings and current corrections are:

- Every object-manifest row is now schema-validated and must bind
  `object_id == sha256:<sha256>` with complete logical-key, location, and
  provenance structure. Non-finite JSON numbers, duplicate members, excessive
  depth, excessive nodes, excessive records, and recursion failure all become
  fixed content-free manifest errors. The new focused manifest tests pass.
- The canonical zettel writer now uses an exact-byte compare-and-swap adapted
  from the mature activity-group primitive for both forward publication and
  rollback. The transaction digest and both deterministic swap residue paths
  are bound into the plan, operation target, support-effect set, and v0.2
  receipt.
- The persistent control artifact is reverified before the first mutation and
  at the final boundary. Snapshot and receipt cleanup was removed from failure
  handling because a detached observation followed by pathname deletion could
  delete a same-user replacement. Created evidence remains for explicit
  reconciliation.
- Usage/privacy classification now includes both the canonical
  `zettel-objet-link` command and its alias. A malformed private argument is not
  echoed in JSON or text mode. Failures after the workflow starts now report
  `execution/state_unknown`, `files_written: null`, reconciliation required,
  and automatic retry forbidden instead of falsely claiming no effect.
- Source and packaged v0.2 receipt schemas are byte-identical after resource
  synchronization. The receipt reader now accepts the transaction fields,
  derives and checks both deterministic paths, requires clean final swap state,
  and is covered by write-to-receipt-lookup regression.
- A reproduced race removed the exact object-manifest target immediately after
  the pre-write validation. A second strict full-manifest exact-target check is
  now the operation's final success linearization point. The targeted test
  proves no success is returned, the canonical bytes are restored by CAS, the
  claim remains `started`, and the retained receipt is not selected as active
  history. Read-only v0.2 receipt lookup also revalidates the current exact
  manifest target.
- Parent directory identities for the control artifact, canonical zettel,
  snapshot, and receipt are being held through the mutation and rollback
  window. Windows junction substitution tests and the final independent review
  are still in progress, so this paragraph is progress evidence rather than a
  release claim.

Documentation now names both private compare-and-swap paths and states that an
interrupted or ambiguous operation may retain full private zettel bytes there.
Such residues, snapshots, and receipts are recovery evidence; WOM does not
auto-delete them or treat receipt presence alone as committed success.

## Second independent-review correction loop

The first P1 correction loop was not treated as release completion. Continued
independent review found additional concrete data-preservation and
archive-boundary failures before any commit, push, tag, or release.

- Approval-bound frontmatter parsing inherited a `.lstrip()` body transform.
  A valid body beginning with four spaces could change from a Markdown code
  block into ordinary text. The Letter 140 path now validates the same strict
  frontmatter but preserves the exact UTF-8 suffix after the closing delimiter.
  Four-space, tab, blank-line, and BOM inputs are covered; the Letter 140
  focused suite then passed 39/39.
- The release wheel checker previously verified packaging, entrypoints, MCP,
  runtime-skill boundaries, onboarding fixed-close behavior, and Doctor, but
  did not execute the newly reopened link workflow. Its isolated installed
  wheel smoke now requires a ready plan, `written` apply result, an actual
  changed canonical SHA, exactly one matching object link, exact leading body
  bytes, exact snapshot, schema-valid v0.2 receipt, and successful lookup.
  Checker unit tests pass 39/39; the actual wheel build remains deliberately
  paused until the remaining P1s close.
- Real Win32 reproduction proved that `ReplaceFileW` may overwrite an already
  existing backup pathname. Therefore the earlier existence check plus a
  deterministic `.previous` backup name was a TOCTOU and could delete foreign
  bytes. The replacement design is a two-step same-handle no-replace rename:
  hold and verify the exact canonical handle, rename that identity to
  `.previous` with `FileRenameInfo.ReplaceIfExists = false`, then hold and
  rename the exact swap handle to canonical under the same rule. The unavoidable
  between-step crash state must be explicitly recoverable without overwriting
  any concurrently created canonical entry. Implementation and injected race
  tests are in progress; this remains a release blocker.
- Real Win32 junction substitution also proved that read-only receipt lookup
  could resolve an internal receipt directory, have it replaced by a junction,
  read and parse an outside candidate, and only then reject it. No content was
  echoed, but this crossed the archive read boundary. Receipt scanning,
  candidate reads, snapshot/revert reads, and the equivalent planning
  observations are being converted to held-parent reads. The acceptance test
  requires zero outside read attempts, not merely a blocked result.

Microsoft's current API documentation confirms that `ReplaceFileW` accepts an
optional backup name but gives no no-replace contract for it, while
`SetFileInformationByHandle` supports `FileRenameInfo` and the corresponding
`FILE_RENAME_INFORMATION.ReplaceIfExists = false` contract fails when the
destination already exists. Local Win11 probes additionally confirmed that a
write/delete-denying held source handle blocks an external `os.replace` while
allowing its own handle-bound no-replace rename.

The plan therefore remains at implementation and adversarial review. Earlier
wheel/full-suite evidence predating these changes is historical progress only
and will be regenerated from one stable final tree.

## Third independent-review correction loop

The second correction loop also remained unreleased. Continued Windows data-
integrity probes showed that exact text bytes alone were not enough for a safe
canonical replacement: deleting the old file could silently discard an
alternate data stream, an NTFS extended attribute such as `$LXMOD`, an object
ID, sparse-file data, a security descriptor, or semantic file attributes.

The Windows compare-and-swap now opens and retains the exact old and proposed
single-link non-reparse files, compares supported security descriptors and
semantic attributes, and performs a handle-bound `BackupRead` stream inventory.
Only the unnamed default data stream is admitted. Any EA, alternate stream,
object ID, sparse data, unknown backup stream, metadata mismatch, or incomplete
query fails before the first namespace move. The new canonical file's identity,
bytes, metadata and final names are reverified before the old link is eligible
for cleanup.

The first cleanup correction used immediate POSIX-semantics disposition for the
direct CAS path, but a further P1 review found that an installed-state retry
still called the older ordinary Windows disposition helper. That would have
silently reintroduced delayed deletion on a filesystem that had already shown
the required immediate-unlink operation was unsupported. Both initial commit
and installed-state reconciliation now call the same `FileDispositionInfoEx`
helper with delete, POSIX-semantics, and ignore-readonly flags. CAS cleanup has
no ordinary fallback. Unsupported systems retain canonical-new plus
`.previous`-old and return a fixed reconciliation error on both first attempt
and immediate retry. Supported systems remove the `.previous` name immediately
even while an external access-zero handle retains only the detached old object.

New Windows regressions cover alternate streams, EAs, object IDs, sparse files,
security and attribute mismatch, raced backup/canonical names, process exit at
each namespace checkpoint, unsupported immediate unlink across a retry,
external open handles, and read-only residue. After the final installed-state
correction, the supervisor independently reran the CAS and mature activity-
group safety modules: 54 tests passed with six platform-expected skips.

A separate final security audit then reproduced another P1 before release. ID-
based selection scanned all of `zettels/` and `inbox/`, but a caller-supplied
`--path` could read only that filename and skip duplicate-ID discovery. Two
files could therefore share the same logical Zettel id while also sharing the
control-lock, link-id, and receipt namespace. The correction requires both ID
and path selectors to perform the same bounded handle-bound two-root scan,
prove exactly one matching id, and for a path selector prove that the unique
match retains the initially selected file identity and exact bytes. A direct
canonical filename is not trusted as uniqueness authority. The duplicate and
same-bytes/new-identity regressions are being completed before the tree can be
called stable.

That audit then found two further approval-authority failures. First,
`archive.yml` was read through the generic YAML loader, so a second
`archive_id` key could silently replace the first and mint a plan from an
ambiguous identity document. Both the operation core and live CLI approval
boundary now parse the held bytes with the existing duplicate-key-rejecting
approval loader, bounded acyclic JSON-safe normalization, and exact-human
archive-id validator. Tests cover top-level and nested duplicates, an alias
cycle, non-finite values, custom tags, an invalid id, and all plan/apply/lookup/
revert core surfaces.

Second, a same-ID file injected after the fresh under-lock plan but before final
success could leave a successful receipt with two Zettels sharing one logical
id and control/receipt namespace. The failpoint reproduced that incorrect
success. The writer now reruns the complete two-root handle-bound uniqueness
and selected-identity proof after canonical, receipt, control, and manifest
readback while still inside the rollback exception boundary. Final drift rolls
the canonical file back through CAS, leaves the durable claim started, retains
the snapshot and receipt for reconciliation, and never reports success.

Current release and operator documentation was also corrected to distinguish
the one reopened link apply from still-fixed-closed revert/capture/project-
update paths, and stale resource/version gates were advanced to v0.4.1. A
preliminary installed-wheel smoke succeeded, but its wheel was intentionally
not preserved because the later CAS and selector P1 corrections changed the
tree. The final wheel, its hash, full shards, PR CI, public Release, anonymous
download, and real v0.4.0-to-v0.4.1 upgrade evidence must all be regenerated
after both final audits report no remaining P0/P1.

## Fourth independent-review correction loop: stable namespace snapshot

The final selector review did not stop at a second sequential directory scan.
It reproduced a moving duplicate that existed for the whole lookup but crossed
from `inbox/` into the already-scanned `zettels/` root between the two scans.
The resolver returned success with two valid files sharing one logical Zettel
id. This was classified P1 and blocked packaging again.

Directory timestamps alone were rejected as the fix. Actual Windows probes
showed that a held directory's `FILE_BASIC_INFO` did not reliably change for
every descendant create or in-place rewrite. The implemented Windows boundary
therefore arms `ReadDirectoryChangesW` before scanning: a non-recursive
archive-root name watch protects absent `zettels/` or `inbox/` roots, and a
subtree watch protects each root that exists. Every discovered directory
binding stays open in one `ExitStack`; its exact identity/token and complete
entry inventory are retained, and every Markdown candidate is re-read for
identity, size, and SHA-256.

Review then found that cancelling several watches sequentially would itself
open a final race. The correction performs one full revalidation, arms an
archive-root subtree closing guard, performs the full revalidation again,
cancels the earlier watches while the guard remains active, and cancels the
guard last. Clean cancellation requires `CancelIoEx` followed by terminal
`GetOverlappedResult`; completed, overflowed, unsupported, or ambiguous watch
states fail closed. Exception cleanup also drains the pending asynchronous I/O
before its buffer, `OVERLAPPED`, event, or handle can be released. POSIX keeps
the directory descriptors open and repeats token, inventory, identity, and
digest validation twice.

Focused Windows regressions cover ID and path cross-root moves, in-place file
rewrites, creation of a previously absent inbox, a duplicate inserted after the
root watcher is cancelled, and a duplicate inserted after the zettels watcher
is cancelled. Independent review found no remaining P0/P1 in this resolver and
watcher boundary. The stable-tree evidence at this checkpoint is:

- bound-read and namespace races: 15/15 passed;
- Letter 140 emergency recovery, binding, CLI, and service: 42/42 passed; and
- approval boundary, completion workflow, exact-human workflow, and credential
  registry regression: 180 passed with two platform-expected skips.

These counts are implementation evidence, not release evidence. Documentation,
package resources, full shards, exact wheel, PR CI, tag, public Release,
anonymous download, and the real public v0.4.0-to-v0.4.1 upgrade still must be
regenerated from the final tree.

## Fifth independent-review correction loop: joint final authority

The next final review found that the manifest target and unique-Zettel proofs
were each strict but did not overlap. The writer first proved the manifest,
then opened the final stable two-root resolver. A deterministic interleaving
could keep a duplicate Zettel present during the manifest check, remove the
manifest after that check, and remove the duplicate before the resolver began.
The old code returned success even though there was no point at which both the
approved manifest provenance and unique Zettel authority were valid. This was
confirmed as P1 and stopped the release after the otherwise-green full rerun.

The final resolver now accepts only the fixed manifest object id and approved
record-set digest as data, not a caller-supplied callback. It opens the exact
manifest parent chain and admits one single-link, non-reparse regular manifest
file. The observation binds the parent stability token plus file identity,
mode, link count, size, timestamps, Windows attributes, and exact bytes. The
approved manifest record set is validated from those already-bound bytes.

That manifest observation now brackets one complete revalidation of every
held Zettel directory inventory and Markdown identity/digest. Windows keeps
the archive-root subtree closing watcher armed across this interval and
cancels it last. POSIX compares the same held manifest parent and file state
before and after the Zettel revalidation. A successful return therefore has a
real joint authority point; missing, replaced, in-place-mutated, or restored
manifest state and any Zettel namespace drift fail inside the existing CAS
rollback and retained-evidence boundary.

The deterministic regression reproduces the former alternating manifest/
duplicate success and now requires the manifest-drift error, original Zettel
bytes restored, receipt evidence retained, and the durable exact-human claim
left `started` for reconciliation. Evidence immediately after this correction:

- the new interleaving regression: 1/1 passed;
- Letter 140 approval/privacy, bound reads, recovery, binding, CLI, service,
  and Windows CAS: 88 passed, one platform-expected skip, plus 106 subtests;
- completion workflows, exact-human approval, credential registry, and
  operation binding: 185 passed, two platform-expected skips, plus 268
  subtests.

The preceding full rerun had 3,425 tests with 3,388 passes, 37 expected skips,
and no failures, and the provisional wheel/upgrade check also passed. Both are
now pre-correction evidence rather than final release evidence because this P1
changed executable code. Full shards, package synchronization, exact wheel,
upgrade, PR CI, tag, public Release, anonymous download, and post-release
checks must be regenerated from this fifth-correction tree.

### POSIX file-version follow-up

The joint-proof review then challenged a narrower POSIX detail. Directory
inventories already carried child timestamps, but the separately retained
Markdown snapshot stored only file identity, size, and SHA-256. The resolver
was strengthened before the final rerun so every candidate observation now
returns and retains a complete file stability token: mode, device, inode, link
count, size, modification time, change time, birth time when available, and
Windows file attributes. The token must be unchanged across the bounded read
itself and every later full-snapshot revalidation, in addition to the exact
content digest and directory inventory checks. An in-place change cannot be
hidden by restoring the former bytes because its file version token no longer
matches the initial stable observation.

After this follow-up, the complete Letter 140 approval/privacy, bound-read,
recovery, binding, CLI, service, and Windows CAS group again passed: 88 tests,
one platform-expected skip, and 106 subtests. Independent review of the updated
joint snapshot remains a gate before the final full shards begin.

The same review then found one concrete missing-root ordering gap on POSIX.
The resolver previously probed `zettels/` and `inbox/` before recording the
archive-root inventory. If an absent root was created inside the narrow
`FileNotFoundError` boundary, the later root inventory could absorb that new
directory as its baseline even though the directory had already been skipped
and would never be scanned. Windows already had an archive-root name watcher;
POSIX did not.

The resolver now records and holds the archive-root inventory before either
child-root probe. Any later creation, deletion, or replacement therefore
changes the retained root token/inventory and fails a full revalidation. A
deterministic regression creates an `inbox/` plus same-ID Zettel inside the
missing-root probe boundary; the corrected resolver blocks it. After this
ordering correction, the full Letter 140 plus Windows CAS group passed again:
89 tests, one platform-expected skip, and 106 subtests.

## Final frozen-tree validation before PR

The corrected joint-authority and pre-probe root-baseline tree received a new
independent read-only review. It reported P0=0 and P1=0 after tracing POSIX
directory/file version observations, the Windows archive-subtree closing
watcher, manifest-drift exception preservation, rollback, and both new
deterministic regressions.

The complete four-way unittest rerun then finished from that frozen executable
and packaged-document tree:

- shard 0: 1,377 run, 1,369 passed, eight expected skips, zero failures/errors;
- shard 1: 632 run, 623 passed, nine expected skips, zero failures/errors;
- shard 2: 691 run, 683 passed, eight expected skips, zero failures/errors;
- shard 3: 727 run, 715 passed, twelve expected skips, zero failures/errors;
- total: 3,427 run, 3,390 passed, 37 expected skips, zero failures, zero errors.

The explicit pytest-native CI list also passed 210/210. The release-readiness
gate passed public links, Korean product language, public privacy, and Runtime
Skill packaging. Package resources were synchronized and rechecked at 158
files, and `git diff --check` returned success with only Windows line-ending
advisories.

The final preserved candidate wheel is
`wom_kit-0.4.1-py3-none-any.whl` with SHA-256
`5c21c7d5d160e1a8d566df93e5797db6778bb97ec40bc1f64626983fa9dbd96c`.
The independent install checker verified 158/158 resources, 659,549 resource
bytes, 218 wheel files, all four CLI/MCP entry points, matching 130-tool MCP
inventories, Runtime Skill lifecycle, strict Doctor on the checked-in fake
archive, and the installed Letter 140 snapshot/link/receipt workflow.

In a fresh isolated `uv tool` root, the public v0.4.0 wheel reported
`archive 0.4.0`; installing the final local v0.4.1 wheel without `--force`
replaced it and reported `archive 0.4.1`. This is pre-release upgrade evidence.
After merge/tag/Release, the same test must be repeated using the anonymous
public v0.4.1 asset URL. PR CI, merge, exact tag, public Release, anonymous
download hash, public upgrade, and final cleanup remain pending.
