# Decision Log — v0.3.164 R2/S3 Upload Adapter (Stage 2)

Date: 2026-07-04
Batch: v0.3.164 (implements the IMPLEMENTATION-LOCKED spec merged from the Stage-2
design `wom-kit/plans/2026-07-03-r2-upload-adapter-design-locked.md` §§0–10 plus
Critique A (crypto) and Critique B (safety)).
Anchor tree at spec authoring: HEAD `6e613bc0` (v0.3.163, Stage 1 shipped).
Release action: working tree only — no git commit/tag/push. Never touches a real
archive or makes a real network call from tests.

This log records the resolution of every `required_change` and `open_question`
from both critiques, per the AGENTS.md decision-log mandate.

## Crypto critique (CA-*) — resolutions as implemented

- **CA-1 region `auto`** — ADOPTED. `region` threaded into both the credential
  scope `<date>/<region>/s3/aws4_request` and the `kRegion` HMAC. `auto` default
  for cloudflare-r2; `generic-s3` requires explicit region (resolver returns None
  otherwise). KAT V3 asserts `auto` in the scope line and that a different region
  changes the signature.
- **CA-2 per-operation content-sha256** — ADOPTED. PUT/UploadPart sign the real
  lowercase-hex payload hash; HEAD/GET sign `UNSIGNED-PAYLOAD`. No
  `STREAMING-AWS4-HMAC-SHA256-PAYLOAD`. KAT V4 asserts the selection.
- **CA-3 RFC-3986 URI/query encoding** — ADOPTED. `_sigv4_uri_encode`
  (unreserved `A-Za-z0-9-._~`, uppercase `%XX`, key `/` preserved, path encoded
  once) and `_sigv4_query_encode` (sorted by encoded key, `=` for empty). KAT
  covers `/`, `~`, space, `+`.
- **CA-4 header canonicalization + SignedHeaders** — ADOPTED. Lowercased names,
  collapsed values, sorted; `host`/`x-amz-date`/`x-amz-content-sha256` always
  signed; `x-amz-date` and scope date derive from ONE datetime. KAT V1 pins the
  block + SignedHeaders byte-exact.
- **CA-5 string-to-sign + 4-stage key** — ADOPTED. Raw-byte intermediates
  (`.digest()`), hex only on the final signature. KAT V1 pins canonical request,
  string-to-sign, AND signature byte-exact against the AWS documented example
  (signature `f0e8bdb8…bdb41`).
- **CA-6 known-answer vectors** — ADOPTED. V1 (AWS doc GET, third-party
  byte-exact anchor), V2 (PUT + real payload hash + `$` encoding), V3 (R2 region
  `auto` + `/`-containing key, frozen), V4 (`EMPTY_SHA256_HEX` /
  `UNSIGNED_PAYLOAD` constants + HEAD-vs-PUT hash selection). Re-derived at code
  time; not transcribed on faith.
- **CA-7 HEAD-after checksum contract (the showstopper)** — ADOPTED at the
  transport boundary; the executor comparison is UNCHANGED. **SUPERSEDED by the
  post-review correction below:** the CA-7-as-written mechanism (PUT base64
  `x-amz-checksum-sha256`, HEAD-after via GetObjectAttributes, base64→hex) does
  not work against R2. It is replaced by re-download-and-hash (HeadObject +
  GetObject re-hash), which satisfies the same unchanged executor comparison. See
  "Post-review corrections (2026-07-04)".
- **CA-8 multipart FULL_OBJECT** — ADOPTED as written, then **REVERSED by the
  post-review correction below:** `SHA256` + `x-amz-checksum-type: FULL_OBJECT` is
  an unsupported combination on both AWS S3 and R2 (SHA-256 multipart is
  COMPOSITE-only; full-object multipart is CRC-only). The shipped multipart path
  sends no checksum-type header and verifies the whole object by re-download-and-
  hash. See "Post-review corrections (2026-07-04)".
- **CA-9 retry classification on error CODE, fail-closed on auth** — ADOPTED.
  `_object_storage_classify_http_status` maps SignatureDoesNotMatch/
  RequestTimeTooSkewed/InvalidAccessKeyId/AccessDenied/403/400 → `auth` (no
  retry); 429/503-SlowDown/500-InternalError/conn-reset → `rate_limited`. No body
  ever returned/logged.
- **CA-10 injectable single-egress seam** — ADOPTED. `S3CompatibleTransport`
  takes `send`; only `_default_urllib_sender()` reaches urllib. Structural proof
  replaces the source grep.
- **CB-Q1..Q5** — LOCKED as the unit/live boundary; region `auto`, one-datetime
  x-amz-date, precomputed-hash streaming PUT, fail-closed skew, all as above.

## Safety critique (SA-*) — resolutions as implemented

- **SA-1 build before flip** — ADOPTED. The real transport + KATs land and pass
  before the capability flags flip; the flip is the last code edit.
- **SA-2 hard total-run PUT ceiling** — ADOPTED. `OBJECT_STORAGE_TOTAL_PUT_CEILING`
  = 64; `object_storage_upload_run` counts cumulative provider PUT/put_part calls
  and aborts with `total_put_ceiling_exceeded` independent of `--max-objects`.
  Test drives the ceiling to 0 and asserts abort before any PUT.
- **SA-3 bounded retry + attempt ceiling** — ADOPTED.
  `OBJECT_STORAGE_MAX_ATTEMPTS_PER_OBJECT` = 4, `OBJECT_STORAGE_BACKOFF_BASE_MS`
  = 200; exponential backoff with jitter via an injectable `sleep` seam; auth
  fails closed with zero retries; real `retry_summary.backoff_ms_total`. Tests
  cover bounded-then-fail, immediate-auth-fail, and recover-within-ceiling.
- **SA-4 leak gate extended to derived material** — ADOPTED. Structural exclusion
  primary (signing material lives in transport locals); belt-and-suspenders adds
  the derived hex `kSigning` to the run's `key_values`. Test proves a leaked
  signing key fails the run closed.
- **SA-5 multipart HEAD-after-mismatch cleanup** — ADOPTED. `delete_object`
  (new Protocol + NullTransport + transport method) is invoked on a
  completed-then-mismatch before returning `failed_upload`. Test asserts the
  delete fires with the right key.
- **SA-6 tiered tiny-first gate** — ADOPTED. `object_storage_proven_tier` derives
  the store's highest proven tier from durable receipt facts; a run whose requested
  tier exceeds proven+1 REFUSES with `tiered_gate_unmet`. **Tier model corrected
  post-review:** receipts are one-per-object, so tier 3 (batch) is derived from the
  COUNT of distinct successful receipts (≥ `OBJECT_STORAGE_TIER3_BATCH_MIN`) plus a
  tier-2 large-object proof — not a per-receipt `object_count`, which was always 1
  and made the tier-3 branch dead code. Tests prove the bulk-first-live refuse, the
  single-then-batch refuse, and the receipt-set tier derivation reaching tier 3.
- **SA-7 structural no-socket proof** — ADOPTED. T-NN3 split into: (a) no
  boto3/httpx/requests import; (b) no transport METHOD references
  urllib/socket/ssl/http.client/urlopen — only `_default_urllib_sender` does; (c)
  patch the default sender factory to raise on any call and assert every Stage-2
  path still passes (fakes injected).
- **SA-8 KATs before flip** — ADOPTED (see SA-1/CA-5/CA-6).
- **SB-Q1..Q5** — LOCKED per the above.

## Design-doc residuals reconciled

- §10 R4 (manifest atomic+locked): already shipped in Stage 1; Stage 2 keeps the
  locked writer. §10 R1 (`--skip-uploaded` trusts only `wom_uploaded`): kept.
  §10 R3 (crash-safe ledger): kept, authoritative every re-run. §10 R6 / §6.2:
  made concrete by CA-8. §9 R2 (SigV4 unprovable in temp dir): now KAT-pinned;
  residual reduced to live acceptance only.

## Deviations from the literal spec (documented)

- **Capability-flag flip scope.** The spec's Part IV grep-hit list named the
  evidence-registration surface (`archive_services.py:40984`) and the
  audit surface (`:41541`) alongside the upload base result (`:55743–55744`). We
  flipped `live_object_upload_adapter_implemented` / `provider_api_call_implemented`
  to true ONLY on the upload-adapter surface (the shared base result used by
  plan/verify/run). On the evidence and audit surfaces, `live_object_upload_adapter_implemented`
  is contextually a statement that THAT command performs no live upload (it only
  registers/audits external claims) — which remains true — and those surfaces
  also carry `provider_confirmation_by_wom_kit: False` / `object_bytes_read:
  False`. Flipping them would misreport those distinct commands and break their
  honest tests. The capability-matrix upload-adapter row (the "flip the row to
  real" intent) is flipped. This is the honest reading of the spec's intent.
- **CLI flags.** The spec said "no new flags required." A real PUT needs the
  non-secret endpoint host and bucket; these are supplied as optional
  `--endpoint-host` / `--bucket` / `--region` flags (all non-secret metadata) and
  the production `send` seam is wired for `--approve` only. The tiered gate
  itself remains receipt-derived (no flag), as specified.

## Post-review corrections (2026-07-04)

A code review of the first Stage-2 implementation found that three of the
spec's own load-bearing premises are physically impossible against the target
(AWS S3 / Cloudflare R2). These are release-STOPPING blockers, verified against
authoritative provider documentation, and are corrected here. The corrections
preserve every WOM invariant (unchanged executor hex comparison; never trust
ETag/size; fail-closed; no orphan objects).

- **Blocker — SHA-256 multipart + FULL_OBJECT is unsupported (was CA-8).** AWS's
  own algorithm/type table lists SHA-256 multipart as Composite=Yes,
  Full-object=No; full-object multipart checksums are CRC-only (CRC64NVME/CRC32/
  CRC32C). R2's S3-compatibility table marks SHA-256 + FULL_OBJECT "Feature Not
  Implemented." `create_multipart` no longer sends any `x-amz-checksum-algorithm`
  / `x-amz-checksum-type`. Refs:
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html>,
  <https://developers.cloudflare.com/r2/api/s3/api/>.
- **Blocker — CompleteMultipartUpload schema + Content-Type (was CA-8/finding 2,3).**
  The completion request now carries only the `<Part><PartNumber><ETag></Part>`
  list (no top-level `<ChecksumSHA256>`, which for SHA-256 would be a COMPOSITE
  checksum-of-checksums and is not how a whole-object checksum is conveyed anyway)
  and an explicit `text/xml` Content-Type. AWS forbids
  `application/x-www-form-urlencoded` for CompleteMultipartUpload; the default
  sender would otherwise apply it to any body-carrying request. Single-part PUT and
  UploadPart now send an explicit `application/octet-stream` Content-Type, fixing
  both the protocol violation and the stored-object metadata. Verified on a
  loopback socket that no request is form-urlencoded.
- **Blocker — GetObjectAttributes is unimplemented on R2 (was CA-7/finding 5).**
  R2 lists GetObjectAttributes in neither its supported nor unsupported operation
  tables, and marks the `x-amz-checksum-*` headers "Feature Not Implemented." The
  original CA-7 mechanism (store base64 sha256 on PUT, read it back via
  GetObjectAttributes) therefore could never confirm a real upload — every
  HEAD-after would report present:False and the SA-5 cleanup would DELETE a
  genuinely-uploaded object. **Resolution (the spec's own CB-Q2 fallback):**
  `head_object` now issues a `HeadObject` (presence + `Content-Length`) followed
  by `GetObject`, and re-hashes the returned bytes to the lowercase hex the
  executor compares. This is provider-agnostic, identical for single-part and
  multipart, and depends on no provider checksum surface. Upload requests still
  sign the real payload sha256 in SigV4 for on-wire body integrity.
- **Should — multipart retry class was swallowed (SA-3 multipart).**
  `_object_storage_multipart_put` caught every provider error and returned
  `status_class="failed"`, collapsing a `rate_limited` mid-multipart failure so the
  executor's bounded retry loop saw `failed` and gave up after one attempt. It now
  propagates the real `status_class` from `_ObjectStorageProviderError` (and aborts
  the in-flight upload on failure), so a throttled multipart part retries to the
  attempt ceiling exactly like the single-PUT path. New tests cover mid-multipart
  rate_limited (retries to ceiling), recover-within-ceiling, and auth (zero
  retries).
- **Should — dead tier-3 branch / tier model (finding 6).** See the corrected SA-6
  entry above: tier 3 is now derived from the count of distinct successful
  one-per-object receipts plus a tier-2 large-object proof, replacing the
  unreachable per-receipt `object_count > 1` branch.
- **Should — V2/V3 SigV4 KATs were tautological.** V2 and V3 asserted the computed
  signature equalled a re-invocation of the same signer (can never fail). They now
  pin literal expected signatures: V2 against the AWS-documented PUT example
  (`98ad7217…108bd`) and V3 as a frozen R2 vector
  (`47de6b43…708374`, region `auto`, `/`-containing key), both derived with an
  independent reference implementation.
- **Nits.** Explicit `application/octet-stream` on all body PUTs (stored metadata
  correctness); the misleading tiered-gate test renamed to state that the batch
  REFUSES after a single object; the leak-gate derived-material comment documents
  that the per-request Signature/Authorization are covered structurally (not
  precomputable) and now also adds yesterday's `kSigning` to survive a UTC-midnight
  boundary. The total-PUT ceiling remains enforced at object granularity (a bound,
  not a literal per-PUT cap), backstopped by the per-object attempt ceiling and the
  tiered gate.
