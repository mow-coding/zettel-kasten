# Work Log: v0.2.15 WOM Safe HTML Profile Validator Dry-Run

Date: 2026-05-23

Status: public-safe work log

## Context

`v0.2.14` documented the WOM Safe HTML Profile as the long-term canonical/interchange/rendering target for zets, and its compatibility-path section already named the next step as "add profile validator or Markdown-to-safe-HTML dry-run".

`v0.2.15` ships exactly that first step: a read-only CLI dry-run validator. The intent is to give existing v0.2 Markdown-compatible zets a way to be inspected for future Safe HTML compatibility, without writing any files and without making any normative commitment to the final element/attribute allowlist.

## Decision

Add a single new CLI subcommand:

```text
archive check-safe-html <archive-root> --path <zet> --dry-run --format json
```

It is read-only and intentionally narrow. It does not convert Markdown to HTML, change mint output, or migrate existing zets.

The proposed profile identifier is `wom-safe-html/v0.1-draft`. The `v0.1-draft` suffix is explicit: the WOM Safe HTML Profile is not yet a finalized standard, and the validator only flags an obvious block list of unsafe patterns at this stage.

## Block List

These zet body patterns are blocked, regardless of context:

- `<script>` elements,
- `<iframe>` elements,
- `<object>` elements,
- `<embed>` elements,
- `javascript:` URLs in links,
- inline event handler attributes such as `onclick=`, `onload=`, and other `on*=` attributes inside an HTML element.

Normal Markdown-compatible text passes without blockers.

## JSON Output Contract

The CLI returns a structured JSON document with:

- `ok`,
- `lifecycle_action`: `check_safe_html`,
- `source_path`,
- `detected_format`: `markdown_compatible`,
- `proposed_profile`: `wom-safe-html/v0.1-draft`,
- `blockers`,
- `warnings`,
- `html_profile_preview`,
- `text_extraction_preview`,
- `source_reference_preview`.

`text_extraction_preview` intentionally reports counts (char/line/word) and metadata only; it does not echo the zet body, so CLI output and CI logs do not accidentally surface private zet content.

## Tests

Focused tests live in `wom-kit/tests/test_safe_html_validator.py`:

- safe Markdown body passes with `ok: true` and no blockers,
- `<script>` tag is blocked,
- `javascript:` URL inside a Markdown link is blocked,
- `<iframe>`, `<object>`, and `<embed>` elements are all blocked in one run,
- inline `onclick=` event handler attribute is blocked,
- dry-run does not modify the zet file or add any new files anywhere under the archive root,
- the CLI rejects `check-safe-html` without `--dry-run` and exits non-zero.

All seven new tests pass locally. Existing test suites continue to run unchanged.

## Compatibility

- existing Markdown-compatible zets remain valid,
- there is no schema change in this batch,
- there is no new archive folder, no new receipt file type, and no MCP surface change,
- doctor behavior is unchanged.

## Explicit Non-Goals

This batch does not implement:

- Markdown-to-WOM-Safe-HTML conversion,
- a finalized element/attribute allowlist,
- HTML migration,
- UI,
- live sharing,
- P2P transport,
- external provider sync,
- MCP parity for `check_safe_html` (deferred until the profile shape is more concrete).

## Files Updated

Public-facing updates in this batch:

- `CHANGELOG.md`
- `UPGRADE.md`
- `UPGRADE.ko.md`
- `VERSIONING.md`
- `wom-kit/README.md`
- `wom-kit/docs/concepts/wom-safe-html-profile.md`
- `wom-kit/docs/concepts/wom-safe-html-profile.ko.md`
- `wom-kit/docs/releases/v0.2.15.md`
- `wom-kit/plans/work-log-2026-05-23-safe-html-validator.md`
- `wom-kit/src/wom_kit/archive_cli.py`
- `wom-kit/src/wom_kit/archive_services.py`
- `wom-kit/tests/test_safe_html_validator.py`
