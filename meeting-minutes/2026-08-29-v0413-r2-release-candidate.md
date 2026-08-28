# 2026-08-29 v0.4.13 R2 preservation release candidate

## User intent and operating boundary

- The user asked that work continue until the beta-client problems are genuinely handled, without confusing a development release with a completed client-data recovery.
- The public development repository is the only write scope for this release task.
- The private beta-client archive, provider credentials, provider APIs, and feedback ledger remain outside the development release write scope.
- A client problem may be marked resolved only after the client installs the released project runtime, runs the exact operation on its own archive, and returns independently verifiable terminal evidence.

## Implementation completed

- v0.4.13 adds create-only, resumable R2 byte preservation with exact setup evidence, immutable request identity, pre-call durable journal reservations, conservative call-budget accounting, and terminal receipts.
- Resume distinguishes observed, charged, and ambiguous provider calls. It does not repeat a PUT after a single exact remote match and does not treat an ambiguous multipart attempt as complete without exact remote evidence.
- Receipt readers remain compatible with the v0.2 and v0.3 terminal receipt schemas.
- The link-index full-scale benchmark is bound to the exact candidate commit and wheel instead of an ambient checkout.

## Corrections made during release verification

- The installed-wheel compatibility smoke originally hard-coded the previous package version. It now receives the actual built package version.
- Three historical smoke archives no longer construct incomplete minimal archives. They copy the checked-in fake archive, preserve its archive identity, build a current index before writers, and fail closed on synthetic target collisions.
- Duplicate reconciliation now preserves pre-existing manifest rows and verifies only the exact synthetic target.
- A v0.3 receipt schema newline and mixed v0.2/v0.3 receipt-shape handling issue were corrected before packaging.

## Evidence at candidate commit

- Candidate commit: `682e990f5e4ac6eb9db8fd513b2127dc5d7e28f7`.
- Candidate wheel: `wom_kit-0.4.13-py3-none-any.whl`.
- Candidate wheel SHA-256: `6149703c6ec76b834a8424521f6392d1b4a34f7f3243fa943e064a2ae8c19c90`.
- The isolated installed-wheel check passed for all four entry points, historical recovery workflows, strict Doctor, packaged resources, privacy checks, and exact version agreement.
- An independent offline install verified every RECORD entry, all 167 packaged resources, `pip check`, the real `archive` entry point, and byte identity between all 76 packaged Python files and the candidate source tree.
- Independent security and release-readiness audits found no real Windows user path, private archive path, credential, or secret in the public candidate.
- The Windows link-index full-scale benchmark passed at 8,616 Zet, 22,441 Objet, and a 37 MiB manifest.
- The Doctor full-scale functional, privacy, first-status, heartbeat, and scan-count checks passed, but both measured Doctor modes exceeded the 180-second limit on the local Windows machine while another full-scale benchmark was running. The threshold is not weakened. The authoritative Ubuntu pull-request gate must pass before merge.

## Pull-request CI correction

- PR #89's first Ubuntu Python 3.10 shard found one historical-evidence test failure. The test hashed checkout bytes, so Windows CRLF bytes and the committed LF Git blob had different hashes.
- The correction does not replace the evidence or weaken its expected value. The test now reads the exact blob from the annotated v0.4.12 tag, asserts the current HEAD blob remains byte-identical, and hashes those platform-neutral Git bytes.
- The v0.4.12 evidence blob is 5,458 bytes with SHA-256 `b115168676d71a1b3c71dcde47af0fb6db2820ddf94b43b3983be407c75bb20c`.
- The focused historical test and the complete link-index benchmark module passed after the correction: 15 tests and 10 subtests.
- An independent review found no P0, P1, or P2 issue. All required CI jobs must run again against the corrected head.

## Pending release steps

1. Push the candidate branch and open a pull request.
2. Require every Ubuntu and Windows test shard plus both scale gates to pass.
3. Merge the exact reviewed head.
4. Tag the exact merge commit, publish one wheel, download it anonymously, and re-verify its hash and clean installation.
5. Do not install it into or run it against a beta-client archive from the development session.
