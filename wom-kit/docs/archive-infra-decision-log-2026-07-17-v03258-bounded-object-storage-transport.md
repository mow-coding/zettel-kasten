# Archive Infra Decision Log - v0.3.258 Bounded Object-Storage Transport

Date: 2026-07-17

Status: accepted for v0.3.258 implementation and release

## Context

The default S3-compatible sender read an entire `data_path` into one `bytes`
value for every single PUT and read every successful or error response without
a size bound. The single-PUT threshold is 5 GiB, and every successful upload is
verified by a whole-object GET, so a valid operation could require several
gigabytes of RAM after the provider had already accepted the object.

The follow-up audit also reproduced a stronger integrity problem: a successful
PUT followed by an unavailable or truncated verification GET produced a null
checksum, which the executor treated as a proven byte mismatch and followed
with DELETE. The observed call sequence was `HEAD, PUT, HEAD, GET, DELETE` even
though the GET had not completed.

## Decision

1. v0.3.258 is restricted to the default S3/R2 HTTP sender, streamed
   verification evidence, and the executor's post-upload cleanup boundary.
2. The injected sender signature remains exactly `method`, `url`, `headers`,
   `data_path`, and `data_bytes`; no retry-on-`TypeError` compatibility shim is
   allowed after a mutating request.
3. A single path PUT uses a replayable iterable. Each iteration reopens the
   path and yields at most 1 MiB while preserving the already-signed
   `Content-Length`, `Content-Type`, and real `x-amz-content-sha256`.
4. The iterable fails closed if the bytes emitted no longer equal the signed
   length. It never silently switches to an unsigned or transfer-chunked
   payload contract.
5. A successful verification GET is consumed in 1 MiB chunks. Only SHA-256,
   actual byte count, and completeness are retained; object bytes are not
   returned by the default sender.
6. Legacy injected fake senders that return `body: bytes` remain supported for
   test and integration compatibility.
7. XML and provider error bodies are retained only up to a 64 KiB prefix.
   Oversized multipart-initiation XML is not trusted for an `UploadId`. A
   CompleteMultipartUpload HTTP 200 containing `<Error>` is classified as a
   failure and the in-progress upload is aborted before bounded retry.
8. The executor performs no unconditional mismatch DELETE. Even a complete GET
   proves only the generation read; a concurrent correct replacement could
   occupy the key before DELETE. Remote cleanup requires a future
   provider-supported generation/ETag condition.
9. The sender disables automatic redirects so SigV4 Authorization and
   `x-amz-*` headers cannot be forwarded to another origin. Redirect bodies are
   classified through the same bounded error path.
10. Only HTTP 200 is a complete HEAD/whole-object GET. A 206 response cannot
    become full-object evidence, and 404 is the only status that proves remote
    absence. Auth, rate, network, redirect, and other HEAD failures refuse PUT.
    Content-Length evidence accepts strict ASCII decimal at most 20 digits long;
    missing, oversized, or invalid size makes presence-size verification
    unavailable.
11. Bounded control XML is complete only when it reaches EOF without exceeding
    the cap and, when Content-Length is present, its strict declared size equals
    the bytes read. Multipart initiation refuses a short-but-plausible UploadId
    prefix, and invalid or contradictory control lengths fail closed.
12. Multipart part reads, the 5 GiB threshold, retry ceilings, cost gates,
   credential handling, key layout, receipt schemas, and unrelated mutation
   infrastructure do not change in this batch.

## Standards Basis

- Python `urllib.request.Request` accepts file-like or iterable byte bodies and
  uses an explicit `Content-Length` instead of adding chunked transfer encoding.
- Python `http.client` documents the same iterable-body rule and does not infer
  a length for file or iterable bodies when the header is absent.
- AWS SigV4 permits a single signed payload whose `x-amz-content-sha256` is the
  actual object digest.
- Cloudflare R2 requires `Content-Length` for PUT/POST requests and reports
  incomplete bodies as request errors.

## Verification Contract

- Sentinels reject every unbounded request-file, successful-response, and
  provider-error `read()`.
- The path body can be iterated twice with identical bytes and a fixed maximum
  chunk size.
- The stdlib request retains exact Content-Length and does not add
  Transfer-Encoding.
- Streamed GET digest and byte count match a known fixture, while the raw marker
  is absent from transport results.
- Truncated, failed, mismatching, missing-length, and HTTP 206 verification GETs
  never call unconditional DELETE.
- HEAD 503/transport failure never authorizes a new PUT; recorded-location
  re-verification also refuses an implicit repair PUT when verification is
  unavailable.
- The no-redirect opener retains a 3xx response locally and caps its body.
- A CompleteMultipartUpload 200-with-Error becomes a scalar retry class and
  triggers AbortMultipartUpload.
- Oversized control/error bodies are capped and cannot surface a canary placed
  beyond the cap.
- Existing SigV4 vectors, five-keyword fake sender, presence-only HEAD, retry,
  multipart, leak-gate, and object-storage command tests remain green.
- Independent reviewers must report no unresolved P0/P1 before versioning.

## Independent Review Outcome

Three independent read-only reviews found no remaining P0/P1 in the final
runtime/test boundary. Reviewers also reproduced the streamed PUT wire length,
redirect refusal, short GET/control response handling, presence-only unavailable
propagation, CompleteMultipartUpload embedded-error abort, and generation-safe
no-delete behavior against focused fakes or local HTTP servers.

The final local release gate passed 1,515 tests with 13 skips and 4,226 passing
subtests. Public-link, Korean product-language, public-privacy, runtime-skill,
and packaged-resource checks passed. A clean temporary environment built and
installed the wheel, exercised all four console entrypoints, and passed the
onboarding and strict-doctor smoke tests.

## Consequences

Peak memory for the default single-PUT and verification-GET path becomes
constant with respect to object size. A verification transport failure may
leave a correct remote object present and report failure; this is deliberate.
A complete mismatch may likewise leave an object for later operator/provider-
conditional cleanup. A later retry can prove or reuse the key, while an
unconditional DELETE could irreversibly destroy a concurrent correct object.
