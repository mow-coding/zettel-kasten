# Archive infra decision log: letter 186 (2026-10-07)

Status: implemented for v0.4.68 under the owner's standing instruction.
Executing AI: Claude Fable 5.1.

Letter 186 came from v0.4.67. The store-label diagnosis of v0.4.67 worked for
the customer (an unregistered ledger label was named as such, the registered
label passed to `ready_for_exact_human_approval`). The new route
`object-storage-scope-list --approval-id` then found the customer's
succeeded capture approval, saw that it carried no session mark, and
attributed none of its 21 objects: `object_count: 0`,
`approvals_with_no_valid_capture_receipt_count: 1`, no list written.

## Root cause: a defect of mine, and an older one

A real objet-capture receipt carries the operation approval receipt:

```text
exact_human_approval:
  schema_version, operation, plan_sha256, target_binding_sha256,
  exact_human_approval: { approval_id, context_sha256, ... }
```

The reference is one level deeper than the selector read. The selector read
`exact_human_approval.approval_id`, found nothing, and skipped every real
receipt. Two consequences:

1. The v0.4.67 approval route never could have worked on a real archive. I
   verified it only against the synthetic receipt of the existing scope
   tests, whose shape was flat and had never matched production. That was my
   verification gap: the fix for a customer's blocked route was shipped
   without a receipt produced by the real writer.
2. The same reader served the session selector (`_session_owners`) since it
   was written. No real capture receipt was ever attributed to a session by
   its capture; session scopes were populated only through the
   session-object-usage records of later zet writes (which is why the
   customer's `--this-session` still found 22 objects through their 43
   links).

Reproduced with a receipt and claims produced by the real
`objet-capture-batch` writer under a window approval: the outer block has
no `approval_id`, the nested reference does.

## Decisions

1. `_approval_reference` reads the nested reference and, for a nested
   shape, requires the outer `operation` to be a capture operation. The flat
   shape stays accepted for synthetic or future receipts.
2. Every receipt or item that is not attributed is counted by a fixed
   reason: `envelope_invalid`, `approval_reference_missing`,
   `claim_not_found`, `claim_context_mismatch`,
   `claim_not_succeeded_capture`, `item_not_completed`. The scope-list
   result carries, for the named approvals, the number of receipts naming
   them and the summed rejections; the session diagnosis carries the
   archive-wide counts. No id, path or object id is echoed.
3. The scope tests' synthetic receipt now has the real nested shape, and a
   new test module produces receipts and claims with the real writer.
4. Nothing in the archive is rewritten; signed claims and the ledger are
   untouched. The customer needs no repair: rerunning the same command on
   v0.4.68 attributes the 21 objects.

## Boundaries

Verified with receipts and claims from the real writer in a temporary
archive, and with the synthetic scope fixtures. The customer's archive and
run are not verified.
