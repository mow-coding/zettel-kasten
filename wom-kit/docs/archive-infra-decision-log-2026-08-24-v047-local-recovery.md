# Archive infrastructure decision log - v0.4.7 local recovery

## Recovery evidence does not invent targets

Captured objects, source mirrors, and prior receipts are candidate authority.
Only a unique target joined through the target's own preserved source identity
may enter an executable manifest. Title-only or ambiguous evidence remains a
review result; an absent target never authorizes recapture or target creation.

## Current evidence wins over historical totals

Every plan binds the complete observed population, its classifications, and
their digests. An operator-supplied expected total is a fail-closed assertion,
not a goal for the implementation to manufacture. A mismatch stops that
operation and leaves other recovery domains available.

## Writes are field-scoped and receipt-bound

Title recovery owns only `frontmatter.title`; object linking owns only
`frontmatter.assets`; locator recording owns only the reviewed coordinate set;
marker restoration owns only transaction-attributed omission markers. Later
changes to unrelated fields or bodies cannot silently expand the approved
effect.

## A plan is not a repair

A recovery is complete only after native exact-human approval, the common
checkpointed writer, interruption/resume coverage, field-scoped revert,
independent verification, and a durable result receipt all succeed. Public
results contain counts and digests but no private identifiers, paths, titles,
provider locators, or source values.

## Human approval is a decision, not a manual audit

WOM computes population totals, source and target hashes, field effects, and
archive identity. The first execution presents one native run/cancel decision
over that bound manifest; it does not require the operator to count records or
compare digests. A manifest identifier is required only for exceptional resume
or revert so the tool can reload the already approved private control without
replanning or asking for the private evidence again.

## Existing commands gain exact local execution instead of new command families

Single-object capture and receipt-bound edge revert use the same native
selection-digest approval as the batch recovery writers. The ordinary unbound
approval route remains fail-closed. An exact capture may bypass only the legacy
persistent live-write marker for that one approved selection; it does not grant
general archive write authority, provider access, or credential access.

## Public output is bounded even when the private manifest is large

Normal dry-run and approval summaries publish the manifest identifier, effect
digest, classification totals, and content-free warnings. They do not print the
complete per-item manifest. The full manifest remains privately bound to the
approval, checkpoint, resume, verification, and revert controls, so reducing
terminal output does not weaken the operation binding.
