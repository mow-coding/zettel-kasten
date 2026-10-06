# Archive infra decision log: letter 185 (2026-10-06)

Status: implemented for v0.4.67 under the owner's standing instruction.
Executing AI: Claude Fable 5.1. The design choices below were made by the
worker's recommendation under the owner's 2026-09-25 design delegation; they
were not individually approved.

Letter 185 came from v0.4.66. The session-scoped Git backup of letter 184
worked for the customer (42 zettels, 173 paths, remote ref verified). The
remote preservation preview of their 21 objets then stopped:
`object-storage-upload --this-session --dry-run` with a store label taken
from the ledger returned `writer_unavailable` and the helper could not tell
which of several possible causes it was. Their 21 captures had been approved
through a window before the grant, so the approvals carry no session mark.

## A. What `writer_unavailable` means

The writer line has exactly four causes, all about the `--provider-kind` and
`--store-ref` arguments: no live transport for the provider kind, an unsafe
label, no registration under the label, a registration whose facts differ.
The preview already carried `writer_unavailable_reason` and the registered
labels (v0.4.36), but a reader who only looked at the state and the blocker
could not see that.

Decisions:

1. The preview carries `writer_unavailable_explained`: a fixed `category`,
   the `reason`, a sentence of meaning, what it `is_not` (a missing writer,
   another writer, a lock, a credential, the session scope, the manifest or
   index), that the scope and the manifest were not evaluated, and plain
   sentences.
2. `preservation_relation` states that a Git backup never holds objet bytes
   and what the remote preservation state is (`blocked_before_plan`,
   `planned_not_performed`, `nothing_to_upload`, `review_required`). A Git
   backup completion and remote preservation are two facts.
3. A label seen in the ledger is not necessarily the registered label; the
   preview says so and lists the registered ones.

## B. Captures approved through a window

A capture approved through a window carries no session mark, so
`--this-session` cannot attribute its objects. The capture is complete and
its receipt is valid; only the attribution is missing. Changing the claim is
impossible and undesirable (claims are MAC-verified and immutable).

Decisions:

1. `object-storage-scope-list --approval-id <id>` (repeatable) adds the
   objects captured under exactly those approvals: a valid capture receipt
   naming a MAC-verified succeeded capture claim with the same context
   digest, the same evidence the session selector already uses, minus the
   session mark. The person names their own approval ids from their own
   batch results; nothing is inferred from names, dates or other sessions.
2. The result counts the named approvals: found, succeeded captures, without
   a session mark, objects, and approvals with no valid capture receipt. No
   id and no object id is echoed.
3. When `--this-session` selects nothing, the upload refusal carries a
   diagnosis in counts (objects marked for this session, for other sessions,
   without a mark and their approval count, without a valid receipt), the
   meaning of the mark, and the exact-approval route.
4. No "attribution correction" writes anything. The reviewed object list is
   the correction; it is bound to receipts and claims and never widens.

## Boundaries

Verified with a synthetic archive, receipts and claims (the claim store
boundary substituted) and the real CLI. The customer's store label, their
registered labels and their run are not verified.
