# Work Log: v0.2.12 Real Delegate Receipt Write

Date: 2026-05-23
Status: public-safe work log
Related release: v0.2.12

## Context

`v0.2.10` introduced dry-run `delegate-zet`, `attest-zet`, and `anchor-zet` previews.

`v0.2.11` then clarified the delegate capability contract with `counterparty_bound`, `claimable_once`, `delegation_capability`, `claim_binding`, and `settlement_condition: {mode: "none"}`.

This batch implements the next narrow step: real local delegate receipt writing. It intentionally does not implement transport, attestation writes, anchor writes, claim registries, spent registries, revocation registries, blockchain, payment, or UI.

## Work Performed

Implemented:

- `archive delegate-zet --approve --reviewed-by <actor>`,
- real receipt writes under `receipts/delegate/*.delegate.json`,
- reuse of the existing `delegate-zet --dry-run` gates before any approved write,
- duplicate receipt protection through dry-run blockers and exclusive file creation,
- applied delegate receipt validation in `archive doctor`,
- runtime schema validation support for the simple `if`/`then` conditional used by applied delegate receipts,
- real delegate capability nonce issuance,
- receipt-local claim/spent/registry state that explicitly marks claim, spent, and revocation registries as not implemented,
- `claimable_once` approved delegate receipts that can still defer `target_archive`,
- CLI tests for required approval, real receipt writing, duplicate blocking, and claimable-once approved writes,
- release, upgrade, README, CLI, and lifecycle documentation updates.

Release-review corrections before commit:

- fixed a broken Korean Summary in the `v0.2.12` release note,
- corrected the legacy MCP `share_check` tool schema so it again requires `target_archive`, matching the handler,
- added an MCP tool-list assertion that `share_check` remains legacy-target-bound while `delegate_zet_check` supports optional `target_archive` and `target_policy`.

## Behavior

Dry-run still previews the receipt and writes nothing:

```text
archive delegate-zet ./archive --view view.example --dry-run
```

Approved write requires an explicit reviewer:

```text
archive delegate-zet ./archive --view view.example --approve --reviewed-by person:me
```

Applied delegate receipts include:

- `dry_run: false`,
- `reviewed_by`,
- `reviewed_at`,
- generated capability nonce,
- `result.created_paths`,
- `registry_state` showing claim/spent/revocation registries are not implemented.

## Verification

Focused verification:

```text
python -m unittest ai-archive-kit.tests.test_cli.ArchiveCliTests.test_delegate_zet_dry_run_previews_receipt_with_hashes ai-archive-kit.tests.test_cli.ArchiveCliTests.test_delegate_zet_real_requires_approve_and_reviewed_by ai-archive-kit.tests.test_cli.ArchiveCliTests.test_delegate_zet_approve_writes_real_receipt ai-archive-kit.tests.test_cli.ArchiveCliTests.test_delegate_zet_claimable_once_approve_writes_receipt_without_target_archive ai-archive-kit.tests.test_cli.ArchiveCliTests.test_claimable_once_attest_binds_claimant_and_anchor_preserves_claim
python -m unittest ai-archive-kit.tests.test_mcp_server.McpServerTests.test_delegate_attest_anchor_checks_are_dry_run_only
```

One initial MCP focused-test command used the wrong test class name and failed before running the test. It was corrected to `McpServerTests`, and the focused MCP test then passed.

Full validation:

```text
python -m unittest discover -s ai-archive-kit\tests
python ai-archive-kit\cli\archive.py doctor ai-archive-kit\examples\fake-life-archive --strict
git diff --check
```

Result:

```text
145 tests OK, 8 skipped
doctor strict: 0 errors, 0 warnings
git diff --check: no whitespace errors; only expected CRLF normalization warnings
```

## Files Changed

- `ai-archive-kit/src/ai_archive_kit/archive_services.py`
- `ai-archive-kit/src/ai_archive_kit/archive_cli.py`
- `ai-archive-kit/src/ai_archive_kit/mcp_server.py`
- `ai-archive-kit/src/ai_archive_kit/__init__.py`
- `ai-archive-kit/src/ai_archive_kit/schema_validator.py`
- `ai-archive-kit/schemas/delegate-receipt.schema.json`
- `ai-archive-kit/tests/test_cli.py`
- `ai-archive-kit/tests/test_mcp_server.py`
- `CHANGELOG.md`
- `UPGRADE.md`
- `UPGRADE.ko.md`
- `VERSIONING.md`
- `README.md`
- `README.ko.md`
- `CITATION.cff`
- `ai-archive-kit/README.md`
- `ai-archive-kit/cli/README.md`
- `ai-archive-kit/docs/concepts/zet-sharing-lifecycle.md`
- `ai-archive-kit/docs/concepts/zet-sharing-lifecycle.ko.md`
- `ai-archive-kit/docs/releases/v0.2.12.md`
- `ai-archive-kit/plans/work-log-2026-05-23-real-delegate-receipt-write.md`
- `meeting-minutes/2026-05-23-v0212-real-delegate-receipt-write.md`
- `archive-infra-decision-log-2026-05-23.md`

## Follow-Up

Future batches can implement real attestation writes, real anchor writes, claim/spent registry design, revocation, P2P/workpack transport, or optional settlement references.

Those should remain separate feature steps so `delegate` does not silently become public-link sharing or transport.
