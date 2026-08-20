# Archive Infra Decision Log - v0.3.268 Title Remap Usability

Date: 2026-07-28

Status: accepted and locally verified for v0.3.268 release

## Context

The protected pilot ran the v0.3.263 title remap plan against 2,743 real
proposals. It validated 2,701 rows, but the blocked rows exposed five
operator-facing gaps:

- safe proposal-path explanations existed in the service but the CLI replaced
  all of them with one generic sentence;
- the proposal-only 200-character title ceiling excluded 21 real source names,
  including a 301-character value, although canonical title schema has no such
  ceiling;
- one blocker name conflated line breaks with double spaces and NBSP;
- URL, local-path, credential, token, and bare security-topic signals collapsed
  into one boolean with no rule name;
- the existing `human_written` basis had no complete fallback procedure.

The same pilot corrected its earlier search complaint after running the
official command. Search behavior is not part of this release.

## Decision

1. Keep the command read-only. This release improves proposal preparation and
   diagnosis; it does not create title write authority.
2. Add `ZetTitleRemapInputError` with fixed code/message pairs only for the
   proposal path and size errors whose text contains no user value or absolute
   path. Archive-root and unexpected errors keep the generic redacted message.
3. Raise the proposal title ceiling from 200 to 2,000 Unicode characters. The
   canonical frontmatter schema has no title maximum. The 2,000 ceiling also
   matches the official Notion rich-text `text.content` request limit:
   https://developers.notion.com/reference/request-limits
4. Keep normalization explicit and human-reviewed. The command does not alter
   a proposal title. It requires one line, permits only U+0020 SPACE as
   whitespace, and rejects leading, trailing, or consecutive spaces. Line
   breaks and other whitespace receive separate blocker codes.
5. Report only fixed safety rule names, never the matched substring or value.
   Local absolute paths, private provider URLs, credential assignments/private
   keys, and token-shaped values remain blockers.
6. Ordinary HTTP/HTTPS citation URLs are allowed with the content-free warning
   `title_contains_public_web_url`. Private Notion/Tiro provider URLs remain
   blocked. Bare topic words such as `password`, `token`, or `credential` are
   not secrets and do not block a title by themselves.
7. Document `basis: human_written` as the path for a missing, empty, or
   unusably vague source title. The human must write and review a specific
   replacement, refresh the canonical file SHA-256, and rerun the complete
   plan. WOM does not invent the text.

## Compatibility

The proposal schema id remains `wom-kit/zet-title-remap-proposal/v0.1`.
Increasing `maxLength` is a backward-compatible relaxation: every previously
valid row remains valid. Result fields and rule/warning codes are additive
except that the misleading `title_not_normalized_single_line` blocker is
replaced by two precise codes.

## Privacy Boundary

The result still emits no current or proposed title, title digest, exact title
length, zettel id/path, proposal filename, provider URL, matched safety value,
body, or absolute local path. A fixed rule name explains which category fired
without revealing the private text that matched.

## Consequences

The 21 real titles above 200 characters can enter the plan without truncation.
The 37 whitespace cases can be repaired using a published contract. Bookmark
style public URLs can remain in reviewed source titles, while genuinely private
locators and token-shaped values still fail closed. The six automatic-source
gaps have an explicit human-authored route.

Approved title write, immutable receipts, interruption recovery, audit, and
revert remain the next release track.
