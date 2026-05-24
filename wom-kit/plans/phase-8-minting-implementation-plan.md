# Phase 8 Minting Implementation Plan

Status: proposed
Date: 2026-05-22

This plan follows:

- `wom-kit/specs/zettelkasten-zet-product-blueprint.md`
- `wom-kit/specs/zettelkasten-zet-implementation-research.md`
- `wom-kit/docs/open-source-publication-model.md`

## 1. Goal

Implement the first local proof of the `zet` lifecycle:

```text
draft zet
-> mint
-> canonical private zet inside zettel-kasten
-> mint receipt
-> draft snapshot
-> source/edge/provenance validation
```

This phase does not implement external `zet` sharing.

## 2. Non-Goals

Do not build in this phase:

- P2P sharing,
- SNS/feed publishing,
- messenger behavior,
- collaborative workspace sync,
- Notion import automation,
- Google Drive import automation,
- object storage upload automation,
- CRDT editing,
- blockchain anchoring,
- DID/UCAN compatibility.

Those are future layers.

## 3. Existing Baseline

The current project already has:

- zettel spec,
- zettel lifecycle spec,
- zettel-kasten actions/policies/rules,
- draft inbox,
- canonical zettels,
- object manifests,
- source maps,
- archive identity,
- archive lineage,
- workpacks,
- receipts,
- doctor checks,
- tests.

Phase 8 should extend this baseline rather than inventing a new structure.

## 4. Proposed User-Facing Command

```text
python cli/archive.py mint-zettel <archive> --draft <draft-id-or-path> --reviewed-by <person-id> --approve
```

Potential compatibility:

```text
promote-zettel
```

can remain as an alias or legacy vocabulary for the same internal action.

## 5. Minting Rules

Minting means:

```text
private archive issuance
```

It does not mean:

- external publication,
- SNS posting,
- sharing,
- workpack export.

## 6. Mint Transaction Outputs

The command must create/update:

1. canonical zet in `zettels/`,
2. mint receipt in `receipts/mint/`,
3. draft snapshot in `receipts/mint/drafts/`,
4. source refs in the canonical zet envelope/frontmatter,
5. typed edges,
6. local AI session provenance if present,
7. integrity hashes,
8. index update or index rebuild trigger.

## 7. Draft Snapshot Policy

Use the selected policy:

```text
inbox draft is copied/snapshotted into receipts/mint/drafts/
canonical zet is written into zettels/
inbox is cleaned or marked according to archive policy
```

The original draft content must remain recoverable from the mint receipt path.

## 8. Receipt Schema

Add:

```text
schemas/mint-receipt.schema.json
```

Minimum fields:

- receipt_id,
- action,
- archive_id,
- actor,
- reviewed_by,
- created_at,
- input draft path/hash,
- output zet id/path/hash,
- source refs,
- edges,
- local AI session refs,
- checklist result,
- side effects.

## 9. Validation

Update doctor checks so they can warn or fail when:

- a canonical minted zet lacks a mint receipt,
- receipt hashes do not match files,
- source refs point to missing objects or invalid external refs,
- edges use unknown link types,
- local AI session provenance points to external AI URLs,
- provider URLs appear where object ids/source bindings are required.

## 10. Test Plan

Add tests for:

- successful mint from draft path,
- successful mint from draft id,
- draft snapshot creation,
- mint receipt creation,
- canonical status update,
- source refs preserved,
- typed edges preserved,
- invalid edge type rejected,
- missing reviewed_by rejected,
- external AI URL rejected as local AI provenance,
- doctor validates example mint receipt.

## 11. Open Implementation Choice

One implementation choice remains:

```text
Should mint-zettel be a new command,
or should promote-zettel remain the command and mint be product language?
```

Recommended:

```text
Expose mint-zettel as the new user-facing command.
Keep promote-zettel as internal/legacy alias if already implemented.
```

## 12. Acceptance Criteria

Phase 8 is complete when:

- `mint-zettel` works on the fake archive,
- mint receipt schema exists,
- doctor validates minted zets and receipts,
- tests pass,
- documentation explains minting as private archive issuance,
- no external sharing behavior is introduced.

