# Archive Infrastructure Decision Log: v0.3.232 Explicit Abstract Publication

Date: 2026-07-14
Decision: accepted for v0.3.232

## Context

v0.3.231 can detect canonical zets that lack an explicit first-read abstract,
but detection alone does not prevent new gaps. Drafts must remain flexible, so
making `abstract` mandatory at capture time would incorrectly turn an early
idea into publication-ready knowledge.

## Decision

- Keep `create-draft` permissive when `abstract` is missing and return an
  explicit not-ready `first_read_check`.
- Require a normalized, bounded, safe explicit `frontmatter.abstract` at the
  canonical transition in `mint-zet`, `mint-zettel`, and legacy `promote`.
- Never accept compatibility fields as publication authorization.
- Revalidate the full draft SHA-256 and abstract SHA-256 after dry-run, then
  derive canonical text, snapshot, and receipt evidence from one byte read.
- Put only content-free status, count, limit, and hash evidence in outputs and
  receipts; never duplicate abstract text there.
- Preserve existing canonical zets and receipts without migration.

## Consequences

WOM can capture incomplete thought without friction while preventing future
canonical memory from being born without an explicit compact first read. The
gate proves structural publication readiness only. Semantic correctness,
freshness after later body revisions, and actual model consumption remain
separate work.
