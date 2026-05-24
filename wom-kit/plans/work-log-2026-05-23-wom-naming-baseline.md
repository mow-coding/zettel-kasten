# Work Log: WOM Naming Baseline

Date: 2026-05-23
Status: public-safe work log

## Context

After `v0.2.12`, the project naming was reviewed.

The user decided that the umbrella name should be:

```text
WOM
Widesider of Modernity
```

The name expresses the ambition to widen the horizon humans can perceive at the frontier of modernity.

## Work Performed

Recorded and reflected the naming baseline:

- `WOM` as the umbrella name,
- `zettel-kasten` as historical root and local archive method,
- `zet` as the active text primitive,
- `node` as the subject/archive participant,
- `tie` as a candidate relationship/capability term,
- `mint -> delegate -> attest -> anchor` as the preferred lifecycle,
- `promote` and `share` as legacy/general compatibility language,
- `workpack` / `pack` / `import` as compatibility terms moving toward `parcel` / `admit`,
- `receipt` as the current implementation-compatible term, with product language moving toward `proof`, `credential`, and `attestation`,
- `credit` reserved for possible future attribution/contribution/settlement semantics rather than core evidence.

## Files Added Or Updated

- `wom-kit/docs/concepts/naming-and-terminology.md`
- `wom-kit/docs/concepts/naming-and-terminology.ko.md`
- `README.md`
- `README.ko.md`
- `wom-kit/README.md`
- `wom-kit/cli/README.md`
- `wom-kit/docs/public-documentation-map.md`
- `wom-kit/docs/public-documentation-map.ko.md`
- `wom-kit/docs/concepts/product-philosophy.md`
- `wom-kit/docs/concepts/product-philosophy.ko.md`
- `wom-kit/docs/concepts/foundational-product-whitepaper.md`
- `wom-kit/docs/concepts/foundational-product-whitepaper.ko.md`
- `wom-kit/docs/concepts/zet-sharing-lifecycle.md`
- `wom-kit/docs/concepts/zet-sharing-lifecycle.ko.md`

Local detailed records were also updated but remain ignored by the public repository policy:

- `meeting-minutes/2026-05-23-zet-terminology-correction-and-naming-audit.md`
- `archive-infra-decision-log-2026-05-23.md`

## Implementation Follow-Through

This batch also implemented the first compatibility-safe CLI aliases:

- `mint-zet` as the preferred alias for `mint-zettel`,
- `parcel` as the preferred alias for `pack`,
- `admit` as the preferred alias for workpack import dry-run.

The old commands remain valid. This is intentional because current v0.2 compatibility still depends on names such as:

- `wom-kit`,
- `mint-zettel`,
- `zettels/`,
- `receipts/`,
- `workpacks/`,
- `archive promote`,
- `archive share`.

The project now has a bridge: new public language can use `mint-zet`, `parcel`, and `admit`, while older examples, scripts, and archive paths continue to work.

## Version And Release Records

This work became:

```text
v0.2.13 WOM Naming Baseline
```

Additional files updated:

- `CHANGELOG.md`
- `UPGRADE.md`
- `UPGRADE.ko.md`
- `VERSIONING.md`
- `CITATION.cff`
- `wom-kit/docs/releases/v0.2.13.md`
- `wom-kit/pyproject.toml`
- `wom-kit/src/wom_kit/__init__.py`
- `wom-kit/src/wom_kit/archive_cli.py`
- `wom-kit/tests/test_cli.py`

## Verification

Verified on 2026-05-23:

```powershell
python -m unittest discover -s wom-kit\tests
python wom-kit\cli\archive.py doctor wom-kit\examples\fake-life-archive --strict
git diff --check
```

Results:

- unit tests: 148 tests passed, 8 skipped,
- strict doctor on fake archive: 0 errors, 0 warnings,
- diff check: no whitespace errors; Git reported Windows line-ending normalization warnings only,
- privacy scan: no newly introduced private local path, token, or secret found in the public-scope changed set; generic examples and security-policy terms remain intentional.
