# Meeting minutes — staged-cleanup evidence correction

Date: 2026-08-13

## Chronology

1. The user directed the work to continue immediately after the human
   credential-console correction.
2. Work resumed on the staged cleanup report from the newest beta feedback.
3. The focused suite reproduced one compatibility defect: a valid official
   derived-text `repair_append` receipt was rejected by the verifier.
4. Independent adversarial testing reproduced a false-safe race: evidence bytes
   could change in place while size, inode, mode, and modification time remained
   equal.
5. A separate audit confirmed that the historical path-only deferred list could
   classify completely replaced bytes as cleanup-safe.
6. Re-reading the named feedback established that ordinary staged files also
   need a linked official receipt, not only manifest and store evidence.
7. The product contract was corrected: official repair receipts remain valid
   when the store is independently rehashed; every file authority carries an
   exact digest and is rehashed before return; missing/invalid ordinary receipts
   receive distinct reasons; deferred entries remain staged and block cleanup.
8. CLI output and operation control retain only bounded, content-free state while
   the complete local result is stored once under the scratch diagnostics
   boundary.

## Files changed

- `wom-kit/src/wom_kit/archive_services.py`
- `wom-kit/src/wom_kit/archive_cli.py`
- `wom-kit/src/wom_kit/operation_control.py`
- staged-cleanup focused and legacy tests
- public documentation, changelog, capability matrix, and this meeting record

## Boundaries

- The named feedback was read only; no protected archive content was changed.
- No provider, network, credential, or real user data was used.
- The checker remains report-only and performs no cleanup.
- Implemented and locally tested is not the same as merged or released.
