# Decision Log: v0.4.13 Create-Only Object-Storage Preservation

Date: 2026-08-29
Status: accepted for the v0.4.13 public implementation contract

## Context

A content-addressed remote key does not by itself prevent overwrite. A remote
object may appear between HEAD and PUT, multipart publication has a different
linearization point from single PUT, and a crash may occur after the provider
accepted bytes but before WOM published its terminal receipt. Separately,
legacy or malformed local setup receipts must not let a provider operation use
the wrong resource identity or expose private setup values.

## Decision

1. Resolve and validate canonical local setup evidence before considering a
   strict, explicitly supported legacy bridge. Unknown, malformed, orphaned,
   changing, or cross-namespace receipts fail closed with content-free codes.
2. Publish new remote bytes only through a conditional create. Single PUT uses
   `If-None-Match: *`; multipart uses it on `CompleteMultipartUpload`.
3. Treat a conditional conflict as a reason to re-read remote state, never as
   permission to retry without the condition.
4. Require HEAD and a complete GET SHA-256 match for successful preservation.
   Keep unavailable evidence nonterminal; preserve proven conflicts as durable
   `review_required` evidence without overwrite or automatic deletion.
5. Bind the private resume ledger and terminal receipts to the exact operation
   manifest. Before each provider mutation, durably reserve and charge one
   manifest-bound budget unit. Distinguish that conservative charge from an
   observed transport attempt; a crash-ambiguous reservation remains charged.
   Resume must query the exact remote target first. Only verified matching
   bytes permit no-PUT finalization. Absence, provider unavailability, and
   uncertain multipart cleanup remain nonterminal and grant no automatic retry
   authority.
6. Keep byte preservation distinct from formal adoption. It changes no central
   object-manifest location and proves no whole-archive backup claim.

## Consequences

- The operation can safely resume after uncertain local finalization without
  issuing a second unconditional upload.
- A remote mismatch is preserved for human review instead of being destroyed.
- Synthetic tests can prove protocol behavior, but only a client-authorized
  live run can prove provider acceptance and actual remote bytes.
- Public documentation and output contain no client counts, object identities,
  storage resource values, credential references, endpoints, or local paths.
