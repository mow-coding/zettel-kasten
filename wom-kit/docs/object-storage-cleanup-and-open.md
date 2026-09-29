# Remote temporary-object disposal and opening

`object-storage-cleanup` permanently removes an exactly selected remote copy
after it has been qualified as unnecessary temporary material. There is no
mandatory waiting period, backup copy or recovery promise. Objects with a
current note/draft reference, retained snapshot dependency, uncertain content,
or unresolved writer ownership remain preserved with a reason code.

`object-storage-open` verifies an uploaded remote object's complete bytes,
creates a short-lived GET link, and passes it directly to the default browser.
The link is not printed or saved. Its default lifetime is 900 seconds; supported
values are 60–86400 seconds. This is browser delivery, not proof that a person
viewed the document. The browser may retain its own history.

Both commands use the existing exact approval and work-session permission
system. An existing applicable `allow_all` grant is honored. Providing
`--reviewed-by` alone is not approval. All examples below are synthetic.

## Connection and execution

The same connection flags as the existing remote storage transport apply:

```text
--provider-kind cloudflare-r2
--endpoint-host synthetic.r2.cloudflarestorage.com
--bucket synthetic-objets
--region auto
--access-key-id-ref env:SYNTHETIC_R2_ACCESS
--secret-access-key-ref env:SYNTHETIC_R2_SECRET
```

Use credential references, never literal credentials in arguments or request
files. A dry run does not read credential values or call the provider. An
approved operation checks the actual transport endpoint/bucket/region against
the private plan binding before a provider call.

```text
archive object-storage-cleanup ARCHIVE --request profiles/local/disposal-request.json --dry-run CONNECTION_FLAGS
archive object-storage-cleanup ARCHIVE --request profiles/local/disposal-request.json --approve --reviewed-by person:owner CONNECTION_FLAGS
archive object-storage-cleanup ARCHIVE --request profiles/local/disposal-request.json --resume --approve --reviewed-by person:owner CONNECTION_FLAGS
archive object-storage-open ARCHIVE --object-id sha256:OBJECT_HASH --store-ref storage:account:synthetic --ttl-seconds 900 --approve --reviewed-by person:owner CONNECTION_FLAGS
```

Replace `CONNECTION_FLAGS` with the separate flags above. `--expected-plan-sha256`
can bind an invocation to a previously reviewed preview. Resume reconciles the
saved per-key state; it does not reuse an old approval claim as new authority.
The ordinary current permission mode still controls execution.

## Stopping an approved cleanup

Approved cleanup and inventory runs publish an `operation_ref` and a separate
result artifact through the existing operation journal. A cooperative cancel
request, including Ctrl-C, waits for a safe boundary. It does not kill a provider
request, undo a completed deletion, or promise immediate interruption.

Cleanup checks before each selected item and after DELETE, its direct absence
check, and the signed per-key outcome record. A stopped result distinguishes
completed items, unknown outcomes and items not attempted. An unknown outcome
keeps the reference fence until reconciled. Use the original request with
`--resume` and the current applicable approval to reconcile the per-key journal;
this command does not reuse an earlier approval claim.

Inventory checks between list pages and complete GETs, and before publishing
its signed inventory. Cancellation never publishes a partial qualification.
Run inventory again through the ordinary approval route when ready.

An acknowledged request only proves that a safe checkpoint was reached.
`operation-control` reports cancellation completed only after the command has
ended and its result is recorded. A completed scan or final write can win a race
with a later cancellation request. Browser opening is not included in this
cancellation contract. See [storage cancellation boundaries](storage-operation-cancellation.md).

## Legacy objects and missing upload receipts

A missing upload/adoption receipt does not permanently exclude an object.
First obtain an authenticated private inventory through the official command:

```text
archive object-storage-cleanup ARCHIVE --inventory --request profiles/local/inventory-request.json --dry-run CONNECTION_FLAGS
archive object-storage-cleanup ARCHIVE --inventory --request profiles/local/inventory-request.json --approve --reviewed-by person:owner CONNECTION_FLAGS
```

The inventory request names exact keys, or one explicit nonempty prefix:

```json
{
  "schema": "wom-kit/remote-disposal-inventory-request/v1",
  "store_ref": "storage:account:synthetic",
  "remote_binding": {
    "service": "s3",
    "endpoint_host": "synthetic.r2.cloudflarestorage.com",
    "bucket": "synthetic-objets",
    "region": "auto"
  },
  "keys": ["legacy/synthetic intermediate.txt"]
}
```

Use `"prefix": "legacy/"` instead of `keys` for a bounded-prefix inventory.
Listing follows every continuation page, rejects duplicate keys/token loops,
and performs a whole GET for each result. An interrupted/incomplete inventory
does not publish a usable qualification. The output gives a private inventory
path. That file holds exact keys, actual SHA-256 identities, sizes and entry IDs,
authenticated with the existing archive key. Review it locally.

Prepare a private cleanup request referencing that inventory:

```json
{
  "schema": "wom-kit/remote-disposal-request/v1",
  "provider_kind": "cloudflare-r2",
  "store_ref": "storage:account:synthetic",
  "remote_binding": {
    "service": "s3",
    "endpoint_host": "synthetic.r2.cloudflarestorage.com",
    "bucket": "synthetic-objets",
    "region": "auto"
  },
  "inventory_path": "profiles/local/remote-disposal/inventories/INVENTORY_DIGEST.json",
  "entry_ids": ["sha256:ENTRY_DIGEST"],
  "classification_path": "profiles/local/disposal-classification.json",
  "management_path": "profiles/local/disposal-management.json"
}
```

The digest placeholders are copied from the reviewed inventory, not guessed.
For an already known exact object, `entries` may replace `inventory_path` and
`entry_ids`. Each entry then contains `remote_key`, `object_id` and integer
`size`; the approved execution still re-downloads and hashes the entire remote
body. Inventory and disposal do not promote legacy material into the canonical
object manifest and do not forge a historical upload receipt.

Classification and management are separate evidence:

```json
{
  "schema": "wom-kit/remote-disposal-classification/v1",
  "entries": [{
    "entry_id": "sha256:ENTRY_DIGEST",
    "object_id": "sha256:ACTUAL_BODY_HASH",
    "decision": "temporary_unnecessary",
    "reason": "Synthetic intermediate output; the reviewed final material does not depend on this copy."
  }]
}
```

```json
{
  "schema": "wom-kit/remote-disposal-management/v1",
  "archive_identity_sha256": "sha256:ARCHIVE_IDENTITY_DIGEST",
  "store_ref": "storage:account:synthetic",
  "remote_binding": {
    "service": "s3",
    "endpoint_host": "synthetic.r2.cloudflarestorage.com",
    "bucket": "synthetic-objets",
    "region": "auto"
  },
  "authority": "exclusive_wom",
  "external_writers": "excluded",
  "immutable_keys": true,
  "entry_ids": ["sha256:ENTRY_DIGEST"]
}
```

Copy the archive identity from the signed private inventory. It uses the existing
exact-approval domain-separated identity contract, not a bare hash of the ID.
Management evidence asserts an established
operating fact: these exact keys are managed only through this archive, are not
overwritten, and other devices/apps cannot write them during disposal. A local
lock, bucket name, API credential, filename or content-addressed shape alone does
not establish those facts. If they are unresolved, record them as unresolved;
the result remains `external_writer_possible` or `needs_management_binding`.
The next step is establishing management scope, then producing a new preview.

## Safety, persistence and completion

All requests/evidence are under the effective Git-ignored `profiles/local/`
boundary. Exact keys are opaque UTF-8 provider values; they are never converted
to filesystem paths. Two keys with identical bytes have different entry IDs.

The cleanup engine takes the existing object/target leases, rechecks complete
reference evidence under the archive writer lock, and publishes a signed
pending tombstone before network work. Reference writers must honor this fence.
Readers filter tombstoned remote locations; another retained remote copy or a
local copy remains usable after deletion completes.
The standard upload writer also checks the signed exact-key disposal state
when planning and again under the archive lock and object lease immediately
before execution. A pending, unknown-outcome or deleted key cannot be uploaded
again, even if an earlier upload plan was already approved.
When a new note references an object with a completed disposal record, WOM also
requires a surviving copy: it re-hashes local bytes or checks another official
verified remote-location record. A matching whole-byte preservation receipt can
also prove a surviving remote copy before formal adoption. An old manifest entry for the deleted key or
an unverified declared location does not satisfy this check. Checking an existing
remote record during a note write is not a fresh provider availability check;
opening or restoring the object still verifies the complete remote bytes.

Deletion requires a fresh whole authenticated GET matching the exact body hash
and size. It writes intent before DELETE, then confirms absence with a direct
S3 HEAD. If interrupted after deletion, resume checks absence without repeating
DELETE. If the object remains, resume obtains another whole-byte proof before
retrying. A changed body is preserved; unknown outcomes keep the fence until
reconciled. A signed per-key record distinguishes completed deletion from an
unverified provider response. No automatic backup or quarantine is created.

R2's documented S3 compatibility does not establish conditional `DeleteObject`
support. The built-in adapter therefore does not claim or send conditional
DELETE. Execution is limited to qualified exclusive immutable-key management.
A future provider adapter may explicitly expose verified conditional-delete
support; then the exact strong ETag from the whole GET is required. AWS feature
support is not treated as proof of R2 support. See [R2 S3 compatibility](https://developers.cloudflare.com/r2/api/s3/api/).

Presigned links are bearer credentials and use the S3 endpoint. They can be used
until expiry; WOM does not promise one-use or custom-domain behavior. See
[R2 presigned URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/).
Remote deletion is permanent; see [R2 object deletion](https://developers.cloudflare.com/r2/objects/delete-objects/).

## Verification boundary

Synthetic tests cover official CLI preview/approval, the actual exact-approval
broker with injected native/key boundaries, legacy qualification, current and
historical references, changed remote content, interruption before/after DELETE,
resume, journal authentication, pagination failures, exact-key location filtering,
SigV4 encoding, TTL and browser-delivery failures without URL disclosure.

No customer account, customer bucket or customer credentials were accessed.
Separately authorized development R2 tests also passed real whole-byte GET,
conditional HEAD, exact-key deletion and direct absence confirmation, legacy
inventory qualification, identical-byte copy selection, current-reference
preservation, and client-injected response loss followed by reconciliation.
The source CLI and an exact installed candidate passed inventory, cleanup, saved
unknown-outcome resume without another DELETE, independent result artifacts and
remote-open signed GET delivery. Installed critical module bytes were compared
with that candidate wheel before invoking its public entrypoint and parser.
Only small synthetic objects were used, and every trial object was removed.

Those live checks used an injected native approval adapter and fetched the
signed URL through a browser-delivery adapter. They do not prove a physical
Windows approval dialog, physical browser launch, a public release or customer
acceptance. Overall disposal completion also requires all canonical
reference and remote-location writers/readers to use the shared fence/projection
hooks.
