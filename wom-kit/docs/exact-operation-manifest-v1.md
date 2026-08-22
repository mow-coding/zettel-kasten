# Exact Operation Manifest v1

`ExactOperationManifest` is the domain-neutral execution foundation for a
reviewed multi-item operation. It lives in
`wom_kit.exact_operation_manifest`; it is not a CLI command and it does not
create approval authority.

## Exact manifest

Every manifest binds:

- the operation code and archive-identity digest;
- a stable item ordinal and opaque item id;
- the exact target kind, private target reference, and stable target-identity
  digest;
- each selected field's pre-state, post-state, and source-evidence SHA-256;
- independent target-set, source-set, effect-set, and whole-manifest digests.

The complete manifest is private operation material because it can contain
target and field references. `approval_digest_context()` is the content-free
projection suitable for a public plan. A direct dataclass construction is
revalidated, so callers cannot bypass the same digest checks used by
`from_document()`.

`None` represents an absent field. Domain adapters encode every other typed
value to exact bytes before calling `hash_field_value()`.

## Existing approval broker

`operation_approval_binding.exact_operation_manifest_approval_binding()`
adapts the manifest to the existing `ExactOperationApprovalBinding` and native
exact-human workflow. It requires an existing `ExactHumanApprovalOperation`,
an exact operation-code match, and an archive id whose digest matches the
manifest. It does not mint a second token format, dialog, claim store, or
approval workflow.

After the existing claim is authenticated, callers create an
`ExactOperationApprovalAuthority` from its strict public reference. The
authority binding participates in the execution digest. The first item-start
checkpoint contains the content-free approval id, context digest, authority
digest, and their binding digest; every later checkpoint must match it. A
resume with no authority or another claim therefore addresses a different
execution and cannot consume the original checkpoint chain.

## Execution and resume

`apply_exact_operation()` performs this sequence:

1. publish an immediate content-free preflight state;
2. load and verify the hash-chained checkpoint journal;
3. validate every selected pre/post/source payload;
4. independently preflight every selected target and field before the first
   write;
5. append an item-start checkpoint;
6. compare the current field hash, write only from the exact expected source
   state, independently read the field back, and append a field receipt;
7. append the item-verification checkpoint;
8. independently verify the complete selected post-state;
9. create or exactly match one durable final result receipt.

If a process writes a field and stops before its receipt is appended, `resume`
accepts the destination hash only for the item already recorded as started.
Future items must still have their exact source state. Existing checkpoints
require an explicit `resume=True`, while a resume request without a checkpoint
fails closed.

Each `field_verified` checkpoint contains a
`wom-kit/exact-operation-field-receipt/v1` digest. It binds the execution,
target identity, field, pre/post/source hashes, and independently observed
destination hash. The checkpoint rows themselves form a separate hash chain.
The checkpoint-store adapter is responsible for durable create/append and
readback semantics.

The common `FileExactOperationCheckpointStore` writes active JSONL journals
under the ignored private root
`profiles/local/exact-operations/checkpoints/`. Every append is fsynced and
strictly reread. `exact_operation_writer_lock()` holds the one fixed
archive-wide OS lock at `profiles/local/exact-operations/.writer.lock`, so
R2, locator, Notion, and later exact-operation writers cannot mutate the same
archive concurrently. The persistent lock marker is local state, not a Git
receipt.

After all item checkpoints and independent verification succeed, the store
publishes a create-or-match content-free receipt under
`receipts/ops/exact-operations/`. That receipt contains state, counts, and
digests, including the approval binding digest; it does not contain target
paths, field values, approval ids, or approval context. A process that stops
after the final item checkpoint can recompute the identical stable result and
idempotently finish this receipt on resume. Finalization independently requires
the complete canonical checkpoint chain and matching item/field/receipt counts;
an empty or partial journal cannot publish a final receipt.

## Field-scoped revert

`revert_exact_operation_fields()` requires an explicit set of `(item_id,
field_ref)` pairs. It compares only those fields against their exact post-state
and writes their exact pre-state. It deliberately does not bind a whole-file
hash, so a later legitimate edit to an unselected field does not destroy safe
revert authority. The target identity still has to remain stable.

## Progress contract

The runner publishes its first preflight state before invoking any injected
adapter. The public timing constants are:

- first status deadline: 2 seconds;
- heartbeat interval: 10 seconds.

Payload, checkpoint, writer, and verifier adapters receive a `heartbeat`
callback. Any adapter call that can run longer than ten seconds must call it at
least once per interval; blocking I/O that cannot cooperate must use a timeout
of ten seconds or less. Heartbeats are throttled with `time.monotonic()`, so
tight per-field loops do not create thousands of redundant events. A progress
sink is observability only: its failure is counted in the result and never
becomes write authority or a false rollback signal.

## Same-claim process resume

The existing exact-human claim remains the authority. The private workflow
core can rehydrate only a cryptographically authenticated claim with the same
fixed approval id, byte-identical context, and `started` status. It does not
display another native prompt and opens the existing archive key with
`create_if_missing=False`. Before entering the writer, an operation-specific
wrapper must prove that the checkpoint addressed by the exact execution digest
exists. Terminal, tampered, context-drifted, missing-checkpoint, and
different-claim resumes fail closed.

Generic writer and checkpoint-guard injection remains underscore-only test
infrastructure. There is intentionally no public generic resume callback API;
each production domain exposes only its fixed, non-injectable operation
wrapper.

## Deliberate boundaries

The common module does not acquire source data, choose targets, display
approval UI, persist credentials, or define a domain transaction. A domain
adapter must establish those boundaries, reuse the existing exact-human
approval workflow, supply independently readable targets, hold the common
writer lock, and use the common durable store before enabling its writer.
