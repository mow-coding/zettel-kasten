# WOM Safe HTML Profile

Status: public design baseline
Date: 2026-05-23

This document records the long-term document-format direction for `zet`.

Core continuity: zet is always text.

## Naming Boundary

Use these words precisely:

```text
WOM
  The whole open infrastructure, worldview, and reference implementation family.

zet
  A unit document minted from a zettel-kasten.

ZET
  The zettel-kasten-based communication layer that can become messenger, feed/SNS, or collaboration behavior.
```

`zet` is lowercase because it is the primitive unit.

`ZET` is uppercase because it names the communication method, service, or protocol layer built from zets.

## Why HTML Is Being Reconsidered

Earlier v0.2 documents treated a `zet` as Markdown-compatible text plus metadata.

That was a good early implementation choice:

- Markdown is easy to write.
- Git diffs are readable.
- AI can draft it easily.
- Security risk is lower than arbitrary HTML.

However, WOM is not meant to be only a note app.

WOM is open infrastructure. People should be able to build their own zettel-kasten and ZET-based SaaS layers on top of it.

That changes the format question.

Plain Markdown is useful for text-first local AI conversation, but custom SaaS layers often need richer web-native surfaces:

- media viewers,
- image galleries,
- audio/video timelines,
- maps,
- diagrams,
- collaborative workspaces,
- feeds,
- embedded source previews,
- accessibility-aware semantic structure,
- interactive but governed views.

HTML is also text, and it is the web's native structured document format. Therefore, HTML is a stronger long-term canonical/interchange/rendering target than Markdown-only storage.

## Core Decision

Do not make every minted `zet` choose between two canonical formats.

The long-term model is:

```text
authoring/import formats
  Markdown
  plain text
  safe HTML input
  external editor/provider exports

canonical/interchange/rendering target
  WOM Safe HTML Profile
```

In other words:

```text
draft input
-> normalization
-> validation
-> canonical WOM Safe HTML zet
```

Markdown remains important as an authoring and import compatibility format.

Existing Markdown zets remain valid in the v0.2 compatibility line.

## Not Arbitrary HTML

`WOM Safe HTML Profile` does not mean arbitrary web pages are canonical zets.

The profile must be:

- security-conscious,
- semantic,
- AI-readable,
- human-readable,
- source-object-aware,
- deterministic enough to replay,
- compatible with Git review,
- suitable for custom SaaS extension.

Untrusted HTML must be validated and sanitized. OWASP guidance treats untrusted HTML as unsafe unless it is handled through allowlists, output encoding, and robust sanitization. GitHub Flavored Markdown also notes that GitHub converts Markdown to HTML and then applies additional post-processing and sanitization for security and consistency.

Reference standards and guidance:

- WHATWG HTML Living Standard: `https://html.spec.whatwg.org/`
- GitHub Flavored Markdown Spec: `https://github.github.com/gfm/`
- OWASP Cross Site Scripting Prevention Cheat Sheet: `https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html`
- OWASP DOM Clobbering Prevention Cheat Sheet: `https://cheatsheetseries.owasp.org/cheatsheets/DOM_Clobbering_Prevention_Cheat_Sheet.html`

## Required Profile Properties

A future WOM Safe HTML zet should define:

- required semantic document structure,
- required metadata envelope location,
- allowed HTML elements and attributes,
- blocked elements and attributes,
- source object references through `object_id`, content hash, or manifest ref,
- deterministic text extraction for AI,
- deterministic source-reference extraction,
- accessibility requirements,
- security rules for links and embedded media,
- rules for local/package-relative assets,
- Git-diff-friendly formatting,
- compatibility with proof/receipt hashing.

## CSS And JavaScript Boundary

CSS and JavaScript are the reason HTML is more extensible than Markdown, but they are also where safety and replay risk appear.

Near-term rule:

```text
canonical zet
  stores semantic content and safe presentation hooks

view/SaaS layer
  owns richer styling and interactive behavior
```

CSS may be allowed only through a constrained profile or safe class/style tokens.

JavaScript should not be freely embedded inside canonical archive memory. Interactive behavior should normally live in a viewer, app, plugin, or ZET SaaS layer that consumes the canonical zet.

Future versions may define signed or sandboxed interaction bundles, but those should be separate from the core archival text unless the safety model is explicit.

## Source Object References

A WOM Safe HTML zet should not depend on raw provider URLs as its primary source identity.

Prefer:

```text
object_id
sha256 or content hash
manifest ref
source binding id
archive-relative ref
```

External URLs may be cited as references, but provider locations should not replace source object identity.

## Compatibility Path

The v0.2 implementation remains Markdown-compatible.

Recommended rollout:

```text
v0.2.14
  document WOM Safe HTML Profile direction

next compatible patch
  add profile validator or Markdown-to-safe-HTML dry-run

later
  preview canonical HTML during mint dry-run

future minor release
  make WOM Safe HTML the preferred canonical/interchange format
```

No existing private archive migration is required by this document.
