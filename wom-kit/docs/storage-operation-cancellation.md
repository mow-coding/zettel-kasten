# Storage operation cancellation boundaries

Cooperative cancellation means finishing and recording the current safe unit
of work before stopping. It does not forcibly terminate network calls or undo
effects. Keep the operation journal, result artifact, original saved plan and
domain receipts for reconciliation or resume.

| Operation | Safe boundary | Recovery |
|---|---|---|
| `object-storage-cleanup` | Before a selected key; after DELETE, direct absence check and signed per-key outcome | Original exact request with `--resume`, under current applicable approval; reconciles unknown outcomes before another DELETE |
| `object-storage-cleanup --inventory` | Between listing pages and complete GETs; before signed inventory publication | Start a new inventory run; partial scans are never published as qualifications |
| `object-storage-restore` | Before a GET; after verified GET, optional local promotion and immutable receipt; before and after manifest publication | Saved original plan, approval ID and execution digest through the existing resume options |
| `object-storage-restore --verify-only` | Before a GET and after verified receipt | Original saved verification plan and the existing resume options; no canonical local promotion or remote mutation |
| `object-storage-upload` | After a terminal ledger entry; separately before and after manifest and receipt publication | Original saved plan, approval ID and execution digest; reuse a verified completed transfer |
| `object-storage-adopt-existing --preserve-local-only` | Before transfer and after its terminal ledger and receipt | Original preservation plan, approval ID and execution digest |
| `object-storage-offload` | After native unlink, durable receipt and marker cleanup | Original plan and claim; reconcile the recorded unlink before continuing |
| `activity-cleanup` | After bound deletion and its journal; between preservation and verification children | Original activity request with `--resume`; finish interrupted children before deleting sources |

The terminal result retains both the cause of interruption and recovery
identifiers. Restore may report a durable receipt without an `item_verified`
checkpoint: cancellation can occur after the receipt but before the common
runner finishes that checkpoint. Resume independently verifies the saved
receipt and local state before reusing the completed effect. It does not
replace the original selection or use an expired grant.

A terminal upload ledger is not a formal receipt. Activity cleanup propagates
child cancellation and records unfinished items: cancellation acknowledgement
does not prove that a child operation completed. Activity restore also checks
between child restores before external create-only publication. Its engine
recovery is verified separately from the public cleanup command. Formal adoption
and browser opening are separate paths from the modes in the table.

Cancellation records reuse the currently active authenticated approval's
bounded MAC capability. The capability is bound to the same archive and a
started claim, uses a fixed cancellation domain, and does not expose key bytes.
Remote-disposal records use a separate fixed-domain capability. This avoids
opening another protected key consumer while an approved writer is active.
Cross-archive calls, completed claims and tampered requests are rejected.
Activity journals and remote preservation proofs also have separate bounded
fixed-domain capabilities. Proof storage can capture the exact active claim for
a provider worker thread; a captured claim cannot sign after its completion or
close. No arbitrary key-access callback is exposed by these capabilities.

## Verified scope

Synthetic tests exercise the actual approval broker, operation journals,
cancellation records and public cleanup, inventory, restore, upload,
preservation, offload and activity cleanup CLI handlers.
They verify that Ctrl-C leaves an independently bound terminal result, that
status distinguishes acknowledgement from completion, and that resume does
not repeat a completed DELETE, restore GET or preservation PUT. A strict key
provider rejects nested key consumers in these tests.

Provider responses and native approval are injected synthetic boundaries.
These checks are not evidence of live R2 behavior, a physical Windows approval
dialog, actual customer receipt, or released-package acceptance.
