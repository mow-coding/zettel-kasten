# ZET Shared Update Record Baseline

Date: 2026-05-27
Status: public concept and example baseline

## Summary

v0.2.55 defines a future ZET shared update record shape.

A shared update record is a receiver-side review artifact. It is not the actual transport, not a feed update, not trust, not import, and not an attestation or signature.

The goal is to make one future question clearer:

```text
When another node shares a zet update with me, what local review record might I inspect before renewal?
```

## Sender And Receiver Are Different

ZET sharing has two sides.

Sender-side actions:

- `mint -> 발행`
- `delegate -> 공유`

Receiver-side renewal actions:

- `attest -> 수용`
- `anchor -> 반영`
- `attest + anchor -> 갱신`

ZET becomes a real sharing layer only when a receiver can review and renew what was shared. A sender publishing and opening access is not enough by itself.

In other words:

```text
sender: mint + delegate
receiver: review -> attest + anchor -> 갱신
```

v0.2.55 documents the review-record shape that may sit before receiver-side renewal.

## Product Language

This baseline follows the v0.2.50 Korean product-language anchors:

| Product term | Korean product term |
| --- | --- |
| `mint` | 발행 |
| `delegate` | 공유 |
| `attest` | 수용 |
| `anchor` | 반영 |
| `attest + anchor` | 갱신 |
| `block` | 상자 |
| `header` | 초록 |
| `body` | 본문 |
| `foreign block` | 소포 |
| `quarantine` | 검문소 |
| `neighbor` | 이웃 |
| `feed` | 담벼락 |
| `receipt` | 영수증 |
| `provenance` | 족보 |

A shared update record may describe a shared `block` / 상자 without including the `body` / 본문. It may refer to a `header` / 초록, provenance / 족보, receipts / 영수증, and review state. It should not pretend to be the shared body itself.

The `header` / 초록 is not merely technical metadata. It also serves as the guide and index surface for review and AI indexing: it lets a reviewer or AI runtime connect issuer, refs, provenance / 족보, receipts / 영수증, review state, and other safe connection hints before reading the full `body` / 본문. This does not expose or include the body itself.

## Relationship To ZET Sharing Forms

A shared update record may later apply to several ZET forms:

- messenger-type ZET: `1:1`, usually key-sharing-based,
- SNS-type ZET: `1:many`, key-sharing and/or radio-frequency style,
- workspace-type ZET: `many:many`, key-sharing, radio-frequency, and/or mirroring style.

These are conceptual future forms. v0.2.55 does not implement transport, feeds, key registries, radio-frequency access, mirroring delivery, or workspace sharing.

## Relationship To User Surfaces

A surface, or 수제 앱, may later display or project shared updates.

Examples may include a private archive UI, a team workspace, a static site, an open-source ZET UI, or a borrowed surface such as WordPress.

WordPress can be a projection surface example. It is not WOM, not ZET itself, not the canonical archive, and not real ZET transport.

## Example Shape

See:

- [ZET Shared Update Record Example](../examples/zet-shared-update-record/)

The example is non-executable and public-safe. It keeps:

- `dry_run: true`,
- `body_included: false`,
- all mutation, write, transport, provider, trust, import, acceptance, anchor, attestation, signature, and full-auto flags set to `false`.

## v0.2.56 Review Preview

v0.2.56 adds a read-only review preview for one local shared update record:

```powershell
python wom-kit\cli\archive.py shared-update-record-review <archive-root> --record <archive-relative-json> --dry-run --format json
```

The command reads only the selected archive-relative JSON record. It writes nothing, does not read a shared body, and does not create trust, import, acceptance, attestation, signature, anchor, feed update, projection, provider call, receipt, or ZET transport effects.

The MCP tool is:

```text
zet_shared_update_record_review_preview
```

MCP requires `dry_run: true` as a boolean and exposes no write/apply/publish/transport/import/trust/attest/anchor sibling tool.

## v0.2.58 Review Index

v0.2.58 adds a read-only review index for direct-child local shared update record JSON files:

```powershell
python wom-kit\cli\archive.py shared-update-record-review-index <archive-root> --records-dir <archive-relative-dir> --dry-run --format json
```

The index reuses the v0.2.56 single-record review preview policy for each JSON record. It writes nothing, ignores non-JSON files, does not recurse, and does not create review records, feed updates, trust, import, acceptance, attestation, signature, anchor, provider calls, projection writes, receipts, or ZET transport effects.

The MCP tool is:

```text
zet_shared_update_record_review_index
```

MCP requires `dry_run: true` as a boolean and exposes no write/apply/publish/transport/import/trust/attest/anchor sibling tool.

## Non-Goals

v0.2.58 still does not implement:

- shared-update transport,
- neighbor feed update,
- automatic `젯 갱신하기`,
- `쿠키 굽기` recommendation behavior,
- trust/import/acceptance/anchor,
- attestation/signature writes,
- provider sync,
- WordPress publishing,
- projection writes or projection receipts,
- ZET transport,
- review writes or approval records.

v0.2.55 was a docs/examples/version baseline only. v0.2.56 adds a read-only preview command and MCP tool only. v0.2.58 adds a read-only index command and MCP tool only.
