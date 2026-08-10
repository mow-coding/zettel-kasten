# WOM v0.3.311 Letter 118 credential continuity and reviewed Notion recovery

Date: 2026-08-10 KST

## User request

The user directed Codex to read beta-tester Letter 118 from the read-only source
archive and proceed immediately with the next development step.

## Workspace and privacy boundary

- Development repository: the local `zettel-kasten` development checkout.
- Isolated worktree: the dedicated `codex/v0.3.311-letter118` worktree.
- Work branch: `codex/v0.3.311-letter118`, created from exact `origin/main`
  commit `49c46df138ab881f74f8ff44583b6d16a32ad9da` (`v0.3.310`).
- The source archive is read-only evidence. No credential value, provider URL, private body,
  archive zettel, objet, profile, locator, or collaboration state may be read or
  written outside existing content-free public contracts.
- Do not ask the operator to paste or reissue a PAT. Do not search the computer
  for token strings or bypass WOM through an ad-hoc provider script.

## Letter 118 outcome and failure boundary

The beta tester confirms that the project update to v0.3.310 succeeded: the
project pin, runtime, source tag, and integrity evidence align. Letter 118 then
reports two ordered blockers:

1. WOM cannot safely rediscover, distinguish, adopt, validate, and reuse a
   previously supplied external-service credential across AI sessions without
   exposing the secret value. Existing inventory and broker commands describe
   future behavior but do not open a supported adapter or bind provider,
   account/workspace, purpose, and scope to durable credential authority.
2. WOM cannot recover a reviewed finite list of 620 missing Notion pages into
   preserved source evidence and the existing retrieval ledger. Current
   `notion-recover` addresses ancestor structure rather than reviewed page-body
   recovery and has no itemized resume/replay receipt.

The reported inventory remains fail closed. Provider calls, secret reads,
credential reissuance, archive writes, and canonical zettel changes all remain
zero at the starting checkpoint.

## Initial decision

Treat credential continuity as a provider-neutral authority layer and Notion
recovery as one bounded consumer of that authority. Do not implement a
Notion-only secret file convention or accept a raw secret on the command line.
Do not let recovery discover a workspace broadly; the reviewed request manifest
must enumerate the complete allowed page-id set.

## Execution plan and feedback loop

1. Audit the existing credential, connected-account, broker, adapter-readiness,
   KeePassXC planning, Notion recovery, objet, ledger, journal, and receipt
   contracts.
2. Reproduce Letter 118 with content-free, read-only source-archive commands and prove
   that the archive and credential values remain untouched.
3. Check current official Notion, KeePassXC, OWASP, and NIST boundaries before
   accepting a live-adapter design.
4. Write fail-first public workflow tests for credential metadata discovery,
   explicit selection/adoption, session-stable rediscovery, approved-action
   secret handoff without disclosure, and reviewed finite-page recovery with
   itemized resume/replay.
5. Implement the smallest provider-neutral and Notion-specific surfaces that
   close the accepted contracts without inventing provider identity, opening an
   unapproved secret store, or editing canonical beta data.
6. Run independent adversarial review, focused and full tests, package/resource
   checks, clean-wheel install, exact public documentation checks, and a
   content-free fixed-code source-archive projection.
7. Only after all gates pass, decide commit, PR, exact tag, public release,
   anonymous fresh-install verification, and task-owned cleanup.

Next checkpoint: current-contract audit, official standards evidence, and
fail-first reproduction.

## Read-only reproduction and contract audit

The v0.3.310 runtime reproduced the reported boundary against the read-only source archive without
reading secret values or calling Notion:

- `credential-ref-inventory --dry-run` returned 54 catalog entries and 37
  blockers, with secret, environment, provider, and write flags all false.
- `connected-accounts --dry-run` returned three account records but no adopted
  Notion account/workspace authority. Its credential catalog remained
  `needs_review` with the same 37 blockers.
- The local credential-ref parser uses an ASCII-only locator expression. Of 44
  inspected content-free local rows, 36 legacy `secret:` locators contain
  Unicode metadata and are rejected as whole-row blockers. This is a locator
  grammar problem, not evidence that the referenced secrets are absent.
- Existing `notion-recover` code plans and fetches ancestor/nested-tree
  structure. It does not capture reviewed page bodies and has no per-page
  durable resume authority for the reported 620-item set.

The repository branch, tag, release, and package baseline were independently
audited before changes: `main == origin/main == v0.3.310` at `49c46df1`, with
PR 53, tag CI, GitHub Release, and its wheel present. A historical unrelated
stash was left untouched.

## Standards corrections to the implementation plan

Official Notion behavior changes two literal status promises from Letter 118:

- A 404 intentionally combines an unknown object with an object not shared to
  the connection. WOM must report `not_found_or_not_shared` (or an equivalent
  combined state) rather than inventing separate `deleted`, `not_shared`, and
  `not_found` conclusions. `deleted` may be used only when an accessible 200
  response explicitly reports `in_trash`.
- A personal access token can identify its user through `/users/me`, but it
  does not provide a reliable token identity or guaranteed workspace id.
  Durable WOM `credential_id` authority plus a reviewed workspace anchor is
  therefore required before the token is adopted for a recovery group.

The reviewed recovery request must preserve the two reported authorities as
separate groups: 577 items for one source group and 43 for the other, totaling
620. Each group binds an opaque credential id, credential binding revision,
workspace fingerprint, scope receipt digest, and exact item ids. Dry-run may
read only that request and local public state; it must call neither the broker
nor provider and must write nothing.

KeePassXC metadata listing is officially available after vault unlock, but its
CLI prints a protected field to stdout. WOM therefore needs a broker-owned
pipe that captures the exact-entry result and passes it directly to the trusted
provider consumer without returning it, logging it, including it in an
exception, or placing it on the command line or clipboard.

## First implementation checkpoint

The operator-feedback title defect was reproduced: the shared source-intake
guard treated the descriptive word `credential` as a secret by itself. The
title field now has a separate fail-closed normalizer. Descriptive security
words are allowed, horizontal whitespace is normalized, and actual secret
assignment/token shapes, provider URLs, email-like values, local paths, NULs,
and multiline values receive value-free reason codes. Focused lifecycle and
new title-policy tests pass.

Next checkpoint: merge the isolated credential-continuity and grouped
Notion-page-recovery modules into explicit CLI dry-run/approval surfaces, then
run adversarial leakage, replay, concurrency, and package tests.

## Letter 119 changed the prerequisite, 2026-08-10

While implementation was in progress, the user immediately shared Letter 119,
`WOM-전달-20260810-119-v0.3.310-인증정보수령후보존인계실패-단일본.md`, and asked whether it belonged in this work or after it. The complete letter was
read from the source archive without modifying it.

Letter 119 establishes that safe-looking credential-reference metadata is not
proof that any PAT was ever persisted in KeePassXC or another approved store.
The operator confirmed that two different, still-valid organization-workspace
PATs remained only in prior agent conversation records; one had been reissued
because a later session could not find the earlier value. A personal-backup
candidate likewise had to be found by the operator, not WOM. The letter does
not expose the values and explicitly forbids treating conversation-wide secret
search as a normal product workflow.

This evidence invalidated a possible implementation shortcut: writing an
adoption binding and receipt from a metadata candidate alone. The project
decision is that Letter 119 is not a later independent feature. It is the
missing prerequisite inside Letter 118 and must be handled before any 620-item
provider execution.

The revised ordered gate is:

1. create a content-free, expiring, one-use intake request;
2. receive the secret through a human-only masked local surface, never normal
   agent stdin, argv, environment, a plaintext file, chat, or tool output;
3. write it to one exact encrypted local-store target and prove exact presence;
4. verify provider identity plus a reviewed workspace anchor;
5. atomically commit a non-secret receipt and only then issue the durable
   credential id with `persisted: true`;
6. if any store, presence, identity, workspace, or receipt step fails, roll
   back the new store entry, issue no credential id, and return a fixed
   value-free reason code;
7. allow new-session rediscovery and approved consumer use by credential id;
8. compare duplicate credentials by non-secret fingerprint, require a human to
   choose one default, mark others `legacy_valid` or `revocation_pending`, and
   never revoke automatically;
9. only then execute the reviewed 577-item and 43-item recovery groups.

Implementation agents were redirected immediately. The metadata-continuity
approval gate now requires both exact-store and provider/workspace evidence;
the secure-intake core is a separate Windows-first worker boundary; and the
Notion recovery request remains unusable until it carries the verified scope
receipt. No historical conversation, PAT, OS vault, or provider was accessed
as part of development.

## Integrated core checkpoint and queued Letter 120

The first integrated test checkpoint completed with 69 focused tests passing:

- legacy credential discovery/adoption and one-time trusted-consumer broker;
- human-only secure intake, rollback, receipt, replay, and duplicate-lifecycle
  contracts;
- the fixed Notion 2026-03-11 HTTP adapter and reviewed-anchor identity check;
- grouped page recovery, exact Markdown byte capture, retry, crash repair,
  replay verification, ambiguous 404 handling, and 577 + 43 count binding.

All provider and store behavior in this checkpoint used injected fakes. There
were zero real OS-vault reads or writes, zero real Notion calls, zero secret
values, and zero source-archive mutations. A remaining integration gap was identified:
an ordinary local intake receipt is not by itself an authenticated next-session
broker authority. The current work therefore adds a stable archive-scoped HMAC
key, an authenticated ignored-local receipt registry, exact receipt/hash/
workspace verification, and a receipt-backed broker before exposing live CLI
approval commands.

The user then shared Letter 120,
`WOM-전달-20260810-120-v0.3.310-최근독자발행zet조회실패와-피드백본문계약부재-단일본.md`, while asking that the current work be finished first. It was accepted as the
next task and audited read-only without mixing its implementation into this
release. The audit found an independent index/query lifecycle defect and a
missing feedback-body contract. In particular, stale SQLite state can contain
both draft and canonical rows for one logical zet, omit a newer canonical zet,
and still be returned by `view-zets` or `search` without a freshness failure.
Mint conditionally updates the generated index and may reduce update failure to
a warning; draft retirement does not remove or invalidate the draft index row.
The next release must therefore fail closed on stale index reads, connect mint/
retire to explicit index invalidation and refresh, add provenance-aware
canonical query semantics, and bind reviewed feedback-body structure and hash.

Letter 120 will be implemented only after the Letter 118/119 release is closed,
from a fresh latest-main branch, because it is functionally independent even
though its feedback-record changes overlap the title-policy file touched here.

The source archive is a data folder with an empty `.git` boundary rather than a usable Git
repository. After Letters 119 and 120 had already been added by the user, a
content-free metadata baseline was captured for final comparison: 126,680
files and SHA-256
`ea3b70cc7fdc69077accc31b2e26ee5c2fb5d5faa80348c6d185b94eacec06fe`, computed
only from relative path, byte length, and UTC modification ticks. File contents
were not read for this integrity snapshot.

## Final integration review and interrupted-session recovery

Before freezing the live surface, independent review found that a successful
HTTP status was not enough to trust a Markdown response. The Notion adapter now
requires the official `object: page_markdown`, the exact requested page or
block id, and the official maximum of 100 `unknown_block_ids`. Page metadata
likewise requires `object: page` and the exact requested id. The workspace
scope fingerprint is derived from the stable reviewed anchor rather than the
token-specific user/bot id, so two valid credentials for the same reviewed
workspace can enter one human default-selection lifecycle while retaining
distinct account and token fingerprints.

Review also found that a three-requests-per-second pacer created once per run
does not protect the same Notion connection when two CLI processes run at the
same time. The release gate was strengthened to require an archive-local,
interprocess coordinator that is opened only immediately before a real
provider GET. Dry-run, rejected approval, credential failure, and fully verified
replay must still create no pacing file and make no provider call. A canonical
zettel byte sentinel was added to the recovery regression boundary.

The public credential-adoption approval is bound to a deterministic digest of
the complete safe request fields. Dry-run does not persist a random plan. On an
approved call, WOM rechecks the exact request digest, creates a fresh expiring
one-use worker plan in memory, and passes that same internal plan digest to the
spawned child. The PAT has no argv, environment, stdin, file, or CLI option.

The Codex turn was interrupted while a Windows test process was starting. The
user asked whether the work had been lost. The exact isolated branch and all
task files were re-audited; no implementation was lost. The interrupted test
pair was rerun and passed before work continued. This was a tool-process
interruption, not a repository reset, branch change, or archive mutation.

## Adversarial release review after continuation

The user was frustrated that the long-running task appeared to stop and asked
Codex to continue. Codex confirmed from the exact worktree and branch that no
implementation had been lost, updated the visible execution plan, and resumed
from the interrupted security-review checkpoint instead of restarting.

Independent review then found and closed several defects that would have made
an early release unsafe or dishonest:

- the first recovery pacer draft was only per process. It now uses one lazy,
  archive-local interprocess gate immediately before every provider GET attempt;
  dry-run, approval rejection, credential failure, and complete replay do not
  create its files;
- Notion projections now require exact HTTP 200, the official `object` shape,
  the exact requested UUID, valid timestamps, at most 100 unknown-block ids,
  bounded bodies, and no redirects carrying an Authorization header;
- exact Windows credential reads remain mutable and are wiped. The current
  vault value is re-fingerprinted and compared with the authenticated receipt,
  so overwriting the same target cannot silently substitute another token;
- authenticated receipt publication is terminal: after durable publication,
  a post-check cannot make the worker delete the credential and leave a false
  `persisted: true` receipt. Exact committer temp residue is safely recognized;
- duplicate valid credentials, including the same secret fingerprint, can be
  resolved by explicit human default selection without automatic revocation;
- spawned adoption and recovery results are reconstructed through parent-owned
  fixed shapes. Approval failures before process start report exact zero, while
  a child crash after start reports unknown durable state and requires same-plan
  reconciliation instead of falsely reporting zero writes;
- the complete Letter 118 request is enforced at the release CLI boundary as
  exactly `zet_notion_db3` 577 plus `zet_notion_db1` 43. A small pilot is a
  slice over that unchanged 620-item request, not a smaller substitute batch;
- recovery plan approval always includes possible credential reads, read-only
  provider GETs, and archive evidence writes for the selected slice. Verified
  replay is an optimization, so losing replay evidence between preview and
  approval cannot silently expand the approved authority;
- the recovery writer now uses the pre-existing zero-byte central object-
  manifest lock instead of poisoning it with a separate one-byte convention;
  and
- central object authority is exactly one row per object id. Two pages with
  identical Markdown reuse one object/manifest row and retain separate page
  projection rows; conflicting or duplicate authority fails closed.

The latest focused credential-intake, Windows-boundary, and registry run at
this checkpoint completed 52 tests with one environment-permission skip and no
real OS or provider call. The recovery module completed 44 tests with two
environment-permission skips. CLI planning also proved that the full reviewed
request stays read-only and that text output states the complete approval
capabilities without echoing private request paths or page ids.

Remaining gates are documentation/resource synchronization, complete local
regression and wheel/fresh-install evidence, independent final review, commit,
PR/CI, merge, exact tag and GitHub Release, then final source-archive metadata-only
comparison. Real credential adoption and the 620-page recovery remain separate
operator actions and have not occurred during development.

## Continued release-blocker audit and queued Letter 121

The final adversarial pass found two archive-authority corruption cases before
the release candidate was frozen. A newline-complete malformed or duplicate-key
JSONL authority row could previously be mistaken for a torn final append and
silently removed. Such complete corruption now fails closed as
`private_state_invalid` without rewriting the evidence; only a genuinely
incomplete final fragment remains repairable. An already occupied aggregate
receipt filename is now accepted only when the existing file has the exact
expected size, full SHA-256, and bytes. Pre-existing or unsafe conflicting
content fails closed as `recovery_authority_conflict`.

The ignored-local request gate already used a bounded descriptor for the 620-id
JSON request, but its `.gitignore` proof still used a separate `lstat` followed
by `Path.read_text`. It was changed to one bounded descriptor read with
before/opened/after identity and reparse checks, so a swapped ignore file cannot
authorize reading a request that is no longer protected. The focused swap,
private-path non-echo, malformed-authority, receipt-preemption, and exact replay
tests passed without a real credential, provider, or source-archive access.

While this release remained in progress, the user queued Letter 121,
`WOM-전달-20260810-121-v0.3.310-개인zet원문보존요청을-AI가임의축약하려한문제-단일본.md`.
The user asked that it be handled only after the current work and emphasized a
combined execution rule: finish work completely even if it takes time, but do
not inflate batches or prolong the work unnecessarily. The fixed sequence is
therefore Letter 118/119 release, Letter 120 as the next independent release,
then Letter 121 as a separate source-faithful preservation review. Letter 121
has been queued by exact path but not yet interpreted or implemented, avoiding
speculative scope changes in v0.3.311.

The release-blocking review was then frozen to five non-duplicated authority
items so the work would remain complete without becoming open-ended. All five
were implemented before the integrated regression:

- the approved archive identity is checked before live access and every
  semantic recovery commit, with prior observed work retained in partial
  operation counts after a later identity change;
- the one-use claim is bound to the archive-local claims root, holds and
  revalidates non-reparse parent authority, completes and syncs its write,
  atomically publishes the marker, and accepts only exact canonical replay;
- object, replacement, and JSONL writers complete short writes and verify exact
  published bytes;
- authenticated receipt/lifecycle/default authority is rechecked before every
  provider GET attempt, so concurrent human lifecycle changes stop the next
  call without another secret read or identity request; and
- authenticated list/lifecycle failures after archive-key access report native
  and key-read counts as unknown and possibly nonzero instead of exact zero.

The spawned-result projector was updated with the corresponding fixed reason
allowlist and arithmetic. In particular, a successful pacing grant followed by
an authority failure may honestly report one paced request and zero provider
calls, and a credential-resolution attempt may produce a zero-item partial
result with observed activity rather than an unknown-child-state false alarm.
The integrated credential/intake/registry/adapter/recovery/workflow run then
completed 173 tests with three environment-permission skips, and the nine
release-facing CLI selection tests passed. All of these remained injected and
made zero real OS-vault, Notion, or source-archive calls.

## Release-candidate regression and artifact checkpoint

After staging the complete candidate, the standard release readiness gate and
198 documentation/resource hygiene tests passed. The first four-shard Windows
run found two release-evidence defects rather than product-runtime failures:
the newly tracked minutes contained two local user-home paths, and new public
files repeated a sealed internal archive name forbidden by the predecessor
privacy subset. The paths were replaced with role-based checkout names and the
internal name with `source archive`; the existing privacy ceiling was not
relaxed. Both exact privacy tests then passed.

The rerun produced three fully green shards (465, 429, and 357 tests). The
1,375-test CLI shard first found one historical fixture title that now matched
the correctly rejected `secret_...` token shape. The fixture was changed to a
normal unpublished title while preserving its no-echo assertion. A complete
rerun passed that test and the other 1,374 assertions; one existing verified-
runtime subprocess exceeded its 30-second harness timeout under the long run.
That exact test passed twice in isolation. Its restored full-inspection timeout
was kept bounded but raised to 60 seconds for slower Windows/antivirus lanes.
Remote PR CI remains the independent full-shard authority.

The two pytest-native lanes passed 113 Windows authority tests and 90 cross-
platform private-index/finder tests. The final documentation, predecessor,
resource, continuity, and root-shim selection passed 220 tests. Artifact
hygiene reported no findings.

The clean temporary wheel workflow built and fresh-installed
`wom_kit-0.3.311-py3-none-any.whl`, verified all 144 manifested resources,
checked `archive`, `wom`, `archive-mcp`, and `wom-mcp`, ran onboarding and
strict doctor, removed the temporary environment, and preserved the wheel
outside the repository. Its SHA-256 is
`ac18630c6c6c3a5c0c889bf24c8e589673f5b185369f70e60dcb2a197d169d0b`.
