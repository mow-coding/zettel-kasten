# Meeting minutes — v0.3.317 local release preparation

Date: 2026-08-13

## Chronology

1. The user required the real-use credential console and staged-cleanup work to
   continue through completion instead of stopping at a partial implementation.
2. The credential correction established a two-owner console contract: the
   helper AI supplies reviewed public-safe task context, while WOM owns fixed
   security, masking, cancellation, persistence, and reuse wording. A matching
   registration is reused only after exact saved-secret fingerprint and current
   reviewed-anchor revalidation; replacement requires explicit reviewed intent.
3. The staged-cleanup correction established complete evidence chains for
   ordinary and exact paired-derived preservation, final exact-byte rehashing,
   content-free saved/control output, and a fail-closed deferred state.
4. After focused product verification, the work was assembled into the local
   v0.3.317 release scope. Version constants, current install guidance, English
   and Korean upgrade guidance, public maps, release tests, and the packaged
   current release note were updated together.
5. The first new release-test pass found four wording assertions that were more
   specific than the actual reviewed documents. The assertions were corrected
   to the existing source-faithful phrases; product behavior was not changed.
6. Package synchronization produced 145 exact resources for v0.3.317. The
   packaged current-note slot contains v0.3.317, while the v0.3.316 release note
   remains a source-only historical document.
7. Independent adversarial review then found that a receipt could outlive or
   disagree with its saved Windows secret. The reuse path was tightened to
   authenticate the receipt, read and HMAC-check only the exact selected entry,
   revalidate the current Notion anchor, observe authority again, and wipe all
   mutable buffers. Missing, tampered, unreadable, and anchor-mismatched cases
   now stop without opening another input console.
8. A later identity audit found that using the reviewed page as the Notion
   workspace fingerprint broke reuse across pages and that requiring only
   `bot.workspace_id` rejected a real person PAT. Official Notion PAT,
   `/users/me`, and User-object documentation was reviewed. The implementation
   now distinguishes internal-integration workspace IDs from person-PAT
   token-scoped witnesses while still requiring current reviewed-page access.
9. Released v0.3.311-v0.3.316 v0.1 credential receipts were confirmed to use
   the old reviewed-page basis. A compatibility design preserves the base
   receipt and saved secret, appends one authenticated local scope-evolution
   record after exact revalidation, and transitions only a simple singleton
   lifecycle. It opens no prompt and performs no provider or credential-store
   write/delete; ambiguous state stops for human review.
10. Release documentation and Agent Skill wording were revised to avoid calling
    the PAT witness a provider-returned workspace ID and to distinguish a human
    paste into the console from WOM or the helper AI reading the clipboard.

## Verification

The counts below describe the earlier release-document checkpoint. Credential
identity and evolution code changed afterward, so they are chronology rather
than final release evidence. A fresh frozen-tree focused and full test run is
required before final release judgment.

- 20 focused current/historical release, source-fidelity, and root-shim tests
  passed.
- 59 predecessor-surface, package-resource, private-resource-delta,
  wheel-integrity, and release-readiness tests passed.
- 152 capability-matrix documentation tests passed.
- Package-resource synchronization check passed for 145 files at v0.3.317.
- Canonical Git-text SHA-256 checks preserved the v0.3.316 release note and
  Letter 129 decision record unchanged.

## Boundaries

- This is local source and test completion only.
- No staging, commit, push, tag, GitHub Release, wheel publication, external CI,
  fresh wheel installation, live provider operation, or beta acceptance was
  performed by this release-preparation step.
- No private archive data, credential value, provider payload, or authenticated
  network service was used. Public Notion documentation was read over the
  network; no authenticated Notion request was made.

## Final frozen-tree verification

The implementation and release-candidate files were frozen before the final
runs. Start and end fingerprints matched.

- The full CLI suite ran 1,375 tests with 8 environment skips and no failure or
  error.
- The full non-CLI unittest suite ran 1,558 tests with 28 environment skips and
  no failure or error.
- Seven pytest-native modules ran 210 tests with no failure or error.
- Focused credential, staged-cleanup, release, package-resource, privacy, and
  documentation suites also passed. Package resources remained synchronized at
  145 files, and the independent final audit found no open P0 or P1 issue.
- This establishes a locally tested v0.3.317 release candidate. It still does
  not establish a commit, push, PR, external CI result, tag, published wheel,
  fresh-install result, live Notion operation, or beta-client acceptance.
