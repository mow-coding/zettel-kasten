# Resume an interrupted prepared registration

`objet-capture-batch` now records the original prepared request, selected items,
source-intake completion and approval scope in private authenticated recovery
evidence before registration. Its existing exact-operation journal records
whether the complete registration has been independently verified.

After an interrupted attempt, keep the prepared request, staged source files
and private evidence. Fix the reported `cause_code`, then pass the returned
`recovery.approval_id` and `execution_sha256` to the official resume command:

```text
archive objet-capture-batch ./synthetic-archive --resume --approve --reviewed-by person:synthetic-owner --approval-id APPROVAL_FROM_RESULT --execution-sha256 EXECUTION_FROM_RESULT --format json
```

The archive and reviewer must match the original approval. Resume loads the
original scope itself; do not supply a replacement manifest, new plan digest or
source-intake execution. The new command creates a new operation journal and
links it to the original operation and registration execution in `recovery`.

WOM rehashes the prepared sources and completed objects. An already registered
object is skipped. An exact object whose bytes were published before its
manifest record is repaired without creating a duplicate. Existing local
receipts remain unchanged; a resumed attempt produces its own truthful receipt.
The final exact receipt is written only after all selected effects and the
successful local receipt have been independently checked.

Resume accepts only the original authenticated started claim and checkpoint.
Changed selections, altered sources, tampered evidence, other archives and
already completed claims are refused. A claim originally authorized through a
session permission also needs the same session presenter and currently valid
permission; an expired or revoked grant is not reused. Refusals preserve state
and report a fixed cause without echoing private source paths or error text.

Cancellation remains cooperative: the current effect reaches its safe boundary
before the attempt stops. Resume does not automatically repeat the command.
Attempts made before this recovery evidence existed still need a fresh reviewed
plan; an old local receipt is not retroactively converted into an approval.

Verification uses synthetic local archives and the real CLI, claim and capture
paths with a simulated native approval and archive authentication key. This is
not evidence of a customer registration, physical approval dialog, or remote
provider acceptance.
