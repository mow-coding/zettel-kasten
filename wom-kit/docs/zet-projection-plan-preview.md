# ZET Projection Plan Preview

Date: 2026-05-26

## Summary

v0.2.46 adds the first executable dry-run layer after the ZET publication surface baseline.

`archive projection-plan` accepts one existing local archive zet and one operator-declared surface kind. It returns a safe planning preview for human review before any render, write, provider call, publication, receipt, or ZET transport exists.

This is planning only. Posting is not minting, and a surface locator is not canonical zet identity.

## CLI

```powershell
archive projection-plan <archive-root> --zet <zet-id-or-archive-relative-path> --surface <surface-kind> --dry-run --format json
```

Supported surface kinds:

- `wordpress_private_blog`
- `static_site`
- `private_workspace`
- `rss_feed`
- `generic_surface`

Optional flags:

- `--visibility private|team|public|unknown`
- `--projection-format metadata_only|safe_html_summary|plain_text_summary`

Visibility is operator-declared intent, not verified provider state. Projection format is future intent, not rendered body output.

## Output Boundary

The preview may include safe metadata:

- archive id,
- zet id,
- archive-relative zet path,
- simple title/status/kind metadata when safe,
- body hash,
- line/word/character counts,
- future review steps,
- closed gates,
- mutation flags set to false.

It does not output the full zet body.

## Closed Gates

v0.2.46 keeps these actions closed:

- provider calls,
- WordPress publishing,
- projection writes,
- projection receipt writes,
- minting,
- trust/import/acceptance,
- attestation writes,
- signatures,
- anchors,
- ZET transport,
- Redis, queues, background workers,
- payments, staking, consensus, blockchain,
- model training, backpropagation, full-auto execution.

## Future Sequence

The intended future order remains:

```text
minted zet
-> projection-plan dry-run
-> scope gate
-> explicit human approval
-> projection receipt preview
-> later provider-specific publisher
```

v0.2.46 stops at the dry-run plan.

## Relationship To Closed Sharing

v0.2.47 adds the ZET closed sharing model baseline. Projection planning is about a local zet and a user-selected surface. Closed ZET sharing is the future relationship/permission layer for shared zet updates between people, groups, archives, agents, or workspaces.

The two layers can meet later, but v0.2.47 still does not publish, write projection receipts, update neighbor feeds, run ZET transport, or accept shared zets automatically.

v0.2.48 adds the ZET radio-frequency recommendation model baseline. It documents future recommendation provenance only; projection planning still does not fetch recommendations, rank feeds, update neighbor feeds, or publish anything.
