# Decision: Read Bodies Only For Freshness Evidence Targets

Date: 2026-07-15
Status: Accepted for v0.3.241

## Context

A real archive confirmed that v0.3.240 removed the unrelated receipt-tree
scan, preserved privacy, and completed successfully. The remaining canonical
stage still opened complete bytes for every zet before discovering that most
rows had no valid explicit abstract. Those rows cannot become `fresh` because
there is no abstract/body pair to compare.

## Decision

1. Read bounded frontmatter for every canonical zet.
2. Use at most eight workers for that frontmatter pass when the archive has at
   least 64 canonical paths; keep small archives sequential.
3. Open complete zet bytes only when frontmatter has a valid explicit abstract
   and a current body hash is required.
4. Reparse the complete selected bytes and recheck id, redaction, and abstract
   validity before producing any hash-pair evidence target.
5. Report exact frontmatter and body read counts, selection policy, scan mode,
   and worker count without echoing content.
6. Do not add a persistent cache or combine this diagnostic with a write.

## Consequences

Missing, redacted, and unreadable-frontmatter rows retain their existing
classifications without unnecessary body I/O. Every row that can become
`fresh`, `stale`, or `unverified` still receives a complete bounded body read
and exact hash calculation. A skipped body is not claimed readable or valid;
broader file health remains the responsibility of Doctor and validation.
