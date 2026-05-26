# Live Publication Template Source Work Log

Date: 2026-05-26
Status: documentation insight

## Context

This change records an additional UX insight from a private WordPress archive workflow, without publishing the real site URL, provider post ID, OAuth token, local script path, private category name, or private conversation contents.

The observed user need was:

```text
I do not want to describe font size, line height, heading spacing, body width,
and thumbnail rules every time I ask AI to publish a new archive post.
I want one existing post to act as the live template.
```

## Product Insight

A publication surface should support a live style template source.

The user-facing idea is simple:

```text
Make the next post look like this existing post.
```

The system-facing model is:

```text
live template post
-> fetch current style profile
-> generate a new surface projection
-> publish through provider
-> record template reference/hash in the projection receipt
```

This keeps style reuse separate from archive identity.

```text
canonical zet
  content, provenance, integrity

projection template
  surface-specific visual style

projection receipt
  evidence that a specific projection used a specific template version/hash
```

## What Changed

Updated:

- `docs/zet-publication-surface-prototype.ko.md`
- `examples/zet-publication-surface/README.ko.md`
- `examples/zet-publication-surface/zet-publication-envelope.example.json`
- `plans/work-log-2026-05-26-live-publication-template-source.md`
- `docs/public-documentation-map.ko.md`

## Safety Boundary

The public record is intentionally sanitized:

- no real WordPress URL,
- no real provider post ID,
- no OAuth token,
- no local filesystem path,
- no private AI conversation text,
- no private user category or site configuration.

## Next Step

A future implementation could add a dry-run projection command that returns both content and style provenance:

```text
archive projection-plan <archive-root>
  --zet <zet-id-or-path>
  --surface wordpress_private_blog
  --template provider_post:example_template
  --dry-run
  --format json
```

The preview should show:

- projected title/body,
- style template reference,
- template fetch timestamp,
- template content hash,
- scope/redaction gate,
- receipt preview,
- provider call plan.

Provider calls should remain separate from preview until explicit human approval.
